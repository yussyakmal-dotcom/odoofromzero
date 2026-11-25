"""YA commercial SO confirmation is tied to protected kitchen capacity.

Only the RO_SO test clone may confirm YA capacity orders. Standard Sales
Quotations remain native and are not subject to YA manufacturing guards.
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
        protected = {'order_line'}
        if protected.intersection(vals) and any(
            o.ya_is_capacity_so and o.state in ('sale', 'done') for o in self
        ):
            raise UserError(_(
                'Produk/Qty YA SO Confirmed terkunci karena kapasitas produksi '
                'sudah dipesan. Perubahan memerlukan prosedur revisi terpisah.'
            ))
        if vals.get('state') in ('draft', 'sent', 'cancel') and any(
            o.ya_is_capacity_so and o.state in ('sale', 'done') for o in self
        ):
            raise UserError(_(
                'SO YA Confirmed tidak dapat dibatalkan/dibuka kembali: '
                'pelepasan reservasi kapasitas belum tersedia.'
            ))
        # Draft quotation remains freely editable; normal Sales unchanged.
        return super().write(vals)

    def action_cancel(self):
        if any(o.ya_is_capacity_so and o.state in ('sale', 'done') for o in self):
            raise UserError(_(
                'Pembatalan SO YA setelah Confirm memerlukan prosedur release '
                'kapasitas yang belum diaktifkan.'
            ))
        return super().action_cancel()

    def action_draft(self):
        if any(o.ya_is_capacity_so and o.state in ('sale', 'done') for o in self):
            raise UserError(_(
                'SO YA Confirmed tidak boleh kembali Draft dengan reservasi aktif.'
            ))
        return super().action_draft()

    def action_open_discount_wizard(self):
        """Use YA's PO-style discount choices only for YA quotations."""
        self.ensure_one()
        if not self.ya_is_capacity_so:
            return super().action_open_discount_wizard()
        if self.state not in ('draft', 'sent'):
            raise UserError(_('Diskon YA hanya dapat diubah pada Quotation Draft/Sent.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Discount'),
            'res_model': 'ya.sale.quotation.discount.wizard',
            'view_mode': 'form',
            'views': [(self.env.ref(
                'ya_sale_production_capacity.view_ya_quotation_discount_wizard_form'
            ).id, 'form')],
            'target': 'new',
            'context': {'default_order_id': self.id},
        }

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
        # Open the YA-only atomic capacity confirmation wizard.
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

    def _ya_native_confirm_without_early_delivery(self):
        """Internal native Confirm after protected capacity is booked.

        Odoo 19 sale_stock respects context skip_procurement in
        sale.order.line._action_launch_stock_rule. Confirm YA commercial
        obligation without a premature Sales-warehouse delivery; the real
        PCK shipment must be created and linked by Packing later.
        """
        self.ensure_one()
        if self.env.cr.dbname != 'erp-yussyakmal-mrp-test-RO_SO':
            raise UserError(_('YA Confirm integration may run only on the RO_SO clone.'))
        if not self.ya_is_capacity_so or self.state not in ('draft', 'sent'):
            raise UserError(_('Expected one YA Draft/Sent quotation.'))
        reserved = self.env['ya.sale.capacity.reservation'].sudo().search_count([
            ('order_id', '=', self.id),
        ])
        if not reserved:
            raise UserError(_('Cannot Confirm YA SO without protected kitchen capacity.'))
        if self.picking_ids:
            raise UserError(_('YA quotation has unexpected existing pickings.'))
        result = super(SaleOrder, self.with_context(
            skip_procurement=True,
        )).action_confirm()
        if self.state not in ('sale', 'done') or self.picking_ids:
            raise UserError(_(
                'YA SO Confirm created an unexpected delivery or did not '
                'reach Confirmed state; transaction must roll back.'
            ))
        Move = self.env['stock.move'].sudo()
        if 'sale_line_id' in Move._fields and Move.search_count([
            ('sale_line_id', 'in', self.order_line.ids),
        ]):
            raise UserError(_(
                'Unexpected native stock movement for YA Confirm: '
                'transaction rolled back. Dispatch must start in Packing.'
            ))
        return result


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.model_create_multi
    def create(self, vals_list):
        order_ids = [v.get('order_id') for v in vals_list if v.get('order_id')]
        if order_ids and any(
            order.ya_is_capacity_so and order.state in ('sale', 'done')
            for order in self.env['sale.order'].browse(order_ids)
        ):
            raise UserError(_(
                'Cannot add lines to confirmed YA SO while production '
                'capacity is reserved.'
            ))
        return super().create(vals_list)

    def write(self, vals):
        protected = {'product_id', 'product_uom_qty', 'product_uom_id', 'order_id'}
        if protected.intersection(vals) and any(
            line.order_id.ya_is_capacity_so
            and line.order_id.state in ('sale', 'done')
            for line in self
        ):
            raise UserError(_(
                'Cannot change the product/Qty/UoM of confirmed YA SO. '
                'Protected capacity would become inconsistent.'
            ))
        return super().write(vals)

    def unlink(self):
        if any(
            line.order_id.ya_is_capacity_so
            and line.order_id.state in ('sale', 'done')
            for line in self
        ):
            raise UserError(_(
                'Cannot delete lines from confirmed YA SO with capacity '
                'reservations.'
            ))
        return super().unlink()
