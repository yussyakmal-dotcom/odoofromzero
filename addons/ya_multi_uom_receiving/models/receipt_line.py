"""Receipt entry in a physical purchase unit; stored independently from stock move lines."""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

from ..conversion_math import to_base_quantity


class YaReceiptUnitLine(models.Model):
    _name = "ya.receipt.unit.line"
    _description = "YA Physical Receipt Unit Line"
    _order = "move_id, id"

    picking_id = fields.Many2one(
        "stock.picking", required=True, index=True, ondelete="cascade",
    )
    move_id = fields.Many2one(
        "stock.move", required=True, index=True, ondelete="cascade",
        string="Baris Permintaan",
    )
    product_id = fields.Many2one(
        "product.product", related="move_id.product_id", store=True,
        readonly=True, string="Produk",
    )
    rule_id = fields.Many2one(
        "ya.purchase.uom.rule", required=True, string="Satuan Fisik",
        ondelete="restrict",
    )
    quantity_units = fields.Integer(
        required=True, default=1, string="Jumlah Fisik",
    )
    factor_snapshot = fields.Integer(
        readonly=True, required=True, default=1,
        string="Faktor ke Dasar",
    )
    unit_label_snapshot = fields.Char(
        readonly=True, string="Label Satuan",
    )
    base_quantity = fields.Integer(
        compute="_compute_base_quantity", store=True,
        string="Kuantitas Dasar",
    )

    @api.depends("quantity_units", "factor_snapshot")
    def _compute_base_quantity(self):
        for line in self:
            if line.quantity_units > 0 and line.factor_snapshot > 0:
                line.base_quantity = to_base_quantity(
                    line.quantity_units, line.factor_snapshot
                )
            else:
                line.base_quantity = 0

    @api.onchange("move_id")
    def _onchange_move_id(self):
        self.rule_id = False

    @api.onchange("rule_id")
    def _onchange_rule_id(self):
        if self.rule_id:
            self.factor_snapshot = self.rule_id.factor
            self.unit_label_snapshot = self.rule_id.purchase_label

    @api.model_create_multi
    def create(self, vals_list):
        Rule = self.env["ya.purchase.uom.rule"]
        for vals in vals_list:
            rule = Rule.browse(vals.get("rule_id")).exists()
            if rule:
                vals["factor_snapshot"] = rule.factor
                vals["unit_label_snapshot"] = rule.purchase_label
        return super().create(vals_list)

    def write(self, vals):
        if "rule_id" in vals:
            rule = self.env["ya.purchase.uom.rule"].browse(vals["rule_id"]).exists()
            if rule:
                vals = dict(vals, factor_snapshot=rule.factor,
                            unit_label_snapshot=rule.purchase_label)
        elif {"factor_snapshot", "unit_label_snapshot"} & set(vals):
            raise ValidationError(_("Unit snapshots cannot be changed manually."))
        return super().write(vals)

    @api.constrains("picking_id", "move_id", "rule_id", "quantity_units",
                    "factor_snapshot")
    def _check_receipt_entry(self):
        for line in self:
            if line.picking_id.state in ("done", "cancel"):
                raise ValidationError(_("Finished receipts cannot be edited."))
            if line.picking_id.picking_type_code != "incoming":
                raise ValidationError(_("Physical purchase units apply to incoming receipts only."))
            if line.move_id.picking_id != line.picking_id:
                raise ValidationError(_("The move must belong to the selected receipt."))
            if line.rule_id.product_id != line.move_id.product_id:
                raise ValidationError(_("The purchase unit must belong to this SKU."))
            if line.quantity_units < 1 or line.factor_snapshot < 1:
                raise ValidationError(_("Quantity and factor must be positive integers."))

    def unlink(self):
        if any(x.picking_id.state in ("done", "cancel") for x in self):
            raise ValidationError(_("Cannot delete entries from a completed receipt."))
        return super().unlink()
