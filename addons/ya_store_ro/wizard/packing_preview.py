"""RO-only Packing Preview: all Confirmed store RO for a delivery date and slot.

Group per kitchen + SKU. Each group becomes the BASIS for one eventual MO.
Read-only for all persistent business documents; no MO or stock move here.
"""
from collections import defaultdict

from odoo import fields, models, _
from odoo.exceptions import UserError

from ..models.allocation_rules import allocate_surplus_prorata

SLOTS = [('S1', 'S1 - 05.00 WIB'), ('S2', 'S2 - 09.00 WIB'),
         ('S3', 'S3 - 11.00 WIB')]


class YaPackingPreview(models.TransientModel):
    _name = 'ya.packing.preview'
    _description = 'YA Packing RO-only Consolidation Preview'

    delivery_date = fields.Date(string='Tanggal Kirim', required=True,
                                default=fields.Date.context_today)
    slot = fields.Selection(SLOTS, string='Slot Pengiriman', required=True)
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
        if not self.env.user.has_group('mrp.group_mrp_manager'):
            raise UserError(_('Only a Manufacturing Manager may preview Packing consolidation.'))
        if not self.delivery_date or not self.slot:
            raise UserError(_('Select Tanggal Kirim and Slot Pengiriman.'))

        # Critical: start from CONFIRMED RO (all stores and kitchens), never
        # from PPIC Planning list. No Draft RO participates.
        orders = self.env['ya.store.ro'].search([
            ('delivery_date', '=', self.delivery_date),
            ('slot', '=', self.slot),
            ('state', '=', 'confirmed'),
        ])
        if not orders:
            raise UserError(_('No Confirmed RO for the selected delivery date and slot.'))

        # Group by Published Planning ID and SKU ID. One Planning = one kitchen
        # for date+slot by the Planning unique DB constraint.
        by_group = defaultdict(dict)
        planning_lines = {}
        included_kitchens = set()
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
                allocation_values.append((0, 0, {
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
    kitchen_code = fields.Char(readonly=True)
    product_id = fields.Many2one('product.product', readonly=True)
    reference = fields.Char(readonly=True)
    store_warehouse_id = fields.Many2one('stock.warehouse', readonly=True)
    qty_requested = fields.Integer(readonly=True)
    qty_surplus = fields.Integer(readonly=True)
    qty_allocated = fields.Integer(readonly=True)
