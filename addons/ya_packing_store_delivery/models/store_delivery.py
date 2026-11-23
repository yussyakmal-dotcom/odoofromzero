"""YA Packing -> transit -> store from previously approved RO allocations.

Generate native outgoing DO per store, no stock change on generation.
When dispatch becomes Done, create one native store receipt per store.
Store stock changes ONLY when that incoming receipt is validated.
No package assembly in this phase. TEST DATABASE ONLY.
"""
from collections import defaultdict

from odoo import fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare

TEST_DB = "erp-yussyakmal-mrp-test"


class YaStoreDeliveryPicking(models.Model):
    _inherit = "stock.picking"

    ya_store_batch_id = fields.Many2one(
        "ya.packing.batch", readonly=True, copy=False, index=True,
        ondelete="restrict", string="YA RO Batch",
    )
    ya_store_warehouse_id = fields.Many2one(
        "stock.warehouse", readonly=True, copy=False, index=True,
        string="YA Destination Store",
    )
    ya_store_stage = fields.Selection(
        [("dispatch", "Packing Dispatch"), ("receipt", "Store Receipt")],
        readonly=True, copy=False, index=True,
    )
    ya_source_dispatch_id = fields.Many2one(
        "stock.picking", readonly=True, copy=False, ondelete="restrict",
    )
    _ya_store_batch_unique = models.Constraint(
        "UNIQUE(ya_store_batch_id, ya_store_warehouse_id, ya_store_stage)",
        "A store may have only one dispatch and one receipt per RO batch.",
    )

    def button_validate(self):
        outgoing = self.filtered(
            lambda p: p.ya_store_stage == "dispatch" and p.ya_store_batch_id
        )
        if outgoing:
            if self.env.cr.dbname != TEST_DB or len(self) != 1:
                raise UserError(_("Validate YA dispatch individually in MRP test DB."))
            self._ya_check_store_dispatch_qty()
            return super(
                YaStoreDeliveryPicking, self.with_context(skip_backorder=True)
            ).button_validate()
        incoming = self.filtered(
            lambda p: p.ya_store_stage == "receipt" and p.ya_store_batch_id
        )
        if incoming:
            if self.env.cr.dbname != TEST_DB or len(self) != 1:
                raise UserError(_("Validate YA receipt individually in MRP test DB."))
            self._ya_check_store_receipt_qty()
            return super(
                YaStoreDeliveryPicking, self.with_context(skip_backorder=True)
            ).button_validate()
        return super().button_validate()

    def _ya_check_store_dispatch_qty(self):
        for picking in self:
            if picking.state in ("done", "cancel"):
                raise UserError(_("DO already closed."))
            if not picking.move_ids:
                raise UserError(_("No SKUs on store DO."))
            packing = self.env["stock.warehouse"].search([("code", "=", "PCK")])
            transit = self.env["stock.location"].search([
                ("usage", "=", "transit"),
                ("name", "=", "Inter-warehouse transit"),
                ("company_id", "in", [False, picking.company_id.id]),
            ])
            if (len(packing) != 1 or len(transit) != 1 or
                    picking.location_id != packing.lot_stock_id or
                    picking.location_dest_id != transit):
                raise UserError(_("Invalid Packing-to-transit route."))
            has_qty = False
            totals = defaultdict(float)
            for move in picking.move_ids:
                if move.state == "cancel":
                    continue
                if (move.location_id != packing.lot_stock_id or
                        move.location_dest_id != transit):
                    raise UserError(_("DO line has incorrect stock locations."))
                if float_compare(
                    move.quantity, 0, precision_rounding=move.product_uom.rounding
                ) <= 0:
                    raise UserError(_(
                        "Qty kosong/nol pada %s. Isi Qty fisik, atau keluarkan "
                        "baris yang tidak dikirim dari DO menurut SOP; "
                        "RO allocation tetap tersimpan."
                    ) % move.product_id.display_name)
                if float_compare(
                    move.quantity, move.product_uom_qty,
                    precision_rounding=move.product_uom.rounding,
                ) > 0:
                    raise UserError(_("Qty melebihi Demand: %s.") % move.product_id.display_name)
                has_qty = True
                totals[move.product_id.id] += move.product_uom._compute_quantity(
                    move.quantity, move.product_id.uom_id, round=False
                )
            if not has_qty:
                raise UserError(_("No positive shipped quantity."))
            Quant = self.env["stock.quant"].sudo()
            for pid, needed in totals.items():
                prod = self.env["product.product"].browse(pid)
                physical = sum(Quant.search([
                    ("product_id", "=", pid),
                    ("location_id", "=", packing.lot_stock_id.id),
                    ("company_id", "=", picking.company_id.id),
                ]).mapped("quantity"))
                if float_compare(needed, physical,
                                 precision_rounding=prod.uom_id.rounding) > 0:
                    raise UserError(_(
                        "Packing stock insufficient for %(product)s: "
                        "Qty %(qty).3f, stock %(physical).3f."
                    ) % {"product": prod.display_name,
                         "qty": needed, "physical": physical})

    def _ya_check_store_receipt_qty(self):
        """Prevent reception before dispatch and prevent negative transit."""
        Quant = self.env["stock.quant"].sudo()
        for picking in self:
            dispatch = picking.ya_source_dispatch_id
            if not dispatch or dispatch.state != "done":
                raise UserError(_("Packing dispatch must be Done before store receipt."))
            if (picking.location_id != dispatch.location_dest_id or
                    picking.location_dest_id != picking.ya_store_warehouse_id.lot_stock_id or
                    picking.state in ("done", "cancel")):
                raise UserError(_("Invalid destination or closed store receipt."))
            shipped = defaultdict(float)
            received = defaultdict(float)
            for move in dispatch.move_ids.filtered(lambda m: m.state == "done"):
                shipped[move.product_id.id] += move.product_uom._compute_quantity(
                    move.quantity, move.product_id.uom_id, round=False
                )
            for move in picking.move_ids:
                if move.state == "cancel":
                    continue
                if (move.location_id != picking.location_id or
                        move.location_dest_id != picking.location_dest_id):
                    raise UserError(_("Incorrect transit-to-store line locations."))
                if float_compare(move.quantity, 0,
                                 precision_rounding=move.product_uom.rounding) < 0:
                    raise UserError(_("Received Qty cannot be negative."))
                if float_compare(move.quantity, move.product_uom_qty,
                                 precision_rounding=move.product_uom.rounding) > 0:
                    raise UserError(_("Received Qty exceeds receipt Demand."))
                received[move.product_id.id] += move.product_uom._compute_quantity(
                    move.quantity, move.product_id.uom_id, round=False
                )
            if not any(qty > 0 for qty in received.values()):
                raise UserError(_("Enter received Qty before validating."))
            for pid, qty in received.items():
                prod = self.env["product.product"].browse(pid)
                if float_compare(qty, shipped.get(pid, 0.0),
                                 precision_rounding=prod.uom_id.rounding) > 0:
                    raise UserError(_("Cannot receive more than dispatched: %s.") %
                                    prod.display_name)
                in_transit = sum(Quant.search([
                    ("product_id", "=", pid),
                    ("location_id", "=", picking.location_id.id),
                    ("company_id", "=", picking.company_id.id),
                ]).mapped("quantity"))
                if float_compare(qty, in_transit,
                                 precision_rounding=prod.uom_id.rounding) > 0:
                    raise UserError(_("Not enough stock in transit: %s.") %
                                    prod.display_name)

    def _action_done(self):
        receipts = self.filtered(
            lambda p: p.ya_store_stage == "receipt" and p.ya_store_batch_id
        )
        if receipts:
            if self.env.cr.dbname != TEST_DB or len(receipts) != len(self):
                raise UserError(_("Complete YA store receipts separately in test DB."))
            self._ya_check_store_receipt_qty()
            return super(
                YaStoreDeliveryPicking,
                self.with_context(cancel_backorder=True),
            )._action_done()
        dispatches = self.filtered(
            lambda p: p.ya_store_stage == "dispatch" and p.ya_store_batch_id
        )
        if not dispatches:
            return super()._action_done()
        if self.env.cr.dbname != TEST_DB or len(dispatches) != len(self):
            raise UserError(_("Complete YA Packing dispatch separately on test DB."))
        self._ya_check_store_dispatch_qty()
        result = super(
            YaStoreDeliveryPicking,
            self.with_context(cancel_backorder=True),
        )._action_done()
        for dispatch in dispatches:
            if dispatch.state != "done":
                raise UserError(_("Packing dispatch did not reach Done."))
            if self.env["stock.picking"].search_count([
                ("ya_source_dispatch_id", "=", dispatch.id),
            ]):
                continue
            store = dispatch.ya_store_warehouse_id
            incoming_type = store.in_type_id
            transit = dispatch.location_dest_id
            if (not store.lot_stock_id or not incoming_type or
                    incoming_type.code != "incoming" or
                    store.company_id != dispatch.company_id):
                raise UserError(_("Store receiving configuration invalid."))
            shipped = defaultdict(float)
            products = {}
            for move in dispatch.move_ids.filtered(lambda m: m.state == "done"):
                qty = move.product_uom._compute_quantity(
                    move.quantity, move.product_id.uom_id, round=False)
                if qty > 0:
                    shipped[move.product_id.id] += qty
                    products[move.product_id.id] = move.product_id
            if not shipped:
                raise UserError(_("No shipped items to create store receipt."))
            receipt = self.env["stock.picking"].create({
                "ya_store_batch_id": dispatch.ya_store_batch_id.id,
                "ya_store_warehouse_id": store.id,
                "ya_store_stage": "receipt",
                "ya_source_dispatch_id": dispatch.id,
                "picking_type_id": incoming_type.id,
                "company_id": dispatch.company_id.id,
                "location_id": transit.id,
                "location_dest_id": store.lot_stock_id.id,
                "origin": dispatch.name,
            })
            self.env["stock.move"].create([{
                "picking_id": receipt.id,
                "product_id": pid,
                "product_uom": products[pid].uom_id.id,
                "product_uom_qty": qty,
                "location_id": transit.id,
                "location_dest_id": store.lot_stock_id.id,
                "company_id": dispatch.company_id.id,
            } for pid, qty in sorted(shipped.items())])
            receipt.action_confirm()
        return result


