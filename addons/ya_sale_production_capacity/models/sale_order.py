"""Fase 2 Stage 1: quotation remains native; YA schedule belongs to SO confirmation.

Capacity reservation is not implemented: YA SO confirmation MUST fail closed.
Standard Sales / Quotations are unaffected.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.addons.ya_store_ro.models.date_labels import format_ymondd


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    ya_is_capacity_so = fields.Boolean(
        string='YA Production Capacity SO', default=False, copy=False,
        readonly=True, index=True,
    )
    ya_delivery_date = fields.Date(
        string='YA Tanggal Kirim', copy=False, index=True,
    )
    ya_delivery_date_label = fields.Char(
        string='YA Tanggal Kirim (YYYY-Mon-DD)',
        compute='_compute_ya_delivery_date_label', readonly=True,
    )
    ya_slot = fields.Selection(
        [('S1', 'S1 - 05.00 WIB'), ('S2', 'S2 - 09.00 WIB'),
         ('S3', 'S3 - 11.00 WIB')],
        string='YA Slot Kirim', copy=False, index=True,
    )

    @api.depends('ya_delivery_date')
    def _compute_ya_delivery_date_label(self):
        for order in self:
            order.ya_delivery_date_label = format_ymondd(order.ya_delivery_date)

    @api.model_create_multi
    def create(self, vals_list):
        # Quotation can be created without any YA schedule.
        if self.env.context.get('default_ya_is_capacity_so'):
            for vals in vals_list:
                vals['ya_is_capacity_so'] = True
        return super().create(vals_list)

    def write(self, vals):
        # The classification is immutable once the quotation has been created.
        if 'ya_is_capacity_so' in vals and any(
            order.ya_is_capacity_so != bool(vals['ya_is_capacity_so'])
            for order in self
        ):
            raise UserError(_('Jenis Sales Order YA tidak dapat diubah setelah dibuat.'))
        if {'ya_delivery_date', 'ya_slot'} & set(vals) and any(
            order.ya_is_capacity_so and order.state not in ('draft', 'sent')
            for order in self
        ):
            raise UserError(_('Jadwal Sales Order YA tidak boleh diubah setelah Confirm.'))
        # Do not validate date/slot on draft quotation, send, or standard SO.
        return super().write(vals)

    def action_confirm(self):
        ya_orders = self.filtered('ya_is_capacity_so')
        if not ya_orders:
            return super().action_confirm()
        if len(self) != 1:
            raise UserError(_(
                'Konfirmasi Custom SO YA dilakukan satu per satu melalui form.'
            ))
        self.ensure_one()
        if self.state not in ('draft', 'sent'):
            raise UserError(_('Hanya penawaran Draft/Sent yang dapat dikonfirmasi.'))
        # Open a wizard for date and slot; it will not confirm while the
        # capacity reservation engine is unfinished.
        return {
            'type': 'ir.actions.act_window',
            'name': _('YA Jadwal Kirim — Konfirmasi Sales Order'),
            'res_model': 'ya.sale.capacity.confirm.wizard',
            'view_mode': 'form',
            'views': [(self.env.ref(
                'ya_sale_production_capacity.view_ya_sale_capacity_confirm_wizard_form'
            ).id, 'form')],
            'target': 'new',
            'context': {
                'default_order_id': self.id,
                'default_delivery_date': self.ya_delivery_date or False,
                'default_slot': self.ya_slot or False,
            },
        }
