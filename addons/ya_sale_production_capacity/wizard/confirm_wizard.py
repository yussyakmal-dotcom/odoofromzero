"""YA SO confirmation gate. Does NOT confirm or reserve capacity in Stage 1."""
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons.ya_store_ro.models.date_labels import format_ymondd


class YaSaleCapacityConfirmWizard(models.TransientModel):
    _name = 'ya.sale.capacity.confirm.wizard'
    _description = 'YA Sales Order Delivery Schedule Confirmation Gate'

    order_id = fields.Many2one('sale.order', required=True, readonly=True)
    delivery_date = fields.Date(string='YA Tanggal Kirim', required=True)
    slot = fields.Selection(
        [('S1', 'S1 - 05.00 WIB'), ('S2', 'S2 - 09.00 WIB'),
         ('S3', 'S3 - 11.00 WIB')],
        string='YA Slot Kirim', required=True,
    )
    delivery_date_label = fields.Char(
        string='Format YYYY-Mon-DD', compute='_compute_delivery_date_label',
    )

    @api.depends('delivery_date')
    def _compute_delivery_date_label(self):
        for wizard in self:
            wizard.delivery_date_label = format_ymondd(wizard.delivery_date)

    def action_check_and_confirm(self):
        self.ensure_one()
        order = self.order_id
        if not order.exists() or not order.ya_is_capacity_so or order.state not in ('draft', 'sent'):
            raise UserError(_('Hanya penawaran Custom SO YA Draft/Sent yang dapat dikonfirmasi.'))
        if not self.delivery_date or not self.slot:
            raise ValidationError(_('YA Tanggal Kirim dan YA Slot Kirim wajib diisi.'))
        planning = self.env['ya.production.planning'].search_count([
            ('delivery_date', '=', self.delivery_date),
            ('slot', '=', self.slot),
            ('state', '=', 'published'),
        ])
        if not planning:
            raise ValidationError(_(
                'Tidak ada Published Planning untuk %(date)s / %(slot)s.'
            ) % {'date': format_ymondd(self.delivery_date), 'slot': self.slot})
        # Verify the actual products and Paket component BoMs against the
        # published kitchen routes BEFORE the yet-unimplemented transaction.
        # Discount lines from the normal Sales discount wizard are excluded.
        # This is read-only: no booking, production, stock or SO confirmation.
        preview = order._ya_prepare_capacity_confirm_readonly(
            self.delivery_date, self.slot
        )
        raise UserError(_(
            'SKU dan Published Planning sudah lolos pemeriksaan awal: '
            '%(count)s SKU dapur; %(pkg)s Paket; %(pck)s komponen dari PCK. '
            'Confirm belum aktif: reservasi atomik dan integrasi prioritas '
            'SO ke MO/Packing belum selesai. Penawaran tetap Draft/Sent.'
        ) % {
            'count': len(preview['capacity']),
            'pkg': len(preview['package_qty']),
            'pck': len(preview['pck_stock_requirements']),
        })
