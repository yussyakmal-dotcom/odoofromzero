"""Fase 2 / Stage 1: YA capacity SO classification and mandatory Published slot.

Deliberately does NOT reserve capacity, create MO2, or change Packing allocations.
Custom SO confirmation fails closed until the approved reservation engine exists.
Native Sales Orders with ya_is_capacity_so=False remain unchanged.
"""
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
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
        compute='_compute_ya_delivery_date_label',
        readonly=True,
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

    def _ya_validate_published_schedule(self):
        """Validate live Published Planning at create/edit, never trust view alone."""
        Planning = self.env['ya.production.planning']
        for order in self.filtered('ya_is_capacity_so'):
            if not order.ya_delivery_date or not order.ya_slot:
                raise ValidationError(_(
                    'Custom YA Sales Order wajib memiliki Tanggal Kirim dan '
                    'Slot Kirim dari Published Planning.'
                ))
            exists = Planning.search_count([
                ('delivery_date', '=', order.ya_delivery_date),
                ('slot', '=', order.ya_slot),
                ('state', '=', 'published'),
            ])
            if not exists:
                raise ValidationError(_(
                    'Belum ada Published Production Planning untuk tanggal '
                    '%(date)s, slot %(slot)s. Hubungi Admin Produksi.'
                ) % {'date': order.ya_delivery_date, 'slot': order.ya_slot})

    @api.model_create_multi
    def create(self, vals_list):
        # The dedicated YA action supplies this context default. Even a caller
        # omitting the boolean from vals cannot bypass the dedicated entry.
        if self.env.context.get('default_ya_is_capacity_so'):
            for vals in vals_list:
                vals['ya_is_capacity_so'] = True
        orders = super().create(vals_list)
        orders._ya_validate_published_schedule()
        return orders

    def write(self, vals):
        # Classification is set on creation; changing it would bypass the
        # separate standard Sales vs YA Production Capacity workflows.
        if 'ya_is_capacity_so' in vals:
            if any(o.ya_is_capacity_so != bool(vals['ya_is_capacity_so'])
                   for o in self):
                raise UserError(_(
                    'Jenis Sales Order YA tidak dapat diubah setelah dibuat.'
                ))
        result = super().write(vals)
        self._ya_validate_published_schedule()
        return result

    def action_confirm(self):
        if any(self.mapped('ya_is_capacity_so')):
            # Never confirm a YA order without the capacity reservation engine:
            # it would silently promise goods without locking planning Max.
            self.filtered('ya_is_capacity_so')._ya_validate_published_schedule()
            raise UserError(_(
                'Custom SO YA masih tahap pengembangan. Konfirmasi ditutup '
                'sementara sampai reservasi kapasitas produksi selesai diuji. '
                'SO standar dari menu Sales tetap berjalan.'
            ))
        return super().action_confirm()
