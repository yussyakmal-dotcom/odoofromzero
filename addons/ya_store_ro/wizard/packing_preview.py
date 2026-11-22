"""RO-only Packing Preview: all Confirmed store RO for a delivery date and slot.

Group per kitchen + SKU. Each group becomes the BASIS for one eventual MO.
Read-only for all persistent business documents; no MO or stock move here.
"""
from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from ..models.allocation_rules import allocate_surplus_prorata
from ..models.date_labels import format_ymondd, parse_ymondd
from ..models.packing_lock import lock_ro_slot

SLOTS = [('S1', 'S1 - 05.00 WIB'), ('S2', 'S2 - 09.00 WIB'),
         ('S3', 'S3 - 11.00 WIB')]


class YaPackingPreview(models.TransientModel):
    _name = 'ya.packing.preview'
    _description = 'YA Packing RO-only Consolidation Preview'

    delivery_date_yyyymmdd = fields.Char(
        string='Tanggal Kirim (YYYY-Mon-DD)', required=True,
        default=lambda self: format_ymondd(fields.Date.context_today(self)),
    )
    slot = fields.Selection(SLOTS, string='Slot Pengiriman', required=True)
    selected_ro_ids = fields.Many2many(
        'ya.store.ro', string='RO Confirmed Dipilih', readonly=True,
    )
    selected_count = fields.Integer(compute='_compute_selected_count')

    @api.depends('selected_ro_ids')
    def _compute_selected_count(self):
        for wizard in self:
            wizard.selected_count = len(wizard.selected_ro_ids)
    ro_count = fields.Integer(readonly=True)
    kitchen_count = fields.Integer(readonly=True)
    sku_count = fields.Integer(readonly=True)
    blocked_count = fields.Integer(readonly=True)
    total_requested = fields.Integer(readonly=True)
    total_production = fields.Integer(readonly=True)
    info = fields.Text(readonly=True)
    state = fields.Selection([('choose', 'Choose'), ('preview', 'Preview')],
                             default='choose', required=True)
    line_ids = fields.One2many('ya.packing.preview.line', 'wizard_id', readonly=True)
    allocation_ids = fields.One2many('ya.packing.preview.allocation',
                                    'wizard_id', readonly=True)
    source_line_ids = fields.One2many('ya.packing.preview.source.line', 'wizard_id')

    def _reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name, 'res_id': self.id,
            'view_mode': 'form', 'views': [(False, 'form')], 'target': 'new',
        }

    def action_preview(self):
        self.ensure_one()
        if not (self.env.user.has_group('mrp.group_mrp_manager') or
                self.env.user.has_group('ya_store_ro.group_ya_packing_admin')):
            raise UserError(_('Only a Manufacturing Manager or Packing Admin may preview consolidation.'))
        try:
            delivery_date = parse_ymondd(self.delivery_date_yyyymmdd)
        except ValueError:
            raise UserError(_('Tanggal Kirim must be YYYY-Mon-DD, e.g. 2026-Nov-22.'))
        if not self.slot:
            raise UserError(_('Select Slot Pengiriman.'))
        orders = self.selected_ro_ids.exists()
        if not orders:
            raise UserError(_('Open Packing from the Confirmed RO list and select RO rows.'))
        if any(ro.state != 'confirmed' for ro in orders):
            raise UserError(_('Some selected RO are no longer Confirmed. Re-select RO.'))
        if any(ro.delivery_date != delivery_date or ro.slot != self.slot for ro in orders):
            raise UserError(_('Selected RO must use the SAME Tanggal Kirim and Slot.'))

        # Group by Published Planning ID and SKU ID. One Planning = one kitchen
        # for date+slot by the Planning unique DB constraint.
        by_group = defaultdict(dict)
        planning_lines = {}
        included_kitchens = set()
        source_ro_by_group_store = {}
        for ro in orders:
            if ro.packing_batch_id:
                raise UserError(_('RO already Pre Produksi: Qty is locked.'))
            plan = ro.planning_id
            if plan.state != 'published':
                raise UserError(_('Confirmed RO %s is linked to non-Published Planning.')
                                % ro.display_name)
            included_kitchens.add(plan.kitchen_code)
            eligible = planning_lines.setdefault(
                plan.id,
                {line.product_id.id: line for line in plan.line_ids
                 if line.max_capacity > 0},
            )
            for order_line in ro.line_ids:
                source_line_values.append((0, 0, {
                    'ro_line_id': order_line.id,
                    'ro_id': ro.id,
                    'store_warehouse_id': ro.store_warehouse_id.id,
                    'kitchen_code': plan.kitchen_code,
                    'product_id': order_line.product_id.id,
                    'reference': order_line.reference,
                    'old_qty': order_line.qty_requested,
                    'new_qty': order_line.qty_requested,
                }))
                source = eligible.get(order_line.product_id.id)
                if not source:
                    raise UserError(_('Confirmed RO %s has SKU outside Published Planning: %s')
                                    % (ro.display_name, order_line.reference))
                if order_line.uom_id != source.uom_id:
                    raise UserError(_('RO SKU UoM mismatch: %s') % order_line.reference)
                if order_line.qty_requested < 0:
                    raise UserError(_('RO Qty cannot be negative.'))
                if order_line.qty_requested:
                    group = (plan.id, order_line.product_id.id)
                    store_id = ro.store_warehouse_id.id
                    # Guard against duplicate lines/store across RO documents.
                    if store_id in by_group[group]:
                        raise UserError(_('Duplicate store Qty for kitchen %s SKU %s.')
                                        % (plan.kitchen_code, order_line.reference))
                    by_group[group][store_id] = order_line.qty_requested
                    source_ro_by_group_store[(plan.id, order_line.product_id.id, store_id)] = ro

        if not by_group:
            raise UserError(_('All Confirmed RO quantities are zero.'))

        line_values, allocation_values, blocked = [], [], []
        source_line_values = []
        total_requested = total_production = 0
        sort_key = lambda item: (
            self.env['ya.production.planning'].browse(item[0]).kitchen_code,
            planning_lines[item[0]][item[1]].reference or '', item[1],
        )
        for plan_id, product_id in sorted(by_group, key=sort_key):
            plan = self.env['ya.production.planning'].browse(plan_id)
            source = planning_lines[plan_id][product_id]
            try:
                bom = source._capacity_bom()
            except UserError as exc:
                raise UserError(_('Dapur %s SKU %s: Cannot resolve BoM: %s') %
                                (plan.kitchen_code, source.reference, exc))
            batch = bom.product_qty
            if batch <= 0 or int(batch) != batch:
                raise UserError(_('Dapur %s SKU %s: BoM output %s must be a positive integer.')
                                % (plan.kitchen_code, source.reference, batch))

            requests = by_group[(plan_id, product_id)]
            produced, allocations = allocate_surplus_prorata(requests, int(batch))
            requested = sum(requests.values())
            blocked_capacity = produced > source.max_capacity
            if blocked_capacity:
                blocked.append('%s / %s' % (plan.kitchen_code, source.reference))
            total_requested += requested
            total_production += produced
            line_values.append((0, 0, {
                'planning_id': plan_id,
                'kitchen_code': plan.kitchen_code,
                'product_id': product_id,
                'reference': source.reference,
                'uom_id': source.uom_id.id,
                'bom_id': bom.id,
                'bom_output': int(batch),
                'max_capacity': source.max_capacity,
                'qty_requested': requested,
                'qty_production': produced,
                'qty_surplus': produced - requested,
                'capacity_status': 'blocked' if blocked_capacity else 'ok',
            }))
            for store_id in sorted(allocations):
                a = allocations[store_id]
                source_ro = source_ro_by_group_store[(plan_id, product_id, store_id)]
                allocation_values.append((0, 0, {
                    'ro_id': source_ro.id,
                    'ro_date_yyyymmdd': (
                        format_ymondd(fields.Datetime.context_timestamp(source_ro, source_ro.create_date)) if source_ro.create_date else ''
                    ),
                    'delivery_date_yyyymmdd': format_ymondd(delivery_date),
                    'planning_id': plan_id,
                    'kitchen_code': plan.kitchen_code,
                    'product_id': product_id,
                    'reference': source.reference,
                    'store_warehouse_id': store_id,
                    'qty_requested': a['requested'],
                    'qty_surplus': a['surplus'],
                    'qty_allocated': a['allocated'],
                }))
        self.write({
            'line_ids': [(5, 0, 0)] + line_values,
            'source_line_ids': [(5, 0, 0)] + source_line_values,
            'allocation_ids': [(5, 0, 0)] + allocation_values,
            'state': 'preview',
            'ro_count': len(orders), 'kitchen_count': len(included_kitchens),
            'sku_count': len(line_values), 'blocked_count': len(blocked),
            'total_requested': total_requested, 'total_production': total_production,
            'info': (
                'Sumber: %s RO Confirmed / %s dapur / %s kombinasi dapur-SKU '
                '(dasar %s MO). Qty RO %s; Qty Produksi (ROUND UP) %s; '
                'Exceeded Planning Max %s. Draft RO excluded. '
                'This preview creates NO MO, stock moves, or reservations. %s'
            ) % (len(orders), len(included_kitchens), len(line_values),
                 len(line_values), total_requested, total_production, len(blocked),
                 ('EXCEEDS MAX: ' + ', '.join(blocked[:20]))
                 if blocked else 'All within Planning Max.'),
        })
        return self._reopen()



    def action_apply_corrections(self):
        """Commit last-chance RO Qty edits with a reason and recalculate in place."""
        self.ensure_one()
        if not self.env.user.has_group('ya_store_ro.group_ya_packing_admin'):
            raise UserError(_('Only Packing Admin may correct Confirmed RO Qty.'))
        if self.state != 'preview' or not self.source_line_ids:
            raise UserError(_('Calculate consolidation before correcting Qty.'))
        delivery_date = parse_ymondd(self.delivery_date_yyyymmdd)
        lock_ro_slot(self.env.cr, delivery_date, self.slot)
        if self.env['ya.packing.batch'].sudo().search_count([
            ('delivery_date', '=', delivery_date), ('slot', '=', self.slot),
        ]):
            raise UserError(_('Pre Produksi already exists: Qty is locked.'))
        orders = self.selected_ro_ids.exists()
        if not orders or any(ro.state != 'confirmed' or ro.packing_batch_id
                             or ro.delivery_date != delivery_date
                             or ro.slot != self.slot for ro in orders):
            raise UserError(_('RO selection changed. Reopen Packing.'))
        source_ids = {line.id for ro in orders for line in ro.line_ids}
        if {item.ro_line_id.id for item in self.source_line_ids} != source_ids:
            raise UserError(_('RO SKU list changed. Recalculate before correcting Qty.'))
        changed = self.source_line_ids.filtered(
            lambda item: item.new_qty != item.old_qty
        )
        if not changed:
            raise UserError(_('No Qty corrections entered.'))
        for item in self.source_line_ids:
            source = item.ro_line_id
            if (source.ro_id != item.ro_id or source.qty_requested != item.old_qty
                    or source.ro_id not in orders):
                raise UserError(_('RO Qty changed in another session: %s. Recalculate.')
                                % item.reference)
            if item.new_qty < 0:
                raise UserError(_('Qty cannot be negative for SKU %s.') % item.reference)
            if item in changed and not (item.reason or '').strip():
                raise UserError(_('Correction reason required for SKU %s, store %s.')
                                % (item.reference, item.store_warehouse_id.display_name))
        for item in changed:
            item.ro_line_id.with_context(
                packing_qty_correction_reason=item.reason.strip()
            ).write({'qty_requested': item.new_qty})
        return self.action_preview()


    def action_move_to_preproduction(self):
        """Persist consolidated Confirmed RO to Pre Produksi; NO MO here."""
        self.ensure_one()
        if not self.env.user.has_group('ya_store_ro.group_ya_packing_admin'):
            raise UserError(_('Only Packing Admin can move consolidation to Pre Produksi.'))
        try:
            delivery_date = parse_ymondd(self.delivery_date_yyyymmdd)
        except ValueError:
            raise UserError(_('Tanggal Kirim must be YYYY-Mon-DD.'))
        if not self.slot:
            raise UserError(_('Choose Slot.'))

        # Same lock is taken by Confirmed RO correction and RO confirmation.
        lock_ro_slot(self.env.cr, delivery_date, self.slot)
        Batch = self.env['ya.packing.batch']
        if Batch.search_count([
            ('delivery_date', '=', delivery_date), ('slot', '=', self.slot),
        ]):
            raise UserError(_(
                'Pre Produksi already exists for this date and slot. '
                'Return to Pre Produksi list instead.'
            ))

        if any(row.new_qty != row.old_qty for row in self.source_line_ids):
            raise UserError(_('Apply Qty corrections before moving to Pre Produksi.'))
        # Crucial: never use possibly stale preview lines from a modal.
        self.action_preview()
        if self.blocked_count:
            raise UserError(_(
                'Blocked: %s SKU exceed Planning Max. '
                'Correct RO/capacity before generating any MO.'
            ) % self.blocked_count)
        if not self.line_ids or any(line.qty_production <= 0 for line in self.line_ids):
            raise UserError(_('No positive consolidated SKU quantities to produce.'))

        orders = self.selected_ro_ids.exists()
        current_all = self.env['ya.store.ro'].search([
            ('delivery_date', '=', delivery_date),
            ('slot', '=', self.slot), ('state', '=', 'confirmed'),
        ])
        # Final release covers the COMPLETE delivery slot; refuse a partial list.
        if not orders or set(orders.ids) != set(current_all.ids):
            raise UserError(_(
                'Pre Produksi requires ALL Confirmed RO for this delivery date and slot. '
                'Return to the RO list, select all matching Confirmed RO, then consolidate.'
            ))
        # Every allocation from preview must have an originating Confirmed RO.
        for allocation in self.allocation_ids:
            if allocation.ro_id not in orders:
                raise UserError(_('Packing allocation references an RO that is not Confirmed.'))

        line_commands = []
        for row in self.line_ids:
            bom = row.bom_id
            pt = bom.picking_type_id
            if not bom or not pt or not pt.warehouse_id:
                raise UserError(_('Kitchen Manufacturing Operation Type missing: %s') % row.reference)
            if not pt.default_location_src_id or not pt.default_location_dest_id:
                raise UserError(_('Manufacturing stock locations missing for kitchen %s.')
                                % row.kitchen_code)
            expected_warehouse = ' '.join(
                ('Dapur ' + (row.planning_id.workcenter_id.name or '')).casefold().split()
            )
            actual_warehouse = ' '.join(
                (pt.warehouse_id.name or '').casefold().split()
            )
            if expected_warehouse != actual_warehouse:
                raise UserError(_(
                    'MO kitchen routing mismatch for SKU %s: expected %s, got %s.'
                ) % (row.reference, expected_warehouse, actual_warehouse))
            if bom.product_uom_id != row.uom_id:
                raise UserError(_('BoM UoM differs from RO/Planning UoM: %s') % row.reference)
            if (bom.product_id and bom.product_id != row.product_id) or (
                    bom.product_tmpl_id != row.product_id.product_tmpl_id):
                raise UserError(_('BoM product mismatch for SKU %s') % row.reference)
            if int(bom.product_qty) != row.bom_output:
                raise UserError(_('BoM output changed since preview: %s') % row.reference)
            line_commands.append((0, 0, {
                'planning_id': row.planning_id.id,
                'kitchen_code': row.kitchen_code,
                'product_id': row.product_id.id,
                'reference': row.reference,
                'bom_id': bom.id,
                'qty_requested': row.qty_requested,
                'qty_production': row.qty_production,
                'qty_surplus': row.qty_surplus,
                'max_capacity': row.max_capacity,
                'uom_id': row.uom_id.id,
            }))

        # Stage immutable source snapshot. No MO and no stock move here.
        batch = Batch.with_context(ya_create_production_batch=True).create({
            'delivery_date': delivery_date, 'slot': self.slot,
            'ro_ids': [(6, 0, orders.ids)],
            'line_ids': line_commands,
            'staged_by': self.env.user.id,
            'staged_at': fields.Datetime.now(),
            'state': 'pre_production',
        })
        by_key = {(l.planning_id.id, l.product_id.id): l for l in batch.line_ids}
        for allocation in self.allocation_ids:
            key = (allocation.planning_id.id, allocation.product_id.id)
            line = by_key.get(key)
            if not line:
                raise UserError(_('Cannot match store allocation to MO line: %s')
                                % allocation.reference)
            self.env['ya.packing.batch.allocation'].with_context(
                ya_create_production_batch=True
            ).create({
                'batch_id': batch.id, 'line_id': line.id,
                'ro_id': allocation.ro_id.id,
                'kitchen_code': allocation.kitchen_code,
                'reference': allocation.reference,
                'product_id': allocation.product_id.id,
                'store_warehouse_id': allocation.store_warehouse_id.id,
                'qty_requested': allocation.qty_requested,
                'qty_surplus': allocation.qty_surplus,
                'qty_allocated': allocation.qty_allocated,
            })

        orders.sudo().with_context(ya_stage_or_reset_packing=True).write({
            'packing_batch_id': batch.id,
        })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pre Produksi'),
            'res_model': 'ya.packing.batch.line',
            'view_mode': 'list',
            'views': [(self.env.ref(
                'ya_store_ro.view_ya_packing_preproduction_line_list').id, 'list')],
            'domain': [('batch_id', '=', batch.id)],
            'target': 'current',
        }


