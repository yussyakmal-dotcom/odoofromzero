"""Server-side whole-number policy on user-entered operational quantities.

Do not change Odoo Float storage, price precision or UoM conversion.
The POS browser editor and form rendering require separate UI integration.
"""

import math

from odoo import api, models, _
from odoo.exceptions import ValidationError


def check_whole_quantity(quantity, label):
    """Accept zero and signed integer quantities (e.g. POS refunds).

    Float computations may have tiny binary errors, so tolerate only 1e-9.
    Reject genuine fractions instead of silently rounding them.
    """
    if not math.isfinite(quantity) or not math.isclose(
        quantity, round(quantity), rel_tol=0, abs_tol=1e-9
    ):
        raise ValidationError(
            _("YA requires a whole-number quantity for %(field)s (received: %(value)s).")
            % {"field": label, "value": quantity}
        )


class PurchaseOrderLine(models.Model):
    _inherit = "purchase.order.line"

    @api.constrains("product_qty")
    def _ya_check_integer_qty(self):
        for line in self:
            check_whole_quantity(line.product_qty, "PO Quantity")


class StockMove(models.Model):
    _inherit = "stock.move"

    @api.constrains("product_uom_qty")
    def _ya_check_integer_demand(self):
        for move in self:
            check_whole_quantity(move.product_uom_qty, "Stock Demand")


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    @api.constrains("quantity")
    def _ya_check_integer_done(self):
        for line in self:
            check_whole_quantity(line.quantity, "Stock Done Quantity")


class StockQuant(models.Model):
    _inherit = "stock.quant"

    @api.constrains("inventory_quantity")
    def _ya_check_integer_count(self):
        for quant in self:
            check_whole_quantity(quant.inventory_quantity, "Inventory Count")


class StockScrap(models.Model):
    _inherit = "stock.scrap"

    @api.constrains("scrap_qty")
    def _ya_check_integer_scrap(self):
        for scrap in self:
            check_whole_quantity(scrap.scrap_qty, "Scrap Quantity")


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.constrains("product_uom_qty")
    def _ya_check_integer_sale(self):
        for line in self:
            check_whole_quantity(line.product_uom_qty, "Sales Quantity")


class PosOrderLine(models.Model):
    _inherit = "pos.order.line"

    @api.constrains("qty")
    def _ya_check_integer_pos(self):
        for line in self:
            check_whole_quantity(line.qty, "POS Quantity")


class MrpProduction(models.Model):
    _inherit = "mrp.production"

    @api.constrains("product_qty")
    def _ya_check_integer_mo(self):
        for production in self:
            check_whole_quantity(production.product_qty, "Manufacturing Quantity")


class MrpBomLine(models.Model):
    _inherit = "mrp.bom.line"

    @api.constrains("product_qty")
    def _ya_check_integer_bom(self):
        for line in self:
            check_whole_quantity(line.product_qty, "BoM Component Quantity")
