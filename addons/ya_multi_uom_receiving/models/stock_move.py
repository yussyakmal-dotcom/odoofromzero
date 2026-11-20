"""Editable physical receipt unit on the existing stock move row."""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class StockMove(models.Model):
    _inherit = "stock.move"

    ya_demand_display = fields.Char(
        string="Demand", compute="_compute_ya_demand_display",
    )

    @api.depends(
        "purchase_line_id.ya_purchase_qty",
        "purchase_line_id.ya_purchase_rule_id.purchase_label",
        "product_uom_qty", "product_uom",
    )
    def _compute_ya_demand_display(self):
        for move in self:
            line = move.purchase_line_id
            if line and line.ya_purchase_rule_id:
                qty = line.ya_purchase_qty
                label = line.ya_purchase_rule_id.purchase_label
            else:
                qty = move.product_uom_qty
                label = move.product_uom.name or ""
            qty_text = ("%g" % qty) if qty is not False else "0"
            move.ya_demand_display = "%s %s" % (qty_text, label)

    ya_receipt_rule_id = fields.Many2one(
        "ya.purchase.uom.rule", string="Unit", compute="_compute_ya_receipt_rule_id",
        store=True, readonly=False, copy=False,
    )
    ya_receipt_qty_units = fields.Integer(string="Quantity", default=0, copy=False)
    ya_received_unit_label = fields.Char(string="Received Physical Unit", copy=False, readonly=True)
    ya_received_unit_qty = fields.Integer(string="Received Physical Qty", copy=False, readonly=True)

    @api.depends("purchase_line_id.ya_purchase_rule_id", "product_id")
    def _compute_ya_receipt_rule_id(self):
        Rule = self.env["ya.purchase.uom.rule"]
        for move in self:
            rule = move.purchase_line_id.ya_purchase_rule_id
            if not rule or rule.product_id != move.product_id:
                rule = Rule.search([
                    ("product_id", "=", move.product_id.id),
                    ("factor", "=", 1), ("active", "=", True),
                ], limit=1) if move.product_id else Rule.browse()
            move.ya_receipt_rule_id = rule

    @api.onchange("ya_receipt_qty_units", "ya_receipt_rule_id")
    def _onchange_ya_receipt_quantity_limit(self):
        """Warn as soon as an Operations quantity/unit is edited in the UI."""
        for move in self:
            if not move.purchase_line_id or not move.ya_receipt_rule_id:
                continue
            rule = move.ya_receipt_rule_id
            if rule.product_id != move.product_id:
                continue
            received_base = move.ya_receipt_qty_units * rule.factor
            if received_base > move.product_uom_qty:
                return {
                    "warning": {
                        "title": _("Received quantity exceeds demand"),
                        "message": _(
                            "Received %(quantity)s %(unit)s exceeds the order demand "
                            "of %(demand)s. Reduce the quantity or select another unit. "
                            "The receipt cannot be validated while it exceeds demand.",
                            quantity=move.ya_receipt_qty_units,
                            unit=rule.purchase_label,
                            demand=move.ya_demand_display,
                        ),
                    },
                }
        return {}

    @api.constrains("ya_receipt_rule_id", "product_id", "ya_receipt_qty_units")
    def _check_ya_physical_receipt(self):
        for move in self:
            if move.ya_receipt_qty_units < 0:
                raise ValidationError(_("Received physical quantity cannot be negative."))
            if move.ya_receipt_rule_id and move.ya_receipt_rule_id.product_id != move.product_id:
                raise ValidationError(_("The selected physical unit belongs to another SKU."))
