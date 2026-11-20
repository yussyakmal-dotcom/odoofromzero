"""Editable physical receipt unit on the existing stock move row."""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class StockMove(models.Model):
    _inherit = "stock.move"

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

    @api.constrains("ya_receipt_rule_id", "product_id", "ya_receipt_qty_units")
    def _check_ya_physical_receipt(self):
        for move in self:
            if move.ya_receipt_qty_units < 0:
                raise ValidationError(_("Received physical quantity cannot be negative."))
            if move.ya_receipt_rule_id and move.ya_receipt_rule_id.product_id != move.product_id:
                raise ValidationError(_("The selected physical unit belongs to another SKU."))
