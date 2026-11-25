"""Clone-only independent MO2 finished-goods internal transfer draft.

Never mix with the established Fase1 MO1 (batch,kitchen) picking. MO2 uses
a unique native stock.picking link to ONE immutable MO2 release line.
Only a DONE native MO2 with matching DONE finished moves and available
physical kitchen stock can create its own draft/confirmed PCK handoff.

The method intentionally does NOT validate stock, does not mark a receipt,
does not create an SO/RO DO, and has no operator UI button yet.
"""
from odoo import fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare

from odoo.addons.ya_store_ro.models.packing_lock import lock_ro_slot

from .mo2_finished_goods_rules import (
    Mo2FinishedGoodsError, plan_mo2_finished_goods_handoff,
)

CLONE_DB = "erp-yussyakmal-mrp-test-RO_SO"


class YaMo2FinishedGoodsPicking(models.Model):
    _inherit = "stock.picking"

    ya_mo2_fg_release_line_id = fields.Many2one(
        "ya.sale.mo2.release.line",
        string="YA MO2 Finished Goods to Packing",
        readonly=True, index=True, copy=False, ondelete="restrict",
    )

    _unique_mo2_finished_goods_picking = models.Constraint(
        "UNIQUE(ya_mo2_fg_release_line_id)",
        "Exactly one MO2 finished-goods picking is permitted per release line.",
    )


