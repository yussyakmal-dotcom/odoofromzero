from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from .date_labels import format_ymondd
from .packing_lock import lock_ro_slot


class YaStoreRO(models.Model):
    _name = 'ya.store.ro'
    _description = 'YA Store Replenishment Order'
    _order = 'delivery_date desc, slot, kitchen_code, id desc'

    name = fields.Char(compute='_compute_name', string='RO')
    planning_id = fields.Many2one('ya.production.planning', required=True, readonly=True,
                                   index=True, ondelete='restrict')
    delivery_date = fields.Date(related='planning_id.delivery_date', store=True, readonly=True)
    delivery_date_yyyymmdd = fields.Char(
        string='Tgl Kirim (YYYY-Mon-DD)', compute='_compute_date_labels',
    )
    ro_date_yyyymmdd = fields.Char(
        string='Tgl RO (YYYY-Mon-DD)', compute='_compute_date_labels',
    )
    slot = fields.Selection(related='planning_id.slot', store=True, readonly=True)
    kitchen_code = fields.Char(related='planning_id.kitchen_code', store=True, readonly=True)
    store_warehouse_id = fields.Many2one('stock.warehouse', required=True,
                                         readonly=True, ondelete='restrict', index=True)
    state = fields.Selection([('draft', 'Draft'), ('confirmed', 'Confirmed')],
                             required=True, default='draft', index=True)
    line_ids = fields.One2many('ya.store.ro.line', 'ro_id', copy=False)
    qty_total = fields.Integer(compute='_compute_qty_total')
    line_count = fields.Integer(compute='_compute_qty_total')
    source_filename = fields.Char(readonly=True)
    confirmed_at = fields.Datetime(readonly=True)
    confirmed_by = fields.Many2one('res.users', readonly=True)
    # Display release status from immutable Packing batch, never set manually.
    production_ok = fields.Boolean(string='Produksi OK', compute='_compute_production_ok',
                                   compute_sudo=True, readonly=True)
    packing_batch_id = fields.Many2one(
        'ya.packing.batch', string='Packing Pre Produksi/Produksi OK',
        readonly=True, copy=False, ondelete='restrict', index=True,
    )
    correction_ids = fields.One2many(
        'ya.store.ro.qty.audit', 'ro_id', string='Riwayat Koreksi Qty', readonly=True,
    )
    _unique_ro_planning_store = models.Constraint(
        'UNIQUE(planning_id, store_warehouse_id)',
        'One RO per store, kitchen, delivery date and slot.'
    )

    @api.depends('delivery_date', 'slot')
    def _compute_production_ok(self):
        for ro in self:
            ro.production_ok = bool(
                ro.delivery_date and ro.slot and
                self.env['ya.packing.batch'].sudo().search_count([
                    ('delivery_date', '=', ro.delivery_date),
                    ('slot', '=', ro.slot), ('state', '=', 'production_ok'),
                ])
            )

    @api.depends('delivery_date', 'create_date')
    def _compute_date_labels(self):
        for ro in self:
            ro.delivery_date_yyyymmdd = (
                format_ymondd(ro.delivery_date) if ro.delivery_date else ''
            )
            ro.ro_date_yyyymmdd = (
                format_ymondd(fields.Datetime.context_timestamp(ro, ro.create_date))
                if ro.create_date else ''
            )

    @api.depends('planning_id', 'store_warehouse_id')
    def _compute_name(self):
        for ro in self:
            p = ro.planning_id
            ro.name = ('RO %s %s %s %s' % (
                (format_ymondd(p.delivery_date) if p.delivery_date else '-'),
                p.slot or '-', p.kitchen_code or '-',
                ro.store_warehouse_id.code or ro.store_warehouse_id.name or '-'))

    @api.depends('line_ids.qty_requested')
    def _compute_qty_total(self):
        for ro in self:
            ro.line_count = len(ro.line_ids)
            ro.qty_total = sum(ro.line_ids.mapped('qty_requested'))

    @api.model
    def action_open_upload(self, *args, **kwargs):
        if not self.env.user.has_group('mrp.group_mrp_manager'):
            raise UserError(_('Only a Manufacturing Manager may upload RO at this phase.'))
        return self.env.ref('ya_store_ro.action_ya_store_ro_import').read()[0]

    @api.model
    def action_open_packing_selected(self, *args, **kwargs):
        """List-view header receives selected record IDs as first RPC argument."""
        if not (self.env.user.has_group('mrp.group_mrp_manager') or
                self.env.user.has_group('ya_store_ro.group_ya_packing_admin')):
            raise UserError(_('Only Packing Admin or Manufacturing Manager may consolidate RO.'))
        selected_ids = list(self.ids)
        if args and isinstance(args[0], (list, tuple)):
            selected_ids = list(args[0])
        if not selected_ids:
            selected_ids = self.env.context.get('active_ids') or []
        if not selected_ids:
            raise UserError(_('Select Confirmed RO rows in the list before clicking Konsolidasi SKU.'))
        orders = self.browse(selected_ids).exists()
        if len(orders) != len(set(selected_ids)):
            raise UserError(_('One or more selected RO records no longer exist.'))
        if any(ro.state != 'confirmed' for ro in orders):
            raise UserError(_('Only Confirmed RO may be consolidated.'))
        if any(ro.packing_batch_id for ro in orders):
            raise UserError(_('One or more selected RO already moved to Pre Produksi.'))
        dates_slots = {(ro.delivery_date, ro.slot) for ro in orders}
        if len(dates_slots) != 1:
            raise UserError(_('Select RO with the SAME Tanggal Kirim and Slot.'))
        delivery_date, slot = next(iter(dates_slots))
        if self.env['ya.packing.batch'].sudo().search_count([
            ('delivery_date', '=', delivery_date), ('slot', '=', slot),
        ]):
            raise UserError(_('This date/slot is already Pre Produksi or Produksi OK. Open the Pre Produksi list.'))
        action = self.env.ref('ya_store_ro.action_ya_packing_preview').read()[0]
        action['context'] = {
            'default_selected_ro_ids': [(6, 0, orders.ids)],
            'default_delivery_date_yyyymmdd': format_ymondd(delivery_date),
            'default_slot': slot,
        }
        return action

    def action_confirm(self):
        self.ensure_one()
        if not self.env.user.has_group('mrp.group_mrp_manager'):
            raise UserError(_('Only a Manufacturing Manager may confirm RO at this phase.'))
        if self.state != 'draft':
            raise UserError(_('Only Draft RO can be confirmed.'))
        lock_ro_slot(self.env.cr, self.delivery_date, self.slot)
        if self.env['ya.packing.batch'].sudo().search_count([
            ('delivery_date', '=', self.delivery_date),
            ('slot', '=', self.slot), ('state', '=', 'production_ok'),
        ]):
            raise UserError(_('Produksi OK already released: cannot add new Confirmed RO.'))
        if self.planning_id.state != 'published':
            raise UserError(_('Source Planning must still be Published.'))
        if not self.line_ids.filtered(lambda r: r.qty_requested > 0):
            raise UserError(_('At least one SKU must have Qty Pesan greater than zero.'))
        eligible = {line.product_id.id for line in self.planning_id.line_ids
                    if line.max_capacity > 0}
        for line in self.line_ids:
            if line.product_id.id not in eligible:
                raise UserError(_('SKU %s is not eligible in Published Planning.') % line.reference)
        self.write({'state': 'confirmed', 'confirmed_at': fields.Datetime.now(),
                    'confirmed_by': self.env.user.id})
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'res_id': self.id, 'view_mode': 'form',
                'views': [(False, 'form')], 'target': 'current'}

    @api.model_create_multi
    def create(self, vals_list):
        if any('production_ok' in vals for vals in vals_list):
            raise UserError(_('Produksi OK cannot be set when creating RO.'))
        return super().create(vals_list)

    def write(self, vals):
        if set(vals) == {'packing_batch_id'}:
            if not (self.env.context.get('ya_stage_or_reset_packing') and
                    self.env.user.has_group('ya_store_ro.group_ya_packing_admin')):
                raise UserError(_('Only Packing workflow may move RO to/from Pre Produksi.'))
            batch_id = vals['packing_batch_id']
            if any(ro.state != 'confirmed' for ro in self):
                raise UserError(_('Only Confirmed RO can be staged.'))
            if batch_id:
                batch = self.env['ya.packing.batch'].browse(batch_id).exists()
                if len(batch) != 1 or batch.state != 'pre_production':
                    raise UserError(_('Target Pre Produksi batch is invalid.'))
                if any(ro.packing_batch_id or
                       ro.delivery_date != batch.delivery_date or ro.slot != batch.slot
                       for ro in self):
                    raise UserError(_('RO staging conflicts with date/slot or prior batch.'))
            else:
                if any(not ro.packing_batch_id or
                       ro.packing_batch_id.state != 'pre_production'
                       for ro in self):
                    raise UserError(_('Cannot remove RO from Produksi OK.'))
            return super().write(vals)
        if 'production_ok' in vals:
            raise UserError(_('Produksi OK requires the future atomic MO generation action.'))
        if any(ro.state != 'draft' for ro in self):
            raise UserError(_('Confirmed RO is immutable.'))
        if vals.get('state') == 'confirmed' and not self.env.user.has_group('mrp.group_mrp_manager'):
            raise UserError(_('Only a Manufacturing Manager may confirm RO.'))
        protected = {'planning_id', 'store_warehouse_id', 'delivery_date', 'slot', 'kitchen_code'}
        if protected.intersection(vals) and any(ro.line_ids for ro in self):
            raise UserError(_('Cannot change store or Planning of an existing RO.'))
        return super().write(vals)

    def unlink(self):
        if any(ro.state != 'draft' for ro in self):
            raise UserError(_('Confirmed RO cannot be deleted.'))
        return super().unlink()


