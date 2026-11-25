"""PO-style discount wizard for YA Quotations; native Sales remains unchanged.

No mixing of native global discount lines with per-line discount.
For tax consistency use Odoo's native sale.order.line.discount and
sale.order.discount on All/Global/Fixed modes.
"""
from odoo import fields, models, _
from odoo.exceptions import ValidationError, UserError
from odoo.tools import float_compare


class YaQuotationDiscountWizard(models.TransientModel):
    _name = 'ya.sale.quotation.discount.wizard'
    _description = 'YA Quotation Discount (% or Amount, Line or Global)'

    order_id = fields.Many2one('sale.order', required=True, readonly=True)
    currency_id = fields.Many2one(related='order_id.currency_id')
    discount_type = fields.Selection([
        ('one_percent', 'One Order Line (%)'),
        ('one_amount', 'One Order Line (Rp)'),
        ('all_percent', 'On All Order Lines (%)'),
        ('global_percent', 'Global Discount (%)'),
        ('global_amount', 'Fixed Amount (Rp)'),
    ], required=True, default='one_percent')
    percentage = fields.Float(string='Discount (%)', digits=(16, 2))
    amount = fields.Monetary(string='Discount (Rp)', currency_field='currency_id')
    line_id = fields.Many2one('sale.order.line', string='Product Line',
                             domain="[('order_id', '=', order_id), ('display_type', '=', False)]")

    def action_apply_discount(self):
        self.ensure_one()
        order = self.order_id
        if not order.exists() or not order.ya_is_capacity_so or order.state not in ('draft', 'sent'):
            raise UserError(_('Diskon ini hanya untuk Quotation YA berstatus Draft/Sent.'))
        typ = self.discount_type
        is_amount = typ in ('one_amount', 'global_amount')
        value = self.amount if is_amount else self.percentage
        if value < 0 or (not is_amount and value > 100):
            raise ValidationError(_('Diskon harus positif, maksimal 100%, atau Rp tidak negatif.'))
        lines = order.order_line.filtered(
            lambda line: not line.display_type and not line.is_downpayment
            and not line._is_global_discount()
        )
        global_lines = order.order_line.filtered(lambda line: line._is_global_discount())
        if typ in ('one_percent', 'one_amount'):
            if global_lines:
                raise ValidationError(_(
                    'Sudah ada diskon global. Hapus baris diskon global terlebih dahulu '
                    'agar diskon tidak dihitung dua kali.'
                ))
            if not self.line_id or self.line_id not in lines:
                raise ValidationError(_('Pilih satu baris produk dari Quotation ini.'))
            gross = self.line_id.product_uom_qty * self.line_id.price_unit
            if typ == 'one_amount':
                if gross <= 0 and value:
                    raise ValidationError(_('Nominal diskon memerlukan total baris positif.'))
                if float_compare(value, gross, precision_rounding=order.currency_id.rounding) > 0:
                    raise ValidationError(_('Diskon Rp tidak boleh melebihi total nilai baris.'))
                percent = 100 * value / gross if gross else 0
            else:
                percent = value
            self.line_id.write({'discount': percent})
        else:
            if global_lines:
                raise ValidationError(_(
                    'Sudah ada diskon global. Hapus baris diskon global lama sebelum '
                    'mengganti diskon agar tidak membuat diskon ganda.'
                ))
            if typ in ('global_percent', 'global_amount') and any(line.discount for line in lines):
                raise ValidationError(_(
                    'Diskon per baris sudah ada. Hapus diskon per baris lebih dahulu '
                    'sebelum memakai diskon global.'
                ))
            if typ == 'all_percent' and any(line.discount for line in lines):
                # Replacing all line percentages is safe, but do not compound them.
                pass
            if typ == 'global_amount':
                gross_total = sum(line.price_subtotal for line in lines)
                if float_compare(value, gross_total, precision_rounding=order.currency_id.rounding) > 0:
                    raise ValidationError(_('Diskon global Rp melebihi subtotal produk.'))
            vals = {'sale_order_id': order.id}
            if typ == 'all_percent':
                vals.update(discount_type='sol_discount', discount_percentage=value / 100)
            elif typ == 'global_percent':
                vals.update(discount_type='so_discount', discount_percentage=value / 100)
            else:
                vals.update(discount_type='amount', discount_amount=value)
            self.env['sale.order.discount'].create(vals).action_apply_discount()
        return {'type': 'ir.actions.act_window_close'}
