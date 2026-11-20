"""Ensure new products have a selectable base unit in YA Purchase UI."""

from odoo import api, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model_create_multi
    def create(self, vals_list):
        products = super().create(vals_list)
        Rule = self.env["ya.purchase.uom.rule"].sudo()
        for product in products:
            if not product.uom_id:
                continue
            label = product.uom_id.name
            existing = Rule.with_context(active_test=False).search([
                ("product_id", "=", product.id)
            ])
            if not any((r.purchase_label or "").casefold() == label.casefold()
                       for r in existing):
                Rule.create({"product_id": product.id, "purchase_label": label,
                             "factor": 1, "company_id": product.company_id.id or self.env.company.id})
        return products
