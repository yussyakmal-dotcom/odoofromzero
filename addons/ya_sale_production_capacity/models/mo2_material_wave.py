"""Clone-only MO2 incremental CDC -> kitchen material document.

MO1 transfer logic remains in ya_material_requirement, untouched.
MO2 has its own stock.picking identity linked to the immutable MO2 release
line. ONE picking per MO2, independent from UNIQUE(batch,kitchen) for MO1.
Issue the FULL raw requirement of the CONFIRMED MO2 only (not MO1).
CDC shortage does not suppress the transfer demand. Operator must validate
the actual amount through native Odoo. No stock quant or inventory valuation
is posted by creating this document; no GUI button until rollback QA.
"""
from collections import defaultdict

from odoo import fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare

from odoo.addons.ya_store_ro.models.packing_lock import lock_ro_slot

CLONE_DB = "erp-yussyakmal-mrp-test-RO_SO"


class StockPickingMo2Material(models.Model):
    _inherit = "stock.picking"

    ya_mo2_material_release_line_id = fields.Many2one(
        "ya.sale.mo2.release.line",
        string="YA Incremental MO2 CDC Transfer",
        readonly=True,
        copy=False,
        index=True,
        ondelete="restrict",
    )

    _unique_mo2_material_wave = models.Constraint(
        "UNIQUE(ya_mo2_material_release_line_id)",
        "The same MO2 already has its CDC material transfer.",
    )


