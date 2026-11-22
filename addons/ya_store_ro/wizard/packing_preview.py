"""Read-only Packing consolidation preview for one Published kitchen/date/slot.

No MO, transfer, stock reservation, or persistent consolidated document is made.
Only confirmed RO records are included; Drafts are excluded.
"""
from collections import defaultdict

from odoo import fields, models, _
from odoo.exceptions import UserError

from ..models.allocation_rules import allocate_surplus_prorata


class YaPackingPreview(models.TransientModel):
    _name = 'ya.packing.preview'
    _description = 'YA Packing RO-only Consolidation Preview'

    planning_id = fields.Many2one(
        'ya.production.planning', string='Published Planning', required=True,
        domain=[('state', '=', 'published')],
    )
    ro_count = fields.Integer(readonly=True)
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
        plan = self.planning_id
        if not plan or plan.state != 'published':
            raise UserError(_('Choose one Published Planning.'))
        orders = self.env['ya.store.ro'].search([
            ('planning_id', '=', plan.id), ('state', '=', 'confirmed'),
        ])
        if not orders:
            raise UserError(_('No Confirmed RO for this kitchen, date and slot.'))

        # One Confirmed RO per store + Planning by SQL constraint.
        store_ids = orders.mapped('store_warehouse_id').ids
        if len(store_ids) != len(orders):
            raise UserError(_('Duplicate store RO detected; abort consolidation.'))

        by_product = defaultdict(dict)
        plan_lines = {line.product_id.id: line for line in plan.line_ids
                      if line.max_capacity > 0}
        for ro in orders:
            for order_line in ro.line_ids:
                if order_line.qty_requested < 0:
                    raise UserError(_('RO Qty cannot be negative.'))
                if order_line.product_id.id not in plan_lines:
                    raise UserError(_('Confirmed RO has SKU not in eligible Published Planning: %s')
                                    % order_line.reference)
                if order_line.uom_id != plan_lines[order_line.product_id.id].uom_id:
                    raise UserError(_('RO SKU UoM disagrees with Planning: %s')
                                    % order_line.reference)
                if order_line.qty_requested:
                    by_product[order_line.product_id.id][ro.store_warehouse_id.id] = (
                        order_line.qty_requested
                    )

        if not by_product:
            raise UserError(_('All Confirmed RO quantities are zero.'))

        line_values = []
        alloc_values = []
        blocked = []
        total_requested = total_production = 0
        for product_id in sorted(by_product, key=lambda p: (plan_lines[p].reference, p)):
            source = plan_lines[product_id]
            bom = source._capacity_bom()
            batch = bom.product_qty
            if batch <= 0 or int(batch) != batch:
                raise UserError(_('SKU %s has non-integer BoM output %s; cannot consolidate.')
                                % (source.reference, batch))
            requests = by_product[product_id]
            produced, allocations = allocate_surplus_prorata(requests, int(batch))
            requested = sum(requests.values())
            surplus = produced - requested
            is_blocked = produced > source.max_capacity
            if is_blocked:
                blocked.append(source.reference)
            total_requested += requested
            total_production += produced
            line_values.append((0, 0, {
                'product_id': product_id, 'reference': source.reference,
                'uom_id': source.uom_id.id, 'bom_id': bom.id,
                'bom_output': int(batch), 'max_capacity': source.max_capacity,
                'qty_requested': requested, 'qty_production': produced,
                'qty_surplus': surplus,
                'capacity_status': 'blocked' if is_blocked else 'ok',
            }))
            for store_id in sorted(allocations):
                row = allocations[store_id]
                alloc_values.append((0, 0, {
                    'product_id': product_id, 'reference': source.reference,
                    'store_warehouse_id': store_id,
                    'qty_requested': row['requested'],
                    'qty_surplus': row['surplus'],
                    'qty_allocated': row['allocated'],
                }))
        # Preview is a scratchpad only. Recompute on every click, never modify RO.
        self.write({
            'line_ids': [(5, 0, 0)] + line_values,
            'allocation_ids': [(5, 0, 0)] + alloc_values,
            'state': 'preview', 'ro_count': len(orders),
            'sku_count': len(line_values), 'blocked_count': len(blocked),
            'total_requested': total_requested,
            'total_production': total_production,
            'info': (
                'RO-only preview: %s Confirmed RO; %s SKU; requested %s; '
                'rounded-up production %s; capacity exceptions %s. '
                'SO, MO, internal transfer and stock are NOT processed. %s'
            ) % (
                len(orders), len(line_values), total_requested,
                total_production, len(blocked),
                ('BLOCKED SKUs: ' + ', '.join(blocked[:20]))
                if blocked else 'Capacity preview OK.',
            ),
        })
        return self._reopen()


class YaPackingPreviewLine(models.TransientModel):
    _name = 'ya.packing.preview.line'
    _description = 'Packing Consolidation Preview SKU'

    wizard_id = fields.Many2one('ya.packing.preview', required=True, ondelete='cascade')
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
        [('ok', 'Within Max'), ('blocked', 'Exceeds Max')],
        readonly=True,
    )


class YaPackingPreviewAllocation(models.TransientModel):
    _name = 'ya.packing.preview.allocation'
    _description = 'Packing Consolidation Preview Store Allocation'

    wizard_id = fields.Many2one('ya.packing.preview', required=True, ondelete='cascade')
    product_id = fields.Many2one('product.product', readonly=True)
    reference = fields.Char(readonly=True)
    store_warehouse_id = fields.Many2one('stock.warehouse', readonly=True)
    qty_requested = fields.Integer(readonly=True)
    qty_surplus = fields.Integer(readonly=True)
    qty_allocated = fields.Integer(readonly=True)
