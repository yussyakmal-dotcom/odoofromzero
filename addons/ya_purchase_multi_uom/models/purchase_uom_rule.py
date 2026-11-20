"""Per-product purchase unit rules with editable Odoo master data."""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class YaPurchaseUomRule(models.Model):
    _name = "ya.purchase.uom.rule"
    _description = "YA SKU Purchase UoM Conversion Rule"
    _order = "product_id, purchase_label"
    _rec_name = "purchase_label"

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

    @api.depends("purchase_label", "factor", "base_uom_id")
    def _compute_display_name(self):
        for rule in self:
            if rule.purchase_label and rule.base_uom_id:
                rule.display_name = "%s (1 = %s %s)" % (
                    rule.purchase_label, rule.factor, rule.base_uom_id.name
                )
            else:
                rule.display_name = rule.purchase_label or _("New purchase unit")

    def _ya_assert_unreferenced(self):
        used = self.env["purchase.order.line"].sudo().search([
            ("ya_purchase_rule_id", "in", self.ids)
        ], limit=1)
        if used:
            raise ValidationError(_(
                "This purchase unit is already referenced by a PO. "
                "Archive it and create a new rule instead of changing its identity or factor."
            ))

    def write(self, vals):
        if {"product_id", "purchase_label", "factor"} & set(vals):
            self._ya_assert_unreferenced()
        return super().write(vals)

    def unlink(self):
        self._ya_assert_unreferenced()
        return super().unlink()

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
