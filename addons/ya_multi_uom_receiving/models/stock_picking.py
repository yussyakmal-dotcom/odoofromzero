"""Apply physical receiving quantities to stock moves explicitly before Validate."""
from collections import defaultdict

from odoo import fields, models, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class StockPicking(models.Model):
    _inherit = "stock.picking"

    ya_receipt_unit_line_ids = fields.One2many(
        "ya.receipt.unit.line", "picking_id",
        string="Penerimaan Satuan Fisik YA",
        copy=False,
    )

    def _ya_is_purchase_receipt(self):
        self.ensure_one()
        return (
            self.picking_type_code == "incoming"
            and any(move.purchase_line_id for move in self.move_ids)
        )

    def _ya_receipt_totals(self):
        self.ensure_one()
        totals = defaultdict(int)
        if not self.ya_receipt_unit_line_ids:
            raise UserError(_("Fill the physical receiving lines before validation."))
        for line in self.ya_receipt_unit_line_ids:
            if line.move_id not in self.move_ids:
                raise UserError(_("Physical entry refers to another receipt."))
            if line.rule_id.product_id != line.move_id.product_id:
                raise UserError(_("Unit rule does not belong to the selected SKU."))
            if line.quantity_units <= 0 or line.factor_snapshot <= 0:
                raise UserError(_("Physical quantities must be positive integers."))
            totals[line.move_id.id] += line.base_quantity
        for move in self.move_ids:
            if move.state in ("done", "cancel"):
                continue
            if move.product_uom != move.product_id.uom_id:
                raise UserError(_(
                    "A stock move does not use the SKU's base UoM; review before applying."
                ))
            base = totals[move.id]
            if base > move.product_uom_qty:
                raise UserError(_(
                    "Receipt of %(sku)s exceeds ordered base units (%(received)s > %(ordered)s)."
                ) % {
                    "sku": move.product_id.default_code or move.product_id.display_name,
                    "received": base, "ordered": move.product_uom_qty,
                })
        return totals

    def action_ya_apply_receipt_units(self):
        """Explicitly transfer physical entries into editable stock.move.quantity."""
        for picking in self:
            if not picking._ya_is_purchase_receipt():
                raise UserError(_("This action is only for incoming purchase receipts."))
            if picking.state in ("done", "cancel"):
                raise UserError(_("This receipt is already finished."))
            totals = picking._ya_receipt_totals()
            for move in picking.move_ids:
                if move.state in ("done", "cancel"):
                    continue
                qty = totals[move.id]
                # Odoo 19's editable computed quantity uses its inverse to
                # synchronize detailed move lines. Do not create extra stock moves.
                move.write({"quantity": float(qty)})
                if float_compare(move.quantity, float(qty), precision_rounding=move.product_uom.rounding):
                    raise UserError(_(
                        "Stock quantity did not synchronize. Nothing was committed."
                    ))
                move.write({"picked": bool(qty)})
                if move.move_line_ids:
                    move.move_line_ids.write({"picked": bool(qty)})
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Penerimaan YA"),
                "message": _("Physical units converted to base quantities. Review before Validate."),
                "type": "success",
                "sticky": False,
            },
        }

    def button_validate(self):
        for picking in self:
            if not picking._ya_is_purchase_receipt() or picking.state in ("done", "cancel"):
                continue
            if picking.picking_type_id.create_backorder != "never":
                raise UserError(_(
                    "Set the receipt operation type's backorder policy to Never "
                    "before using YA physical receiving."
                ))
            totals = picking._ya_receipt_totals()
            for move in picking.move_ids:
                if move.state in ("done", "cancel"):
                    continue
                expected = totals[move.id]
                if float_compare(move.quantity, expected,
                                 precision_rounding=move.product_uom.rounding):
                    raise UserError(_(
                        "Apply physical receiving units before validating; "
                        "stock quantity differs from physical entry."
                    ))
        return super().button_validate()