class YaPackingStoreDeliveryBatch(models.Model):
    _inherit = "ya.packing.batch"

    ya_store_delivery_ids = fields.One2many(
        "stock.picking", "ya_store_batch_id", readonly=True,
        string="DO and Store Receipts",
    )
    ya_store_delivery_count = fields.Integer(
        compute="_compute_ya_store_delivery_count",
    )

    def _compute_ya_store_delivery_count(self):
        for batch in self:
            batch.ya_store_delivery_count = len(batch.ya_store_delivery_ids)

    def action_ya_open_store_deliveries(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("DO and Store Receipts - %s") % self.name,
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "domain": [("id", "in", self.ya_store_delivery_ids.ids)],
            "context": {"create": False},
            "target": "current",
        }

    def action_ya_generate_store_do(self):
        self.ensure_one()
        if self.env.cr.dbname != TEST_DB:
            raise UserError(_("Generate DO is allowed in test DB only."))
        if not (self.env.user.has_group("ya_store_ro.group_ya_packing_admin") or
                self.env.user.has_group("stock.group_stock_manager")):
            raise UserError(_("Packing Admin or Inventory Administrator required."))
        if self.state != "production_ok":
            raise UserError(_("Generate DO from a Produksi OK batch only."))
        self.env.cr.execute(
            "SELECT id FROM ya_packing_batch WHERE id = %s FOR UPDATE",
            [self.id],
        )
        if self.ya_store_delivery_ids:
            return self.action_ya_open_store_deliveries()

        packing = self.env["stock.warehouse"].search([("code", "=", "PCK")])
        transit = self.env["stock.location"].search([
            ("usage", "=", "transit"),
            ("name", "=", "Inter-warehouse transit"),
            ("company_id", "in", [False, packing.company_id.id]),
        ])
        if (len(packing) != 1 or not packing.lot_stock_id or
                len(transit) != 1 or not packing.out_type_id):
            raise UserError(_("Packing/Transit route is not uniquely configured."))
        if packing.out_type_id.code != "outgoing":
            raise UserError(_("Packing outgoing operation type is invalid."))

        # Require finished-goods handoff for this batch before DO generation.
        fg = self.ya_fg_transfer_ids
        kitchens = self.line_ids.mapped("mo_id").filtered(
            lambda mo: mo.state == "done" and
            mo.product_id.default_code != "11076"
        ).mapped("picking_type_id.warehouse_id")
        if (not fg or any(p.state != "done" for p in fg) or
                set(fg.mapped("ya_fg_kitchen_id").ids) != set(kitchens.ids)):
            raise UserError(_(
                "Complete Produk Jadi ke Packing for this batch first."
            ))

        groups = defaultdict(lambda: defaultdict(float))
        for row in self.allocation_ids:
            if row.qty_allocated <= 0:
                continue
            wh = row.store_warehouse_id
            if (not wh.lot_stock_id or wh.company_id != packing.company_id or
                    wh == packing):
                raise UserError(_("Invalid store destination on %s.") % row.product_id.display_name)
            groups[wh.id][row.product_id.id] += row.qty_allocated
        if not groups:
            raise UserError(_("No store allocations with positive Qty."))

        Picking = self.env["stock.picking"]
        Move = self.env["stock.move"]
        Quant = self.env["stock.quant"].sudo()
        available = {}
        for skus in groups.values():
            for pid in skus:
                if pid not in available:
                    available[pid] = max(0.0, sum(Quant.search([
                        ("product_id", "=", pid),
                        ("location_id", "=", packing.lot_stock_id.id),
                        ("company_id", "=", packing.company_id.id),
                    ]).mapped("quantity")) - sum(Quant.search([
                        ("product_id", "=", pid),
                        ("location_id", "=", packing.lot_stock_id.id),
                        ("company_id", "=", packing.company_id.id),
                    ]).mapped("reserved_quantity")))
        for wh_id, skus in sorted(groups.items()):
            store = self.env["stock.warehouse"].browse(wh_id)
            picking = Picking.create({
                "ya_store_batch_id": self.id,
                "ya_store_warehouse_id": store.id,
                "ya_store_stage": "dispatch",
                "picking_type_id": packing.out_type_id.id,
                "company_id": packing.company_id.id,
                "location_id": packing.lot_stock_id.id,
                "location_dest_id": transit.id,
                "origin": "%s / %s" % (self.name, store.code),
            })
            move_records = []
            for pid, qty in sorted(skus.items()):
                prod = self.env["product.product"].browse(pid)
                move_records.append({
                    "picking_id": picking.id,
                    "product_id": pid,
                    "product_uom": prod.uom_id.id,
                    "product_uom_qty": qty,
                    "location_id": packing.lot_stock_id.id,
                    "location_dest_id": transit.id,
                    "company_id": packing.company_id.id,
                })
            moves = Move.create(move_records)
            picking.action_confirm()
            for move in moves:
                # Populate Done Qty only where all allocated demand can be met
                # from currently unreserved, untracked PCK stock. No partial
                # shipment decision is inferred.
                prod = move.product_id
                qty = move.product_uom_qty
                if (prod.tracking == "none" and
                        float_compare(available[prod.id], qty,
                                      precision_rounding=prod.uom_id.rounding) >= 0):
                    move.write({"quantity": qty})
                    available[prod.id] -= qty
        return self.action_ya_open_store_deliveries()