class YaPackingPreviewLine(models.TransientModel):
    _name = 'ya.packing.preview.line'
    _description = 'Packing Consolidation Preview Kitchen SKU'

    wizard_id = fields.Many2one('ya.packing.preview', required=True, ondelete='cascade')
    planning_id = fields.Many2one('ya.production.planning', readonly=True)
    kitchen_code = fields.Char(readonly=True)
    product_id = fields.Many2one('product.product', readonly=True)
    reference = fields.Char(readonly=True)
    uom_id = fields.Many2one('uom.uom', readonly=True)
    bom_id = fields.Many2one('mrp.bom', readonly=True)
    bom_output = fields.Integer(readonly=True)
    max_capacity = fields.Integer(readonly=True)
    qty_requested = fields.Integer(readonly=True)
    qty_production = fields.Integer(readonly=True)
    qty_surplus = fields.Integer(readonly=True)
    capacity_status = fields.Selection(
        [('ok', 'Within Max'), ('blocked', 'Exceeds Max')], readonly=True,
    )


class YaPackingPreviewAllocation(models.TransientModel):
    _name = 'ya.packing.preview.allocation'
    _description = 'Packing Consolidation Preview Store Allocation'

    wizard_id = fields.Many2one('ya.packing.preview', required=True, ondelete='cascade')
    planning_id = fields.Many2one('ya.production.planning', readonly=True)
    ro_id = fields.Many2one('ya.store.ro', readonly=True)
    ro_date_yyyymmdd = fields.Char(string='Tgl RO (YYYY-Mon-DD)', readonly=True)
    delivery_date_yyyymmdd = fields.Char(string='Tgl Kirim (YYYY-Mon-DD)', readonly=True)
    kitchen_code = fields.Char(readonly=True)
    product_id = fields.Many2one('product.product', readonly=True)
    reference = fields.Char(readonly=True)
    store_warehouse_id = fields.Many2one('stock.warehouse', readonly=True)
    qty_requested = fields.Integer(readonly=True)
    qty_surplus = fields.Integer(readonly=True)
    qty_allocated = fields.Integer(readonly=True)

class YaPackingPreviewSourceLine(models.TransientModel):
    _name = 'ya.packing.preview.source.line'
    _description = 'Packing Last RO Qty Correction Before Pre Produksi'
    _order = 'kitchen_code, reference, store_warehouse_id, id'

    wizard_id = fields.Many2one('ya.packing.preview', required=True, ondelete='cascade')
    ro_line_id = fields.Many2one('ya.store.ro.line', required=True, readonly=True)
    ro_id = fields.Many2one('ya.store.ro', required=True, readonly=True)
    store_warehouse_id = fields.Many2one('stock.warehouse', readonly=True)
    kitchen_code = fields.Char(readonly=True)
    product_id = fields.Many2one('product.product', readonly=True)
    reference = fields.Char(readonly=True)
    old_qty = fields.Integer(string='Qty Confirmed', readonly=True)
    new_qty = fields.Integer(string='Qty Koreksi', required=True)
    reason = fields.Text(string='Alasan Koreksi')
