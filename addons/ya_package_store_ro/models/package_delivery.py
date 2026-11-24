"""Add native finished Paket SKU lines to the EXISTING store DO per shop.

Original ya_packing_store_delivery remains the owner of dispatch, transit
and store receipt. Joint batches first finish actual native Paket assembly,
then extend the same per-shop DO instead of creating a second distribution
flow. No fictitious Paket stock; native final delivery Qty can be zero.
"""
from collections import defaultdict

from .package_finish_rules import group_package_finish_demands

from odoo import models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare

from odoo.addons.ya_store_ro.models.packing_lock import lock_ro_slot


TEST_DB = "erp-yussyakmal-mrp-test"


class YaPackingBatchPackageDelivery(models.Model):
    _inherit = "ya.packing.batch"

    def action_ya_generate_store_do(self):
        self.ensure_one()
        if not self.ya_has_package:
            return super().action_ya_generate_store_do()

        if self.env.cr.dbname != TEST_DB:
            raise UserError(_("Paket delivery is test DB only."))
        if not (self.env.user.has_group("ya_store_ro.group_ya_packing_admin") or
                self.env.user.has_group("stock.group_stock_manager")):
            raise UserError(_("Packing/Inventory Administrator required."))

        lock_ro_slot(self.env.cr, self.delivery_date, self.slot)
        self.env.cr.execute(
            "SELECT id FROM ya_packing_batch WHERE id = %s FOR UPDATE",
            [self.id],
        )
        if self.ya_store_delivery_ids:
            # Reopening existing dispatch never creates a second package DO
            # or duplicates native stock moves.
            return self.action_ya_open_store_deliveries()

        frozen = group_package_finish_demands([
            {"product_id": d.product_id.id,
             "store_id": d.store_warehouse_id.id,
             "qty": d.qty_requested}
            for d in self.ya_package_demand_ids
        ])
        demand_by_sku = frozen["assembly_mo_qty"]
        mos = self.ya_package_assembly_mo_ids
        if not demand_by_sku or set(mos.mapped("product_id").ids) != set(demand_by_sku):
            raise UserError(_("Create Paket assembly MOs before generating DO."))
        for mo in mos:
            if mo.state != "done":
                raise UserError(_(
                    "Selesaikan MO Rakit Paket di Packing sebelum Generate DO. "
                    "Stok Paket jadi baru tersedia setelah MO Done."
                ))
            # Trust actual DONE finished stock moves, never just the MO demand
            # or planned quantity. The same criterion is used by kitchen FG
            # transfers; it works independently of optional qty_produced fields.
            finished = mo.move_finished_ids.filtered(
                lambda move: move.state == "done" and
                move.product_id == mo.product_id and
                move.location_dest_id == mo.location_dest_id
            )
            actual = sum(move.product_uom._compute_quantity(
                move.quantity, mo.product_id.uom_id, round=False
            ) for move in finished)
            # Native MO Done is evidence of actual finished inventory, NOT
            # proof that every unit requested by the stores was produced.
            # Existing DO workflow allows the operator to ship a smaller Qty
            # or enter Qty 0 with a reason. Do not block unrelated store SKUs.
            if float_compare(
                actual, 0.0,
                precision_rounding=mo.product_id.uom_id.rounding,
            ) < 0:
                raise UserError(_(
                    "Paket %s has invalid negative finished Qty."
                ) % mo.product_id.display_name)
            # If actual is below frozen store demand, native DO is still
            # created with the requested Qty and operator selects actual
            # shipped Qty (or zero + a reason), exactly like ordinary DO.
            # If actual is higher, extra stock can be transferred separately;
            # never silently inflate a store's confirmed Paket allocation.

        # Base implementation continues to control existing ordinary RO DO
        # creation, PCK finished transfer, and native transit/store receipts.
        # For joint batch with ordinary allocations, create those DOs first.
        if self.allocation_ids.filtered(lambda a: a.qty_allocated > 0):
            result = super().action_ya_generate_store_do()
        else:
            # Package-only slot: still validate existing kitchen-to-PCK
            # transfer before preparing native outgoing pickings.
            if not self.ya_fg_transfer_ids or any(
                    p.state != "done" for p in self.ya_fg_transfer_ids):
                raise UserError(_("Finish kitchen-to-PCK transfer first."))
            result = self.action_ya_open_store_deliveries()

        Packing = self.env["stock.warehouse"].sudo().search([
            ("code", "=", "PCK")])
        Transit = self.env["stock.location"].sudo().search([
            ("usage", "=", "transit"),
            ("name", "=", "Inter-warehouse transit"),
            ("company_id", "in", [False, Packing.company_id.id]),
        ])
        if (len(Packing) != 1 or not Packing.lot_stock_id or
                not Packing.out_type_id or
                Packing.out_type_id.code != "outgoing" or
                len(Transit) != 1):
            raise UserError(_("PCK/Transit dispatch route is not configured uniquely."))

        existing = {
            picking.ya_store_warehouse_id.id: picking
            for picking in self.ya_store_delivery_ids
            if picking.ya_store_stage == "dispatch"
        }
        totals = frozen["store_do_qty"]
        for store_id in totals:
            store = self.env["stock.warehouse"].browse(store_id)
            if (not store.lot_stock_id or store == Packing or
                    store.company_id != Packing.company_id):
                raise UserError(_("Invalid Paket destination store: %s") % store.name)

        Picking = self.env["stock.picking"]
        Move = self.env["stock.move"]
        Quant = self.env["stock.quant"].sudo()
        available = {}
        for quantities in totals.values():
            for product_id in quantities:
                if product_id not in available:
                    quants = Quant.search([
                        ("product_id", "=", product_id),
                        ("location_id", "=", Packing.lot_stock_id.id),
                        ("company_id", "=", Packing.company_id.id),
                    ])
                    available[product_id] = max(
                        0.0, sum(quants.mapped("quantity")) -
                        sum(quants.mapped("reserved_quantity")))
        for store_id, quantities in sorted(totals.items()):
            store = self.env["stock.warehouse"].browse(store_id)
            picking = existing.get(store_id)
            newly_created = not bool(picking)
            if newly_created:
                picking = Picking.create({
                    "ya_store_batch_id": self.id,
                    "ya_store_warehouse_id": store.id,
                    "ya_store_stage": "dispatch",
                    "picking_type_id": Packing.out_type_id.id,
                    "company_id": Packing.company_id.id,
                    "location_id": Packing.lot_stock_id.id,
                    "location_dest_id": Transit.id,
                    "origin": "%s / %s" % (self.name, store.code),
                })
            move_values = []
            for product_id, quantity in sorted(quantities.items()):
                if picking.move_ids.filtered(
                        lambda m: m.product_id.id == product_id):
                    raise UserError(_(
                        "Paket SKU already appears on ordinary RO DO: %s"
                    ) % product_id)
                product = self.env["product.product"].browse(product_id)
                move_values.append({
                    "picking_id": picking.id,
                    "product_id": product_id,
                    "product_uom": product.uom_id.id,
                    "product_uom_qty": float(quantity),
                    "location_id": Packing.lot_stock_id.id,
                    "location_dest_id": Transit.id,
                    "company_id": Packing.company_id.id,
                })
            new_moves = Move.create(move_values)
            # Match the native original DO workflow: a newly created
            # package-only picking is confirmed at the picking level.
            # When appending to an already confirmed ordinary RO picking,
            # only confirm the freshly added Paket moves.
            if newly_created:
                picking.action_confirm()
            else:
                new_moves._action_confirm()
            for move in new_moves:
                product = move.product_id
                quantity = move.product_uom_qty
                if (product.tracking == "none" and
                        float_compare(
                            available[product.id], quantity,
                            precision_rounding=product.uom_id.rounding) >= 0):
                    move.write({"quantity": quantity})
                    available[product.id] -= quantity

        # The standard DO button must now open a combined per-store document.
        # No stock is physically transferred until Packing dispatch validates.
        return self.action_ya_open_store_deliveries()
