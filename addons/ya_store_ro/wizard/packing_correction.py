from odoo import api, fields, models, _
from odoo.exceptions import UserError


class YaPackingQtyCorrection(models.TransientModel):
    _name = 'ya.packing.qty.correction'
    _description = 'Packing - Last Correction of Confirmed RO Quantity'

    ro_id = fields.Many2one(
        'ya.store.ro', string='RO Confirmed', required=True,
        domain=[('state', '=', 'confirmed'), ('packing_batch_id', '=', False)],
    )
    line_id = fields.Many2one(
        'ya.store.ro.line', string='SKU', required=True,
        domain="[('ro_id', '=', ro_id)]",
    )
    old_qty = fields.Integer(related='line_id.qty_requested', readonly=True)
    new_qty = fields.Integer(string='Qty Pesan Baru', required=True)
    reason = fields.Text(string='Alasan Koreksi / Permintaan Toko', required=True)

    @api.onchange('ro_id')
    def _onchange_ro(self):
        self.line_id = False

    @api.onchange('line_id')
    def _onchange_line(self):
        if self.line_id:
            self.new_qty = self.line_id.qty_requested

    def action_apply(self):
        self.ensure_one()
        if not self.env.user.has_group('ya_store_ro.group_ya_packing_admin'):
            raise UserError(_('Only Packing Admin can revise Confirmed RO.'))
        if not self.ro_id or self.ro_id.state != 'confirmed':
            raise UserError(_('Choose a Confirmed RO.'))
        if self.ro_id.packing_batch_id or self.ro_id.production_ok:
            raise UserError(_('Pre Produksi / Produksi OK: corrections are closed.'))
        if self.line_id.ro_id != self.ro_id:
            raise UserError(_('The selected SKU does not belong to this RO.'))
        reason = (self.reason or '').strip()
        if not reason:
            raise UserError(_('Reason for correcting Qty is mandatory.'))
        if self.new_qty < 0:
            raise UserError(_('Qty cannot be negative.'))
        if self.line_id.qty_requested == self.new_qty:
            raise UserError(_('New Qty must differ from existing Qty.'))
        self.line_id.with_context(
            packing_qty_correction_reason=reason,
        ).write({'qty_requested': self.new_qty})
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'ya.store.ro',
            'res_id': self.ro_id.id,
            'view_mode': 'form', 'views': [(False, 'form')],
            'target': 'current',
        }
