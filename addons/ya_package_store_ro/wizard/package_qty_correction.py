"""Controlled Qty correction by Packing, before immutable Pre Produksi."""
from odoo import fields, models, _
from odoo.exceptions import UserError


class YaPackageROQtyCorrection(models.TransientModel):
    _name = "ya.package.ro.qty.correction"
    _description = "Packing - Koreksi Qty RO Paket Confirmed"

    ro_id = fields.Many2one(
        "ya.package.store.ro", required=True, readonly=True,
        domain=[("state", "=", "confirmed")])
    line_id = fields.Many2one(
        "ya.package.store.ro.line", required=True,
        domain="[('ro_id', '=', ro_id)]")
    old_qty = fields.Integer(related="line_id.qty_requested", readonly=True)
    new_qty = fields.Integer(string="Qty Baru", required=True)
    reason = fields.Text(string="Alasan Koreksi / Permintaan Toko", required=True)

    def action_apply(self):
        self.ensure_one()
        if not self.env.user.has_group("ya_store_ro.group_ya_packing_admin"):
            raise UserError(_("Only Packing Admin may correct Confirmed Paket Qty."))
        if not self.ro_id or self.ro_id.state != "confirmed":
            raise UserError(_("Choose a Confirmed Paket RO."))
        if self.line_id.ro_id != self.ro_id:
            raise UserError(_("Paket SKU does not belong to this RO."))
        reason = (self.reason or "").strip()
        if not reason:
            raise UserError(_("Correction reason is required."))
        if self.new_qty < 0:
            raise UserError(_("Qty cannot be negative."))
        if self.new_qty == self.old_qty:
            raise UserError(_("Qty has not changed."))
        self.line_id.with_context(
            ya_package_packing_qty_correction_reason=reason,
        ).write({"qty_requested": self.new_qty})
        return {
            "type": "ir.actions.act_window",
            "res_model": "ya.package.store.ro", "res_id": self.ro_id.id,
            "view_mode": "form", "views": [(False, "form")], "target": "current",
        }