class YaMo2FinishedGoodsRelease(models.Model):
    _inherit = "ya.sale.mo2.release.line"

    ya_mo2_fg_picking_ids = fields.One2many(
        "stock.picking", "ya_mo2_fg_release_line_id",
        readonly=True, string="MO2 Produk Jadi ke Packing",
    )

    def _ya_create_mo2_fg_transfer(self):
        """Prepare, but DO NOT validate, MO2's native internal transfer.

        Internal entrypoint for clone-only rollback QA, no GUI until full
        native stock and Packing allocation tests succeed.
        """
        self.ensure_one()
        if self.env.cr.dbname != CLONE_DB:
            raise UserError(_("MO2 Finished Goods is authorized only on RO_SO clone."))
        if not (self.env.user.has_group("ya_store_ro.group_ya_packing_admin")
                or self.env.user.has_group("stock.group_stock_manager")):
            raise UserError(_("Packing Admin or Inventory Administrator required."))

        batch = self.finalization_id.batch_id
        mo = self.mo_id
        product = self.product_id
        lock_ro_slot(self.env.cr, batch.delivery_date, batch.slot)
        self.env.cr.execute(
            "SELECT id FROM ya_sale_mo2_release_line WHERE id = %s FOR UPDATE",
            (self.id,),
        )
        self.invalidate_recordset(["ya_mo2_fg_picking_ids"])
        existing = self.ya_mo2_fg_picking_ids
        if existing:
            if len(existing) != 1 or existing.ya_mo2_fg_release_line_id != self:
                raise UserError(_("Inconsistent existing MO2 FG picking link."))
            return existing

        plan = self.planning_line_id
        if (batch.state != "production_ok"
                or self.finalization_id.delivery_date != batch.delivery_date
                or self.finalization_id.slot != batch.slot
                or self not in self.finalization_id.line_ids
                or plan.planning_id.state != "published"
                or plan.planning_id.delivery_date != batch.delivery_date
                or plan.planning_id.slot != batch.slot
                or plan.product_id != product
                or mo.product_id != product
                or mo.ya_packing_batch_line_id
                or mo.state != "done"
                or batch.ya_store_delivery_ids
                or batch.ya_package_assembly_mo_ids):
            raise UserError(_(
                "MO2 FG requires DONE native MO2 and an unshipped "
                "Published Planning/Packing slot."
            ))
        if not isinstance(self.qty_mo2, int) or self.qty_mo2 <= 0:
            raise UserError(_("MO2 released Qty must be positive."))
        mo_qty = mo.product_uom_id._compute_quantity(
            mo.product_qty, product.uom_id, round=False,
        )
        if abs(mo_qty - self.qty_mo2) > 1e-7:
            raise UserError(_("Native MO2 planned output changed after final release."))

        # All MO2 native CDC material demand must be delivered before the
        # additional finished output enters Packing. Do not silently treat
        # an unvalidated or partial material transfer as fulfilled.
        materials = self.ya_mo2_material_picking_ids
        if len(materials) != 1 or materials.state != "done":
            raise UserError(_("Complete the native MO2 CDC transfer first."))
        for raw in materials.move_ids:
            if (raw.state != "done" or float_compare(
                    raw.quantity, raw.product_uom_qty,
                    precision_rounding=raw.product_uom.rounding) < 0):
                raise UserError(_("MO2 CDC move not fully fulfilled: %s.")
                                % raw.product_id.display_name)

        # Fase1 excludes WIP SKU 11076 unless the approved config changes.
        excluded = {
            code.strip() for code in (
                self.env["ir.config_parameter"].sudo().get_param(
                    "ya_finished_packing_transfer.exclude_sku_codes",
                    "11076",
                ) or ""
            ).split(",") if code.strip()
        }
        if product.default_code in excluded:
            raise UserError(_("WIP product excluded from PCK finished-goods: %s.")
                            % product.display_name)
        if product.categ_id.complete_name == "All / Produk Jadi / Paket":
            raise UserError(_("Kitchen MO2 cannot output a PCK-assembled Paket SKU."))
        if product.tracking != "none":
            raise UserError(_(
                "MO2 Finished Goods with lot/serial tracking require a "
                "separate approved traceability workflow."
            ))
        if "is_storable" in product._fields and not product.is_storable:
            raise UserError(_("Non-storable MO2 product cannot move to PCK."))

        company = mo.company_id
        kitchen = mo.picking_type_id.warehouse_id
        if (not kitchen or not kitchen.lot_stock_id
                or kitchen.company_id != company
                or mo.location_dest_id != kitchen.lot_stock_id
                or mo.location_src_id != mo.picking_type_id.default_location_src_id
                or kitchen.lot_stock_id.usage != "internal"):
            raise UserError(_("Native MO2 source kitchen/finished route mismatch."))
        expected = " ".join((
            "Dapur " + (plan.planning_id.workcenter_id.name or "")
        ).casefold().split())
        actual = " ".join((kitchen.name or "").casefold().split())
        if expected != actual or mo.bom_id != plan._capacity_bom():
            raise UserError(_("MO2 Published Planning kitchen BoM routing changed."))

        packing = self.env["stock.warehouse"].sudo().search([
            ("code", "=", "PCK"),
            ("company_id", "=", company.id),
        ])
        if len(packing) != 1 or packing == kitchen:
            raise UserError(_("Exactly one distinct Packing warehouse required."))
        dest = packing.lot_stock_id
        if not dest or dest.usage != "internal" or dest == kitchen.lot_stock_id:
            raise UserError(_("PCK stock location invalid."))
        operation = kitchen.int_type_id
        if (not operation or operation.code != "internal"
                or operation.company_id != company
                or operation.warehouse_id != kitchen):
            raise UserError(_("Kitchen native Internal Operation Type invalid."))

        # Do not rely on MO product_qty, expected output or historic MO1.
        # Only DONE native finished move(s) into this exact kitchen Stock count.
        finished = mo.move_finished_ids.filtered(
            lambda move: move.product_id == product and move.state == "done"
            and move.location_dest_id == kitchen.lot_stock_id
        )
        invalid = mo.move_finished_ids.filtered(
            lambda move: move.product_id == product
            and (move.state != "done"
                 or move.location_dest_id != kitchen.lot_stock_id)
        )
        if invalid or not finished:
            raise UserError(_("MO2 finished moves missing, incomplete or wrong route."))
        quantities = [
            move.product_uom._compute_quantity(
                move.quantity, product.uom_id, round=False,
            )
            for move in finished
        ]
        # A tracked/owned/package quant needs separate traceability handling.
        Quant = self.env["stock.quant"].sudo().with_company(company)
        exact = Quant.search([
            ("product_id", "=", product.id),
            ("location_id", "=", kitchen.lot_stock_id.id),
            ("company_id", "=", company.id),
            ("lot_id", "=", False),
            ("package_id", "=", False),
            ("owner_id", "=", False),
        ])
        physical = sum(exact.mapped("quantity"))
        reserved = sum(exact.mapped("reserved_quantity"))
        try:
            handoff = plan_mo2_finished_goods_handoff(
                self.qty_mo2, quantities, physical, reserved
            )
        except Mo2FinishedGoodsError as exc:
            raise UserError(_("MO2 FG source stock/output gate: %s") % exc) from exc

        Picking = self.env["stock.picking"].with_company(company)
        Move = self.env["stock.move"].with_company(company)
        origin = "YA-MO2-FG-%s" % mo.id
        if Picking.search_count([("origin", "=", origin)]):
            raise UserError(_("Unlinked/duplicate MO2 FG picking origin; reconcile."))

        vals = {
            "ya_mo2_fg_release_line_id": self.id,
            "picking_type_id": operation.id,
            "company_id": company.id,
            "location_id": kitchen.lot_stock_id.id,
            "location_dest_id": dest.id,
            "origin": origin,
        }
        if "note" in Picking._fields:
            vals["note"] = (
                "YA MO2 FG only: %s | %s %s | %s → PCK. "
                "Actual Qty %s from DONE MO2 finished stock moves. "
                "NOT MO1 and NOT planned production Qty. "
                "Picking is NOT VALIDATED; no stock has moved. "
                "Operator validation remains a separate QA gate."
            ) % (mo.name, batch.delivery_date.strftime("%Y-%b-%d"),
                 batch.slot, kitchen.display_name, handoff["transfer_qty"])
        picking = Picking.create(vals)
        move = Move.create({
            "picking_id": picking.id,
            "product_id": product.id,
            "product_uom": product.uom_id.id,
            "product_uom_qty": handoff["transfer_qty"],
            "location_id": kitchen.lot_stock_id.id,
            "location_dest_id": dest.id,
            "company_id": company.id,
        })
        # Leave draft: confirming can reserve native stock, which must not
        # happen at source-stage QA. A later guarded action will confirm
        # and validate in one atomic transaction after rechecking stock.
        if move.state != "draft" or picking.state != "draft":
            raise UserError(_("MO2 FG preparation unexpectedly reserved/posted stock."))
        # Demand equals DONE MO2 output. Actual picked Qty remains zero
        # until the separately tested validation/one-click handoff stage.
        return picking
