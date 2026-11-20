"""Receive in the purchase unit directly on the standard Operations rows."""
from odoo import models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _ya_is_purchase_receipt(self):
        self.ensure_one()
        return (
            self.picking_type_code == "incoming"
            and any(move.purchase_line_id for move in self.move_ids)
        )

    def _ya_apply_physical_quantities(self):
        """Convert each existing Operations row; never require a second list."""
        self.ensure_one()
        for move in self.move_ids:
            if move.state in ("done", "cancel"):
                continue
            if not move.purchase_line_id:
                raise UserError(_("A receipt line has no PO line. Review this receipt."))
            rule = move.ya_receipt_rule_id
            if not rule or not rule.active or rule.product_id != move.product_id:
                raise UserError(_("Choose a valid physical unit for every receipt line."))
            if move.product_uom != move.product_id.uom_id:
                raise UserError(_("Stock move UoM must match the SKU base unit."))
            if move.ya_receipt_qty_units < 0 or rule.factor < 1:
                raise UserError(_("Received quantity must be a nonnegative integer."))
            received_base = move.ya_receipt_qty_units * rule.factor
            if float_compare(
                received_base, move.product_uom_qty,
                precision_rounding=move.product_uom.rounding,
            ) > 0:
                raise UserError(_(
                    "Received quantity exceeds demand for %(sku)s: %(received)s > %(demand)s."
                ) % {
                    "sku": move.product_id.default_code or move.product_id.display_name,
                    "received": received_base,
                    "demand": move.product_uom_qty,
                })
            move.write({
                "quantity": float(received_base),
                "ya_received_unit_label": rule.purchase_label,
                "ya_received_unit_qty": move.ya_receipt_qty_units,
            })
            if float_compare(
                move.quantity, received_base,
                precision_rounding=move.product_uom.rounding,
            ):
                raise UserError(_("Stock quantity did not synchronize; validation cancelled."))
            move.write({"picked": bool(received_base)})
            if move.move_line_ids:
                move.move_line_ids.write({"picked": bool(received_base)})

    def button_validate(self):
        for picking in self:
            if not picking._ya_is_purchase_receipt() or picking.state in ("done", "cancel"):
                continue
            if picking.picking_type_id.create_backorder != "never":
                raise UserError(_(
                    "Set the incoming operation type backorder policy to Never "
                    "before validating YA multi-unit receipts."
                ))
            picking._ya_apply_physical_quantities()
        return super().button_validate()
