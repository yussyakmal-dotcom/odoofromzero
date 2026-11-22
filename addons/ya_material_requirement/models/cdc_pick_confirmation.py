"""CDC physical picking confirmation per existing Packing batch and kitchen.

Explicit operator action; keeps MO demand separate from Special Transfer.
THIS PHASE DOES NOT CREATE OR VALIDATE STOCK PICKINGS/MOVES, OR RESERVE STOCK.
Odoo standard Internal Transfers will be added only after route/FEFO audit.
Strictly limited to the Manufacturing test database.
"""
from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare

TEST_DB = 'erp-yussyakmal-mrp-test'


def _guard_db(env):
    if env.cr.dbname != TEST_DB:
        raise UserError(_('CDC picking confirmation is restricted to test DB %s.') % TEST_DB)


def _guard_role(env):
    if not (env.user.has_group('mrp.group_mrp_manager') or
            env.user.has_group('ya_store_ro.group_ya_packing_admin')):
        raise UserError(_('MRP Manager / YA Packing Admin access required.'))


class YaCdcPickConfirmation(models.Model):
    _name = 'ya.cdc.pick.confirmation'
    _description = 'YA CDC Picking Confirmation Per Kitchen'
    _order = 'batch_id desc, warehouse_id, id'
    _rec_name = 'name'

    name = fields.Char(compute='_compute_name', string='Referensi Picking')
    batch_id = fields.Many2one('ya.packing.batch', required=True, readonly=True,
                               ondelete='restrict', index=True)
    warehouse_id = fields.Many2one('stock.warehouse', string='Dapur Tujuan',
                                   required=True, readonly=True)
    company_id = fields.Many2one('res.company', related='warehouse_id.company_id',
                                 store=True, readonly=True)
    cdc_warehouse_id = fields.Many2one('stock.warehouse',
                                       string='Gudang Asal CDC', required=True,
                                       readonly=True)
    state = fields.Selection([
        ('draft', 'Menunggu Konfirmasi Qty'),
        ('confirmed', 'Qty Picking Terkonfirmasi'),
    ], default='draft', required=True, readonly=True, index=True)
    line_ids = fields.One2many('ya.cdc.pick.confirmation.line',
                               'confirmation_id', string='Bahan yang Dipicking',
                               copy=False)
    confirmed_by = fields.Many2one('res.users', readonly=True)
    confirmed_at = fields.Datetime(readonly=True)
    confirmed_at_label = fields.Char(
        string='Waktu Konfirmasi (YYYY-Mon-DD)', compute='_compute_confirm_label')
    info = fields.Text(readonly=True,
        default='Qty Picking Aktual boleh melebihi kebutuhan MO hanya dengan '
                'Special Transfer dan alasan; cantumkan referensi bila ada. '
                'Tambahan tidak menambah Qty MO. '
                'Konfirmasi di tahap ini TIDAK membuat transfer ataupun mutasi stok.')

    _unique_batch_destination = models.Constraint(
        'UNIQUE(batch_id, warehouse_id)',
        'Picking confirmation for this Packing batch and kitchen already exists.',
    )

    @api.depends('batch_id.name', 'warehouse_id.code')
    def _compute_name(self):
        for rec in self:
            rec.name = '%s / CDC → %s' % (
                rec.batch_id.name or '-', rec.warehouse_id.code or '-')

    @api.depends('confirmed_at')
    def _compute_confirm_label(self):
        for rec in self:
            rec.confirmed_at_label = (
                fields.Datetime.context_timestamp(
                    rec, rec.confirmed_at).strftime('%Y-%b-%d %H:%M')
                if rec.confirmed_at else ''
            )

    @api.model_create_multi
    def create(self, vals_list):
        _guard_db(self.env)
        _guard_role(self.env)
        if not self.env.context.get('ya_create_cdc_pick_confirmations'):
            raise UserError(_('Picking documents must come from the Packing batch form.'))
        for vals in vals_list:
            batch = self.env['ya.packing.batch'].browse(vals.get('batch_id'))
            wh = self.env['stock.warehouse'].browse(vals.get('warehouse_id'))
            cdc = self.env['stock.warehouse'].browse(vals.get('cdc_warehouse_id'))
            if (not batch.exists() or batch.state != 'production_ok' or
                    not wh.exists() or not cdc.exists() or
                    wh.company_id != cdc.company_id or
                    wh == cdc or cdc.code != 'CDC'):
                raise UserError(_('Invalid source batch, destination or CDC warehouse.'))
        return super().create(vals_list)

    def write(self, vals):
        _guard_db(self.env)
        _guard_role(self.env)
        if any(doc.state == 'confirmed' for doc in self):
            raise UserError(_('Confirmed picking documents are locked.'))
        if set(vals) & {'batch_id', 'warehouse_id', 'cdc_warehouse_id',
                        'company_id', 'confirmed_by', 'confirmed_at'}:
            if not self.env.context.get('ya_confirm_cdc_pick'):
                raise UserError(_('Cannot change picking origin, destination or audit.'))
        if 'state' in vals and not (
                self.env.context.get('ya_confirm_cdc_pick') and
                vals['state'] == 'confirmed'):
            raise UserError(_('Only the Confirm Qty button may change state.'))
        return super().write(vals)

    def unlink(self):
        raise UserError(_('Picking confirmation documents cannot be deleted.'))

    def _open_form(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('CDC Picking Confirmation'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref(
                'ya_material_requirement.view_ya_cdc_pick_confirmation_form'
            ).id, 'form')],
            'target': 'current',
        }

    def action_confirm_qty(self):
        """Confirm physical qty, allowing an explicitly documented extra amount.

        Validate quantities against pooled CDC free stock ONCE across kitchens.
        This is still not a reservation; available stock must be checked again
        before native Internal Transfer and lot/FEFO assignment.
        """
        self.ensure_one()
        _guard_db(self.env)
        _guard_role(self.env)
        if self.state != 'draft':
            raise UserError(_('Qty picking already confirmed; cannot confirm twice.'))
        if self.batch_id.state != 'production_ok' or not self.line_ids:
            raise UserError(_('Packing batch or physical picking lines are invalid.'))
        if self.warehouse_id.company_id != self.cdc_warehouse_id.company_id:
            raise UserError(_('CDC and kitchen companies differ.'))
        seen = set()
        for line in self.line_ids:
            if line.product_id.id in seen:
                raise UserError(_('Duplicate product on physical picking sheet: %s.')
                                % line.product_id.display_name)
            seen.add(line.product_id.id)
            rounding = line.uom_id.rounding or 0.00001
            if line.product_id.uom_id != line.uom_id:
                raise UserError(_('Use product stock UoM for %s.')
                                % line.product_id.display_name)
            if (line.product_id.company_id and
                    line.product_id.company_id != self.company_id):
                raise UserError(_('Material company differs: %s.')
                                % line.product_id.display_name)
            if 'is_storable' in line.product_id._fields:
                if not line.product_id.is_storable:
                    raise UserError(_('Not storable: %s.') % line.product_id.display_name)
            elif line.product_id.type != 'product':
                raise UserError(_('Not storable: %s.') % line.product_id.display_name)
            if line.requested_qty < 0 or line.picked_qty < 0:
                raise UserError(_('Quantity cannot be negative: %s.')
                                % line.product_id.display_name)
            is_extra = float_compare(
                line.picked_qty, line.requested_qty,
                precision_rounding=rounding,
            ) > 0
            if is_extra and not line.special_transfer:
                raise UserError(_(
                    'Qty fisik exceeds MO requirement for %s. '
                    'Mark Special Transfer and enter a reason.'
                ) % line.product_id.display_name)
            if is_extra and not (line.special_reason or '').strip():
                raise UserError(_('Special Transfer reason is required for %s.')
                                % line.product_id.display_name)
            if line.special_transfer and not is_extra:
                raise UserError(_('Special Transfer must have actual Qty above '
                                  'MO requirement: %s.')
                                % line.product_id.display_name)
        if not any(line.picked_qty > 0 for line in self.line_ids):
            raise UserError(_('No physical picked quantity to confirm.'))

        # Lock CDC warehouse across concurrent confirmation requests in this DB
        # to avoid approving different kitchen sheets against the same free stock.
        self.env.cr.execute(
            'SELECT id FROM stock_warehouse WHERE id = %s FOR UPDATE',
            [self.cdc_warehouse_id.id],
        )
        docs = self.search([
            ('batch_id', '=', self.batch_id.id),
            ('state', '=', 'confirmed'),
        ])
        needs = defaultdict(float)
        for doc in docs | self:
            for line in doc.line_ids:
                needs[line.product_id.id] += line.picked_qty
        Quants = self.env['stock.quant']
        for pid, qty in needs.items():
            product = self.env['product.product'].browse(pid)
            quants = Quants.search([
                ('product_id', '=', pid),
                ('location_id', 'child_of', self.cdc_warehouse_id.lot_stock_id.id),
                ('location_id.usage', '=', 'internal'),
                ('company_id', '=', self.company_id.id),
            ])
            free = sum(max(0.0, q.quantity - q.reserved_quantity) for q in quants)
            if float_compare(qty, free, precision_rounding=product.uom_id.rounding) > 0:
                raise UserError(_(
                    'Total actual picking from all kitchens for %(product)s '
                    'is %(picked).3f, but CDC free stock is only %(free).3f. '
                    'Adjust actual quantities or replenish CDC outside this flow.'
                ) % {'product': product.display_name, 'picked': qty, 'free': free})
        self.with_context(ya_confirm_cdc_pick=True).write({
            'state': 'confirmed',
            'confirmed_by': self.env.user.id,
            'confirmed_at': fields.Datetime.now(),
        })
        return self._open_form()


