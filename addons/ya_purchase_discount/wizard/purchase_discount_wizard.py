"""Sales-style discount popup for YA Purchase Orders, test database first."""

from odoo import fields, models, _
from odoo.exceptions import UserError, ValidationError


class YaPurchaseDiscountWizard(models.TransientModel):
    _name = "ya.purchase.discount.wizard"
    _description = "Purchase Discount Wizard"

    order_id = fields.Many2one("purchase.order", required=True,
                               default=lambda self: self.env.context.get("active_id"))
    currency_id = fields.Many2one(related="order_id.currency_id")
    discount_type = fields.Selection([
        ("all_lines", "On All Order Lines (%)"),
        ("one_line_percent", "One Order Line (%)"),
        ("one_line_amount", "One Order Line (Rp)"),
        ("global_percent", "Global Discount (%)"),
        ("global_amount", "Fixed Amount (Rp)"),
    ], required=True, default="all_lines")
    discount_percentage = fields.Float(string="Discount (%)", digits=(16, 2))
    discount_amount = fields.Monetary(string="Discount (Rp)", currency_field="currency_id")
    line_id = fields.Many2one("purchase.order.line", string="Order Line",
                              domain="[('order_id', '=', order_id), ('display_type', '=', False)]")

    def action_apply_discount(self):
        self.ensure_one()
        order = self.order_id
        if order.state not in ("draft", "sent"):
            raise UserError(_("Discounts can only be changed on an RFQ."))
        typ = self.discount_type
        use_amount = typ in ("one_line_amount", "global_amount")
        value = self.discount_amount if use_amount else self.discount_percentage
        if value < 0 or (not use_amount and value > 100):
            raise ValidationError(_("Discount must be between 0 and 100 percent, or a nonnegative amount."))
        lines = order.order_line.filtered(lambda l: not l.display_type)
        if typ.startswith("one_line") and (not self.line_id or self.line_id not in lines):
            raise ValidationError(_("Select a product line from this PO."))

        # Reset the previous mode first. This also avoids the mixed-mode
        # constraint firing during the transition between line and global.
        if lines:
            lines.write({"ya_line_discount_value": 0})
        order.write({"ya_global_discount_value": 0, "ya_discount_mode": "none"})

        if typ in ("global_percent", "global_amount"):
            order.write({
                "ya_discount_mode": "global",
                "ya_global_discount_type": "amount" if use_amount else "percent",
                "ya_global_discount_value": value,
            })
        else:
            order.write({"ya_discount_mode": "line"})
            target = self.line_id if typ.startswith("one_line") else lines
            if target:
                target.write({
                    "ya_line_discount_type": "amount" if use_amount else "percent",
                    "ya_line_discount_value": value,
                })
        return {"type": "ir.actions.act_window_close"}