class YaMo2MaterialReleaseLine(models.Model):
    _inherit = "ya.sale.mo2.release.line"

    ya_mo2_material_picking_ids = fields.One2many(
        "stock.picking",
        "ya_mo2_material_release_line_id",
        string="CDC → Dapur for MO2",
        readonly=True,
    )

    def _ya_create_mo2_cdc_transfer(self):
        """Create (NOT validate) one native CDC transfer for this exact MO2.

        Must be invoked inside the normal Odoo HTTP transaction (later button)
        or inside a rollback test. No explicit commit, no handoff to MO1.
        """
        self.ensure_one()
        if self.env.cr.dbname != CLONE_DB:
            raise UserError(_("MO2 CDC transfer is allowed only on RO_SO clone."))
        if not self.env.user.has_group("stock.group_stock_manager"):
            raise UserError(_("Inventory Administrator is required for MO2 CDC."))
        session = self.finalization_id
        batch = session.batch_id
        mo = self.mo_id
        product = self.product_id

        lock_ro_slot(self.env.cr, batch.delivery_date, batch.slot)
        # Native row lock as second line of defense against concurrent clicks
        # by two workers for this very MO2 release line.
        self.env.cr.execute(
            "SELECT id FROM ya_sale_mo2_release_line WHERE id = %s FOR UPDATE",
            (self.id,),
        )
        self.invalidate_recordset(["ya_mo2_material_picking_ids"])
        if batch.ya_pp1_design_b_snapshot:
            session._ya_pp2_frozen_facts()
            if (mo.product_uom_id._compute_quantity(mo.product_qty, product.uom_id, round=False)
                    != self.qty_mo2 or mo.bom_id != self.planning_line_id._capacity_bom()):
                raise UserError(_("Design B MO2 output/BoM changed after release."))
        existing = self.ya_mo2_material_picking_ids
        if existing:
            if len(existing) != 1:
                raise UserError(_("More than one material document linked to MO2."))
            return existing

        if (batch.state != "production_ok" or session.delivery_date != batch.delivery_date
                or session.slot != batch.slot
                or self.planning_line_id.planning_id.state != "published"
                or self.planning_line_id.product_id != product
                or mo.product_id != product
                or mo.ya_packing_batch_line_id
                or mo.state != "confirmed"
                or batch.ya_store_delivery_ids
                or batch.ya_package_assembly_mo_ids
                or (batch.ya_fg_transfer_ids and not batch.ya_pp1_design_b_snapshot)):
            raise UserError(_(
                "MO2 and frozen Packing batch not ready for CDC transfer. "
                "Reject MOs in progress/cancelled/done and advanced Packing."
            ))
        if not self.finalization_id.line_ids.filtered(
                lambda line: line.id == self.id and line.mo_id == mo):
            raise UserError(_("Invalid MO2 finalization membership."))

        kitchen = mo.picking_type_id.warehouse_id
        company = mo.company_id
        if (not kitchen or not kitchen.lot_stock_id
                or kitchen.company_id != company
                or mo.location_src_id != mo.picking_type_id.default_location_src_id
                or mo.location_dest_id != kitchen.lot_stock_id
                or not kitchen.lot_stock_id.usage == "internal"):
            raise UserError(_("MO2 kitchen raw material/finished route mismatch."))
        CDC = self.env["stock.warehouse"].sudo().search([
            ("code", "=", "CDC"), ("company_id", "=", company.id),
        ])
        if len(CDC) != 1 or CDC == kitchen:
            raise UserError(_("Exactly one distinct CDC warehouse is required."))
        cdc = CDC[0]
        source = cdc.lot_stock_id
        operation = cdc.int_type_id
        if (not source or source.usage != "internal" or
                not operation or operation.code != "internal"
                or operation.warehouse_id != cdc
                or operation.company_id != company):
            raise UserError(_("CDC native internal operation type invalid."))

        origin = "YA-MO2-CDC-%s" % mo.id
        Picking = self.env["stock.picking"].with_company(company)
        existing_origin = Picking.search([("origin", "=", origin)], limit=1)
        if existing_origin:
            raise UserError(_(
                "Unlinked MO2 CDC picking already exists (%s); reconcile."
            ) % existing_origin.display_name)

        # Validate the MO's own confirmed raw stock moves and kitchen location
        # sources; do not calculate BoM independently or read MO1's raw moves.
        raw = mo.move_raw_ids
        if not raw or any(m.state in ("done", "cancel") for m in raw):
            raise UserError(_("MO2 confirmed raw moves missing/closed."))
        child_locations = set(self.env["stock.location"].search([
            ("id", "child_of", kitchen.lot_stock_id.id),
        ]).ids)
        requirements = defaultdict(float)
        products = {}
        for move in raw:
            mat = move.product_id
            if (not mat or not move.product_uom
                    or move.location_id.id not in child_locations
                    or (mat.company_id and mat.company_id != company)
                    or ("is_storable" in mat._fields and not mat.is_storable)):
                raise UserError(_("MO2 raw material route / type invalid."))
            qty = move.product_uom._compute_quantity(
                move.product_uom_qty, mat.uom_id, round=False,
            )
            if float_compare(qty, 0, precision_rounding=mat.uom_id.rounding) < 0:
                raise UserError(_("Negative MO2 raw material requirement."))
            if not qty:
                continue
            requirements[mat.id] += qty
            products[mat.id] = mat
        if not requirements:
            raise UserError(_("No positive MO2 raw material demand."))

        Move = self.env["stock.move"].with_company(company)
        if not {"quantity", "product_uom", "product_uom_qty",
                "picking_id"}.issubset(Move._fields):
            raise UserError(_("Expected native Odoo 19 stock.move Qty fields missing."))

        vals = {
            "ya_mo2_material_release_line_id": self.id,
            "picking_type_id": operation.id,
            "company_id": company.id,
            "location_id": source.id,
            "location_dest_id": kitchen.lot_stock_id.id,
            "origin": origin,
        }
        if "note" in Picking._fields:
            vals["note"] = (
                "YA MO2 only: %s | %s %s | CDC → %s. "
                "Demand is FULL confirmed MO2 raw material requirement, "
                "independent of MO1 and kitchen buffer. "
                "Review actual Quantity before native Validate. "
                "This action did NOT move stock."
            ) % (mo.name, batch.delivery_date.strftime("%Y-%b-%d"),
                 batch.slot, kitchen.display_name)
        picking = Picking.create(vals)
        moves = Move.create([{
            "picking_id": picking.id,
            "product_id": pid,
            "product_uom": products[pid].uom_id.id,
            "product_uom_qty": qty,
            "location_id": source.id,
            "location_dest_id": kitchen.lot_stock_id.id,
            "company_id": company.id,
        } for pid, qty in sorted(requirements.items())])
        if len(moves) != len(requirements):
            raise UserError(_("MO2 material line count mismatch."))

        # Mimic tested Phase1 low-click prefill for available untracked
        # exact CDC stock-bin items; do not misrepresent unavailable quantities.
        Quant = self.env["stock.quant"].sudo().with_company(company)
        for move in moves:
            mat = move.product_id
            if mat.tracking != "none":
                continue
            quants = Quant.search([
                ("product_id", "=", mat.id),
                ("location_id", "=", source.id),
                ("company_id", "=", company.id),
                ("lot_id", "=", False),
                ("package_id", "=", False),
                ("owner_id", "=", False),
            ])
            free = sum(max(0, q.quantity - q.reserved_quantity) for q in quants)
            if float_compare(move.product_uom_qty, free,
                             precision_rounding=mat.uom_id.rounding) > 0:
                continue
            move.write({"quantity": move.product_uom_qty})
            move.invalidate_recordset(["quantity", "state"])
            if (move.state in ("done", "cancel") or
                    float_compare(
                        move.quantity, move.product_uom_qty,
                        precision_rounding=mat.uom_id.rounding,
                    ) != 0):
                raise UserError(_("MO2 CDC prefilling mismatch, rollback."))
        if picking.state in ("done", "cancel"):
            raise UserError(_("MO2 CDC document already closed unexpectedly."))
        return picking
