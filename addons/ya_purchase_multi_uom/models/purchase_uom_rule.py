"""Per-product purchase unit rules; no PO/stock overrides in this phase."""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class YaPurchaseUomRule(models.Model):
    _name = "ya.purchase.uom.rule"
    _description = "YA SKU Purchase UoM Conversion Rule"
    _order = "product_id, purchase_label"

    product_id = fields.Many2one("product.product", required=True, index=True, ondelete="cascade")
    purchase_label = fields.Char(required=True, index=True)
    base_uom_id = fields.Many2one(
        "uom.uom", related="product_id.uom_id", readonly=True, store=True
    )
    factor = fields.Integer(
        required=True, default=1,
        help="Number of whole base units in one purchase unit for this SKU.",
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", default=lambda self: self.env.company)

    @api.constrains("factor", "purchase_label", "product_id")
    def _check_rule(self):
        for rule in self:
            if rule.factor < 1:
                raise ValidationError(_("Conversion factor must be a positive integer."))
            label = (rule.purchase_label or "").strip()
            if not label:
                raise ValidationError(_("Purchase unit label is required."))
            duplicates = self.with_context(active_test=False).search([
                ("product_id", "=", rule.product_id.id),
                ("id", "!=", rule.id),
            ])
            if any((existing.purchase_label or "").strip().casefold() == label.casefold()
                   for existing in duplicates):
                raise ValidationError(_("Duplicate purchase unit for this SKU."))

    def to_base_quantity(self, purchase_qty):
        """Return integer base units. Fractional purchase quantities are forbidden."""
        from decimal import Decimal, InvalidOperation

        self.ensure_one()
        try:
            qty = Decimal(str(purchase_qty))
        except (InvalidOperation, TypeError):
            raise ValidationError(_("Invalid purchase quantity."))
        if not qty.is_finite() or qty <= 0 or qty != qty.to_integral_value():
            raise ValidationError(_("Purchase quantity must be a positive whole number."))
        return int(qty) * self.factor

    def price_per_base_unit(self, purchase_unit_price):
        """Return price in product's base unit; does not write prices or costs."""
        from decimal import Decimal, InvalidOperation

        self.ensure_one()
        try:
            price = Decimal(str(purchase_unit_price))
        except (InvalidOperation, TypeError):
            raise ValidationError(_("Invalid purchase unit price."))
        if not price.is_finite() or price < 0:
            raise ValidationError(_("Purchase price must be nonnegative."))
        return float(price / Decimal(self.factor))
