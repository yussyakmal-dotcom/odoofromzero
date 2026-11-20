"""Display-only invoice units. Never change stored accounting amounts."""
from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    ya_report_purchase_unit = fields.Boolean(
        compute="_compute_ya_purchase_print_fields",
    )
    ya_report_qty = fields.Float(
        compute="_compute_ya_purchase_print_fields",
    )
    ya_report_unit = fields.Char(
        compute="_compute_ya_purchase_print_fields",
    )
    ya_report_unit_price = fields.Float(
        compute="_compute_ya_purchase_print_fields",
        digits="Product Price",
    )

    @api.depends("purchase_line_id.ya_purchase_rule_id", "quantity",
                 "price_unit", "product_uom_id", "product_id")
    def _compute_ya_purchase_print_fields(self):
        for line in self:
            rule = line.purchase_line_id.ya_purchase_rule_id
            factor = rule.factor if rule else 0
            base_qty = line.quantity
            physical_qty = (base_qty / factor) if factor else 0
            # Never show a fractional physical unit: keep base units instead.
            valid = bool(
                line.move_id.move_type == "in_invoice"
                and rule and rule.product_id == line.product_id
                and factor > 0 and base_qty >= 0
                and abs(physical_qty - round(physical_qty)) < 0.0000001
            )
            line.ya_report_purchase_unit = valid
            line.ya_report_qty = round(physical_qty) if valid else base_qty
            line.ya_report_unit = (
                rule.purchase_label if valid else line.product_uom_id.name
            ) or ""
            line.ya_report_unit_price = line.price_unit * factor if valid else line.price_unit
