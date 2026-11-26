"""One-click native internal stock movement: MO Done -> kitchen -> Packing.

Strictly test DB. No intermediate picking list or receiving confirmation.
Each Packing batch issues at most one standard picking per source kitchen.
Other batches and supplemental Odoo transfers are NOT blocked.
"""
from collections import defaultdict

from odoo import fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare


TEST_DB = "erp-yussyakmal-mrp-test"


class YaFinishedPackingPicking(models.Model):
    _inherit = "stock.picking"

    ya_fg_batch_id = fields.Many2one(
        "ya.packing.batch", readonly=True, copy=False, index=True,
        ondelete="restrict", string="YA Finished Goods Batch",
    )
    ya_fg_kitchen_id = fields.Many2one(
        "stock.warehouse", readonly=True, copy=False, index=True,
        string="YA Finished Goods Kitchen",
    )
    _ya_fg_batch_kitchen_unique = models.Constraint(
        "UNIQUE(ya_fg_batch_id, ya_fg_kitchen_id)",
        "Finished goods for this batch and kitchen have already been moved.",
    )


class YaFinishedPackingBatch(models.Model):
    _inherit = "ya.packing.batch"

    ya_fg_transfer_ids = fields.One2many(
        "stock.picking", "ya_fg_batch_id",
        readonly=True, string="Dapur ke Packing",
    )
    ya_fg_transfer_count = fields.Integer(
        compute="_compute_ya_fg_transfer_count", string="Transfer ke Packing",
    )

    def _compute_ya_fg_transfer_count(self):
        for batch in self:
            batch.ya_fg_transfer_count = len(batch.ya_fg_transfer_ids)

    def action_ya_fg_open_transfers(self):
        self.ensure_one()
        if not (self.env.user.has_group("ya_store_ro.group_ya_packing_admin") or
                self.env.user.has_group("stock.group_stock_manager")):
            raise UserError(_("Packing Admin or Inventory Administrator required."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Dapur ke Packing - %s") % self.name,
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "domain": [("id", "in", self.ya_fg_transfer_ids.ids)],
            "context": {"create": False},
            "target": "current",
        }

    def _ya_fg_db_allowed(self):
        self.ensure_one()
        return self.env.cr.dbname == TEST_DB

    def _ya_fg_validate_native_picking(self,picking,moves):
        """Default Fase1 native handoff; extension may strengthen reservations."""
        picking.action_confirm()
        # The same location is physically shared; native Odoo operation
        # completes both the dispatch and receipt in one validation.
        for move in moves:
            if move.state in ("done", "cancel"):
                raise UserError(_("Unexpected move state for %s.") % move.product_id.display_name)
            move.write({"quantity": move.product_uom_qty})
        result = picking.with_context(
            skip_immediate=True, skip_backorder=True,
            cancel_backorder=True,
        ).button_validate()
        if isinstance(result, dict) or picking.state != "done":
            raise UserError(_(
                "Odoo did not complete the kitchen-to-Packing move. "
                "Transaction rolled back; no partial batch shipment."
            ))

    def action_ya_fg_move_to_packing(self):
        """Atomically make and validate standard internal movements per kitchen.

        No manual receiving step. Existing batch-specific picking is never
        re-issued by a double click. Only MO Done output is included.
        A cancelled/unfinished MO is not silently represented as produced.
        """
        self.ensure_one()
        if not self._ya_fg_db_allowed():
            raise UserError(_("Finished-goods transfer is test database only."))
        if self.state != "production_ok":
            raise UserError(_("Select a Produksi OK Packing batch."))
        if not (self.env.user.has_group("ya_store_ro.group_ya_packing_admin") or
                self.env.user.has_group("stock.group_stock_manager")):
            raise UserError(_("Packing Admin or Inventory Administrator required."))

        # A lock serializes two users clicking the same batch simultaneously.
        self.env.cr.execute(
            "SELECT id FROM ya_packing_batch WHERE id = %s FOR UPDATE",
            [self.id],
        )
        if self.ya_fg_transfer_ids:
            return self.action_ya_fg_open_transfers()

        packing = self.env["stock.warehouse"].search([("code", "=", "PCK")])
        if len(packing) != 1 or not packing.lot_stock_id:
            raise UserError(_("Exactly one Packing warehouse PCK/Stock required."))
        dest = packing.lot_stock_id
        if dest.usage != "internal":
            raise UserError(_("Packing stock location must be Internal."))

        # WIP filling Jamur (11076) observed in the tested batches is an
        # intermediate component, not a finished product for Packing.
        # The default exclusion may be overridden through a System Parameter
        # after the owner approves an explicit finished-goods SKU policy.
        excluded_codes = {
            x.strip() for x in (
                self.env["ir.config_parameter"].sudo().get_param(
                    "ya_finished_packing_transfer.exclude_sku_codes", "11076"
                ) or ""
            ).split(",") if x.strip()
        }
        groups = defaultdict(lambda: defaultdict(float))
        products = {}
        kitchens = {}
        mos = self.line_ids.mapped("mo_id")
        if not mos:
            raise UserError(_("Batch has no Manufacturing Orders."))
        skipped = []
        for mo in mos:
            if mo.state != "done":
                skipped.append(mo.name)
                continue
            if mo.product_id.default_code in excluded_codes:
                skipped.append(mo.name)
                continue
            kitchen = mo.picking_type_id.warehouse_id
            if (not kitchen or not kitchen.lot_stock_id or kitchen == packing
                    or kitchen.company_id != packing.company_id
                    or mo.location_dest_id != kitchen.lot_stock_id):
                raise UserError(_("Invalid production output location on %s.") % mo.name)
            finished = mo.move_finished_ids.filtered(
                lambda m: m.state == "done" and
                m.product_id == mo.product_id and
                m.location_dest_id == kitchen.lot_stock_id
            )
            if not finished:
                raise UserError(_("MO %s Done but no finished stock move.") % mo.name)
            qty = sum(
                m.product_uom._compute_quantity(
                    m.quantity, mo.product_id.uom_id, round=False
                ) for m in finished
            )
            if float_compare(
                qty, 0, precision_rounding=mo.product_id.uom_id.rounding
            ) <= 0:
                raise UserError(_("MO %s has no positive finished Qty.") % mo.name)
            groups[kitchen.id][mo.product_id.id] += qty
            products[mo.product_id.id] = mo.product_id
            kitchens[kitchen.id] = kitchen
        if not groups:
            raise UserError(_("No eligible completed finished goods to transfer."))

        # Check physical stock by exact source location; no negative stock.
        # This is only a critical inventory integrity guard, not a buffer rule.
        Quant = self.env["stock.quant"].sudo()
        for wh_id, sku_quantities in groups.items():
            kitchen = kitchens[wh_id]
            for product_id, qty in sku_quantities.items():
                prod = products[product_id]
                physical = sum(Quant.search([
                    ("product_id", "=", product_id),
                    ("location_id", "=", kitchen.lot_stock_id.id),
                    ("company_id", "=", packing.company_id.id),
                ]).mapped("quantity"))
                if float_compare(
                    qty, physical,
                    precision_rounding=prod.uom_id.rounding,
                ) > 0:
                    raise UserError(_(
                        "Stok dapur tidak cukup: %(product)s %(qty).3f, "
                        "fisik %(physical).3f. Tidak boleh stok minus."
                    ) % {"product": prod.display_name, "qty": qty,
                         "physical": physical})

        Picking = self.env["stock.picking"].with_company(packing.company_id)
        Move = self.env["stock.move"].with_company(packing.company_id)
        for wh_id, sku_quantities in sorted(groups.items()):
            kitchen = kitchens[wh_id]
            operation = kitchen.int_type_id
            if (not operation or operation.code != "internal" or
                    operation.company_id != packing.company_id):
                raise UserError(_("Invalid kitchen Internal Operation Type: %s.") % kitchen.name)
            picking = Picking.create({
                "ya_fg_batch_id": self.id,
                "ya_fg_kitchen_id": kitchen.id,
                "picking_type_id": operation.id,
                "company_id": packing.company_id.id,
                "location_id": kitchen.lot_stock_id.id,
                "location_dest_id": dest.id,
                "origin": "YA-FG-%s-%s" % (self.id, kitchen.code),
            })
            moves = Move.create([{
                "picking_id": picking.id,
                "product_id": product_id,
                "product_uom": products[product_id].uom_id.id,
                "product_uom_qty": qty,
                "location_id": kitchen.lot_stock_id.id,
                "location_dest_id": dest.id,
                "company_id": packing.company_id.id,
            } for product_id, qty in sorted(sku_quantities.items())])
            self._ya_fg_validate_native_picking(picking,moves)
        return self.action_ya_fg_open_transfers()