class YaStoreROLine(models.Model):
    _name = 'ya.store.ro.line'
    _description = 'YA Store Replenishment Order Line'
    _order = 'id'

    ro_id = fields.Many2one('ya.store.ro', required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one('product.product', required=True, readonly=True)
    reference = fields.Char(required=True, readonly=True)
    qty_requested = fields.Integer(string='Qty Pesan', required=True, default=0)
    uom_id = fields.Many2one('uom.uom', required=True, readonly=True)

    _unique_ro_product = models.Constraint(
        'UNIQUE(ro_id, product_id)', 'Duplicate SKU in the same RO.'
    )
    _qty_nonnegative = models.Constraint(
        'CHECK(qty_requested >= 0)', 'Qty Pesan cannot be negative.'
    )

    @api.constrains('qty_requested')
    def _check_qty(self):
        if any(line.qty_requested < 0 for line in self):
            raise ValidationError(_('Qty Pesan cannot be negative.'))

    @api.model_create_multi
    def create(self, vals_list):
        ids = [vals['ro_id'] for vals in vals_list if vals.get('ro_id')]
        if ids and any(ro.state != 'draft' for ro in self.env['ya.store.ro'].browse(ids)):
            raise UserError(_('Confirmed RO cannot be changed.'))
        return super().create(vals_list)

    def write(self, vals):
        if set(vals) - {'qty_requested'}:
            raise UserError(_('Only Qty Pesan can be edited in a Draft RO.'))
        confirmed = self.filtered(lambda line: line.ro_id.state == 'confirmed')
        if confirmed:
            reason = (self.env.context.get('packing_qty_correction_reason') or '').strip()
            if not self.env.user.has_group('ya_store_ro.group_ya_packing_admin') or not reason:
                raise UserError(_('Only Packing Admin may edit Confirmed Qty with a reason.'))
            ro = confirmed.ro_id
            lock_ro_slot(self.env.cr, ro.delivery_date, ro.slot)
            if ro.packing_batch_id or self.env['ya.packing.batch'].sudo().search_count([
                ('delivery_date', '=', ro.delivery_date),
                ('slot', '=', ro.slot),
            ]):
                raise UserError(_(
                    'RO already entered Pre Produksi or Produksi OK. '
                    'Qty is locked; corrections are no longer allowed.'
                ))
            if set(vals) != {'qty_requested'} or len(self) != 1:
                raise UserError(_('Correct one RO line at a time.'))
            new_qty = vals['qty_requested']
            if not isinstance(new_qty, int) or isinstance(new_qty, bool) or new_qty < 0:
                raise UserError(_('Qty Pesan must be a nonnegative integer.'))
            old_qty = confirmed.qty_requested
            result = super().write(vals)
            if old_qty != new_qty:
                self.env['ya.store.ro.qty.audit'].sudo().with_context(packing_qty_correction_reason=reason).create({
                    'ro_id': confirmed.ro_id.id,
                    'ro_line_id': confirmed.id,
                    'product_id': confirmed.product_id.id,
                    'qty_before': old_qty, 'qty_after': new_qty,
                    'reason': reason,
                })
            return result
        if not self.env.user.has_group('mrp.group_mrp_manager'):
            raise UserError(_('Only RO operators with the current manager permission may edit Draft Qty.'))
        return super().write(vals)

    def unlink(self):
        if any(line.ro_id.state != 'draft' for line in self):
            raise UserError(_('Confirmed RO cannot be changed.'))
        return super().unlink()

class YaStoreROQtyAudit(models.Model):
    _name = 'ya.store.ro.qty.audit'
    _description = 'YA Store RO Packing Qty Correction Audit'
    _order = 'changed_at desc, id desc'

    ro_id = fields.Many2one('ya.store.ro', required=True, ondelete='restrict', readonly=True)
    ro_line_id = fields.Many2one('ya.store.ro.line', required=True, ondelete='restrict', readonly=True)
    product_id = fields.Many2one('product.product', required=True, readonly=True)
    qty_before = fields.Integer(readonly=True)
    qty_after = fields.Integer(readonly=True)
    reason = fields.Text(required=True, readonly=True)
    changed_by = fields.Many2one('res.users', default=lambda self: self.env.user, readonly=True)
    changed_at = fields.Datetime(default=fields.Datetime.now, readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.su:
            raise UserError(_('Audit records are created only by the correction service.'))
        reason = (self.env.context.get('packing_qty_correction_reason') or '').strip()
        if not reason:
            raise UserError(_('Correction reason is required for audit.'))
        for vals in vals_list:
            if (vals.get('reason') or '').strip() != reason:
                raise UserError(_('Correction reason mismatch.'))
        return super().create(vals_list)

    def write(self, vals):
        raise UserError(_('RO Qty audit records cannot be modified.'))

    def unlink(self):
        raise UserError(_('RO Qty audit records cannot be deleted.'))
