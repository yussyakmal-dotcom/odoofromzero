"""PO conversion using base UoM in Odoo's native stock and accounting flows.

The purchase-facing fields are entered in whole units. The native PO line
continues to carry base quantity and base-unit price so purchase_stock can
create receipts without a global UoM conversion factor.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    ya_purchase_rule_id = fields.Many2one(
        "ya.purchase.uom.rule", string="Satuan Pembelian YA",
        domain="[('product_id', '=', product_id), ('active', '=', True)]",
        copy=False,
    )
    ya_purchase_qty = fields.Integer(
        string="Qty Pembelian YA", default=1, copy=False,
    )
    ya_purchase_price = fields.Float(
        string="Harga/Satuan Pembelian YA", digits="Product Price", copy=False,
    )
    ya_purchase_label = fields.Char(
        string="Label Pembelian", related="ya_purchase_rule_id.purchase_label",
        readonly=True,
    )

    @api.onchange("product_id")
    def _ya_reset_purchase_rule_on_product(self):
        for line in self:
            if not line.product_id:
                line.ya_purchase_rule_id = False
                continue
            if line.ya_purchase_rule_id and line.ya_purchase_rule_id.product_id == line.product_id:
                continue
            base = line.product_id.uom_id
            rule = self.env["ya.purchase.uom.rule"].search([
                ("product_id", "=", line.product_id.id),
                ("purchase_label", "=", base.name),
                ("factor", "=", 1), ("active", "=", True),
            ], limit=1)
            line.ya_purchase_rule_id = rule
            if rule:
                line.ya_purchase_qty = int(line.product_qty or 1)
                line.ya_purchase_price = line.price_unit

    @api.onchange("ya_purchase_rule_id")
    def _ya_reprice_purchase_unit(self):
        for line in self:
            if line.ya_purchase_rule_id:
                # Preserve the current base-unit price when switching units.
                line.ya_purchase_price = line.price_unit * line.ya_purchase_rule_id.factor

    @api.onchange("ya_purchase_rule_id", "ya_purchase_qty", "ya_purchase_price")
    def _ya_convert_purchase_values(self):
        for line in self:
            rule = line.ya_purchase_rule_id
            if not rule:
                continue
            if rule.product_id != line.product_id:
                raise ValidationError(_("Purchase conversion rule must match the SKU."))
            base_qty = rule.to_base_quantity(line.ya_purchase_qty)
            line.product_uom_id = line.product_id.uom_id
            line.product_qty = base_qty
            line.price_unit = rule.price_per_base_unit(line.ya_purchase_price)

    @api.constrains("ya_purchase_rule_id", "ya_purchase_qty", "ya_purchase_price",
                    "product_id", "product_uom_id", "product_qty", "price_unit")
    def _ya_check_purchase_conversion(self):
        for line in self:
            rule = line.ya_purchase_rule_id
            if not rule:
                continue
            if not rule.active or rule.product_id != line.product_id:
                raise ValidationError(_("Purchase rule is inactive or belongs to another SKU."))
            if line.product_uom_id != line.product_id.uom_id:
                raise ValidationError(_("Native PO UoM must be the product's base unit."))
            expected_qty = rule.to_base_quantity(line.ya_purchase_qty)
            if float_compare(line.product_qty, expected_qty, precision_rounding=0.0000001):
                raise ValidationError(_("PO base quantity does not match the YA purchase conversion."))
            expected_price = rule.price_per_base_unit(line.ya_purchase_price)
            if float_compare(line.price_unit, expected_price, precision_rounding=0.000001):
                raise ValidationError(_("PO base price does not match the YA purchase conversion."))
