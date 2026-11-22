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


    def action_production_ok_generate_mo(self):
        """All-or-nothing RO-only release using standard Odoo manufacturing orders.

        Must recompute from current Confirmed RO under a date/slot mutex.
        Never start any work orders. Odoo standard confirmation establishes
        component requirements; kitchen receipt/availability gate remains next.
        """
        self.ensure_one()
        if not self.env.user.has_group('ya_store_ro.group_ya_packing_admin'):
            raise UserError(_('Only Packing Admin can release Production OK and MO.'))
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
                'Produksi OK already exists for this date and slot. '
                'MO cannot be generated a second time.'
            ))

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
                'Produksi OK requires ALL Confirmed RO for this delivery date and slot. '
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

        # Creating snapshot and MOs happens in the SAME database transaction.
        # Any exception from standard MO create/confirm rolls everything back.
        batch = Batch.with_context(ya_create_production_batch=True).create({
            'delivery_date': delivery_date, 'slot': self.slot,
            'ro_ids': [(6, 0, orders.ids)],
            'line_ids': line_commands,
            'released_by': self.env.user.id,
            'released_at': fields.Datetime.now(),
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

        for line in batch.line_ids.sorted(lambda l: (
                l.kitchen_code or '', l.reference or '', l.id)):
            bom = line.bom_id
            pt = bom.picking_type_id
            if line.qty_production > line.max_capacity:
                raise UserError(_('Qty exceeds Max Planning: %s') % line.reference)
            if not pt.company_id or pt.company_id != self.env.company:
                raise UserError(_(
                    'Manufacturing Operation Type company differs from active company: %s'
                ) % pt.display_name)

            mo = self.env['mrp.production'].create({
                'product_id': line.product_id.id,
                'product_qty': float(line.qty_production),
                'product_uom_id': line.uom_id.id,
                'bom_id': bom.id,
                'picking_type_id': pt.id,
                'location_src_id': pt.default_location_src_id.id,
                'location_dest_id': pt.default_location_dest_id.id,
                'company_id': pt.company_id.id,
                'date_start': fields.Datetime.now(),
                'origin': '%s / %s / %s' % (
                    batch.name, line.kitchen_code, line.reference,
                ),
                'ya_packing_batch_line_id': line.id,
            })
            mo.action_confirm()  # Standard Odoo: component requirements, NOT production start.
            if mo.state in ('draft', 'cancel', 'done'):
                raise UserError(_('MO %s confirmation failed for SKU %s.')
                                % (mo.display_name, line.reference))
            line.with_context(ya_create_production_batch=True).write({'mo_id': mo.id})

        if len(batch.line_ids) != len(batch.line_ids.mapped('mo_id')):
            raise UserError(_('Not all expected MO were created; release cancelled.'))
        if sum(batch.allocation_ids.mapped('qty_allocated')) != sum(
                batch.line_ids.mapped('qty_production')):
            raise UserError(_('Final allocation does not equal total production.'))

        # Batch exists and all MOs confirmed; status Produksi OK is derived
        # from this immutable, committed release, never from manual flag change.
        return {
            'type': 'ir.actions.act_window',
            'name': _('Produksi OK'),
            'res_model': 'ya.packing.batch', 'res_id': batch.id,
            'view_mode': 'form', 'views': [(False, 'form')],
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