class YaCdcPickConfirmationLine(models.Model):
    _name = 'ya.cdc.pick.confirmation.line'
    _description = 'YA CDC Physical Picked Material'
    _order = 'product_id, id'
    _rec_name = 'product_id'

    confirmation_id = fields.Many2one(
        'ya.cdc.pick.confirmation', required=True, ondelete='cascade',
        index=True,
    )
    product_id = fields.Many2one('product.product', string='Bahan',
                                 required=True)
    uom_id = fields.Many2one('uom.uom', string='Satuan', required=True)
    requested_qty = fields.Float(string='Qty Picking List (MO)',
                                 readonly=True, digits='Product Unit of Measure')
    picked_qty = fields.Float(string='Qty Picking Aktual',
                              digits='Product Unit of Measure')
    special_qty = fields.Float(string='Qty Special Transfer',
                               compute='_compute_special_qty',
                               digits='Product Unit of Measure')
    special_transfer = fields.Boolean(string='Special Transfer?')
    special_reason = fields.Char(string='Alasan Special Transfer')
    special_reference = fields.Char(
        string='Referensi Special Transfer',
        help='Nomor permintaan atau transfer khusus bila tersedia. '
             'Pencatatan nomor ini tidak membuat transfer baru.',
    )

    _unique_doc_product = models.Constraint(
        'UNIQUE(confirmation_id, product_id)',
        'Each product may appear only once per picking confirmation.',
    )

    @api.depends('requested_qty', 'picked_qty')
    def _compute_special_qty(self):
        for line in self:
            line.special_qty = max(0.0, line.picked_qty - line.requested_qty)

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.uom_id = self.product_id.uom_id

    @api.model_create_multi
    def create(self, vals_list):
        _guard_db(self.env)
        _guard_role(self.env)
        for vals in vals_list:
            doc = self.env['ya.cdc.pick.confirmation'].browse(
                vals.get('confirmation_id'))
            if not doc.exists() or doc.state != 'draft':
                raise UserError(_('Can add products only to draft picking confirmations.'))
            product = self.env['product.product'].browse(vals.get('product_id'))
            if not product.exists():
                raise UserError(_('Select a valid product.'))
            if not vals.get('uom_id'):
                vals['uom_id'] = product.uom_id.id
            if vals.get('requested_qty') and not self.env.context.get(
                    'ya_create_cdc_pick_confirmations'):
                raise UserError(_('MO requested Qty may not be entered manually.'))
        return super().create(vals_list)

    def write(self, vals):
        _guard_db(self.env)
        _guard_role(self.env)
        if any(line.confirmation_id.state != 'draft' for line in self):
            raise UserError(_('Confirmed physical picking lines cannot be edited.'))
        if 'requested_qty' in vals and not self.env.context.get(
                'ya_create_cdc_pick_confirmations'):
            raise UserError(_('MO request Qty is read-only.'))
        if 'confirmation_id' in vals:
            raise UserError(_('Cannot move a picked line between documents.'))
        return super().write(vals)

    def unlink(self):
        _guard_db(self.env)
        _guard_role(self.env)
        if any(line.confirmation_id.state != 'draft' for line in self):
            raise UserError(_('Confirmed physical picking lines cannot be removed.'))
        if any(line.requested_qty > 0 for line in self):
            raise UserError(_('MO requested materials must remain on the picking '
                              'confirmation. Set actual Qty to zero if missing.'))
        return super().unlink()
