"""PO discount modes, based on Odoo 19 native purchase.order.line.discount.

DO NOT alter native price_unit: YA Multi-UoM keeps it denominated in the
product's base UoM. Native discount flows into purchase tax and vendor bills.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from ..discount_math import effective_percent, validate_exclusive


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    ya_discount_mode = fields.Selection([
        ("none", "No Discount"),
        ("line", "Per Line"),
        ("global", "Global"),
    ], default="none", required=True, copy=False)
    ya_global_discount_type = fields.Selection([
        ("percent", "Percent (%)"),
        ("amount", "Amount (currency)"),
    ], default="percent", required=True, copy=False)
    ya_global_discount_value = fields.Monetary(
        string="Global Discount", currency_field="currency_id", default=0, copy=False)

    def _ya_gross_total(self):
        self.ensure_one()
        return sum(max(0.0, line.product_qty * line.price_unit)
                   for line in self.order_line if not line.display_type)

    @api.onchange("ya_discount_mode", "ya_global_discount_type", "ya_global_discount_value", "order_line")
    def _ya_onchange_discount(self):
        for order in self:
            if order.ya_discount_mode != "global":
                order.ya_global_discount_value = 0
            if order.ya_discount_mode != "line":
                for line in order.order_line:
                    line.ya_line_discount_value = 0
            for line in order.order_line.filtered(lambda l: not l.display_type):
                line._ya_apply_discount_percent()

    @api.constrains("ya_discount_mode", "ya_global_discount_value", "ya_global_discount_type", "order_line")
    def _ya_validate_discount(self):
        for order in self:
            try:
                validate_exclusive(order.ya_discount_mode, order.ya_global_discount_value,
                                   order.order_line.mapped("ya_line_discount_value"))
                if order.ya_discount_mode == "global":
                    effective_percent(order.ya_global_discount_type,
                                      order.ya_global_discount_value,
                                      order._ya_gross_total(), order._ya_gross_total())
            except ValueError as error:
                raise ValidationError(str(error)) from error


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    ya_line_discount_type = fields.Selection([
        ("percent", "Percent (%)"),
        ("amount", "Amount (currency)"),
    ], default="percent", required=True, copy=False)
    ya_line_discount_value = fields.Float(string="Line Discount", default=0, copy=False)

    def _ya_apply_discount_percent(self):
        for line in self:
            if line.display_type or not line.order_id:
                continue
            order = line.order_id
            mode = order.ya_discount_mode or "none"
            gross = max(0.0, line.product_qty * line.price_unit)
            try:
                if mode == "line":
                    percent = effective_percent(line.ya_line_discount_type,
                                                line.ya_line_discount_value, gross)
                elif mode == "global":
                    percent = effective_percent(order.ya_global_discount_type,
                                                order.ya_global_discount_value, gross,
                                                order._ya_gross_total())
                else:
                    percent = 0.0
            except ValueError as error:
                raise ValidationError(str(error)) from error
            line.discount = percent

    # Odoo 19 recomputes native discount alongside vendor price, so restore
    # the chosen YA rule after the built-in vendor-specific price calculation.
    @api.depends("product_qty", "product_uom_id", "company_id", "order_id.partner_id",
                 "order_id.ya_discount_mode", "order_id.ya_global_discount_type",
                 "order_id.ya_global_discount_value", "ya_line_discount_type",
                 "ya_line_discount_value")
    def _compute_price_unit_and_date_planned_and_name(self):
        super()._compute_price_unit_and_date_planned_and_name()
        self._ya_apply_discount_percent()

    @api.onchange("ya_line_discount_type", "ya_line_discount_value",
                  "product_qty", "price_unit", "ya_purchase_qty",
                  "ya_purchase_price", "ya_purchase_rule_id")
    def _ya_onchange_line_discount(self):
        self._ya_apply_discount_percent()

    @api.constrains("ya_line_discount_value", "ya_line_discount_type", "discount",
                    "product_qty", "price_unit", "order_id")
    def _ya_validate_line_discount(self):
        for line in self:
            if line.display_type or not line.order_id:
                continue
            try:
                validate_exclusive(line.order_id.ya_discount_mode,
                                   line.order_id.ya_global_discount_value,
                                   line.order_id.order_line.mapped("ya_line_discount_value"))
                gross = max(0.0, line.product_qty * line.price_unit)
                if line.order_id.ya_discount_mode == "line":
                    effective_percent(line.ya_line_discount_type,
                                      line.ya_line_discount_value, gross)
            except ValueError as error:
                raise ValidationError(str(error)) from error
