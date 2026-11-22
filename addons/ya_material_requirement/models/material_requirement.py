"""MO Material Requirement diagnostic dashboard, no stock/PO/production writes.

Calculated for Confirmed MOs already released by YA Packing.
Store counts as snapshots in TransientModels ONLY. This first version does NOT
create stock picking, transfer request, stock reservation, or purchase order.
"""
from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError

from .material_rules import shortage_bounds, cdc_shortage_bounds

SLOTS = [('S1', 'S1 - 05.00 WIB'),
         ('S2', 'S2 - 09.00 WIB'),
         ('S3', 'S3 - 11.00 WIB')]

TEST_DB = 'erp-yussyakmal-mrp-test'


def _stock_for_warehouse(env, warehouse, product_ids):
    """Aggregate exact on-hand and all reservations under WH/Stock internal subtree."""
    if not product_ids:
        return {}
    root = warehouse.lot_stock_id
    if not root or root.usage != 'internal':
        raise UserError(_('Warehouse %s has no internal Stock location.')
                        % warehouse.display_name)
    data = defaultdict(lambda: [0.0, 0.0])
    quants = env['stock.quant'].search([
        ('location_id', 'child_of', root.id),
        ('location_id.usage', '=', 'internal'),
        ('company_id', '=', warehouse.company_id.id),
        ('product_id', 'in', list(product_ids)),
    ])
    for quant in quants:
        data[quant.product_id.id][0] += quant.quantity
        data[quant.product_id.id][1] += quant.reserved_quantity
    return data


class YaMaterialRequirementWizard(models.TransientModel):
    _name = 'ya.material.requirement.wizard'
    _description = 'YA Material Requirement - Read Only MO and CDC'

    delivery_date = fields.Date(
        string='Tanggal Kirim', required=True,
        default=lambda self: fields.Date.context_today(self),
    )
    slot = fields.Selection(SLOTS, required=True, default='S1')
    state = fields.Selection(
        [('choose', 'Pilih Jadwal'), ('preview', 'Hasil Audit')],
        required=True, default='choose',
    )
    batch_id = fields.Many2one('ya.packing.batch', readonly=True)
    cdc_warehouse_id = fields.Many2one(
        'stock.warehouse', string='Gudang CDC', readonly=True,
    )
    mo_count = fields.Integer(string='Jumlah MO', readonly=True)
    kitchen_count = fields.Integer(string='Jumlah Dapur', readonly=True)
    raw_move_count = fields.Integer(string='Baris Komponen MO', readonly=True)
    component_count = fields.Integer(
        string='Kombinasi Dapur-Bahan', readonly=True,
    )
    product_count = fields.Integer(string='Bahan Unik CDC', readonly=True)
    need_purchasing_count = fields.Integer(
        string='Bahan Kekurangan di CDC', readonly=True,
    )
    reservation_review_count = fields.Integer(
        string='Bahan Perlu Cek Reservasi', readonly=True,
    )
    info = fields.Text(readonly=True)

    kitchen_line_ids = fields.One2many(
        'ya.material.requirement.kitchen.line', 'wizard_id', readonly=True,
    )
    cdc_line_ids = fields.One2many(
        'ya.material.requirement.cdc.line', 'wizard_id', readonly=True,
    )

    def _reopen(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Material Requirement — Audit MO'),
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref(
                'ya_material_requirement.view_ya_material_requirement_wizard_form'
            ).id, 'form')],
            'target': 'current',
        }

    def action_calculate(self):
        self.ensure_one()
        if self.env.cr.dbname != TEST_DB:
            raise UserError(_(
                'Material Requirement pilot runs on test DB %s only.'
            ) % TEST_DB)
        if not (self.env.user.has_group('mrp.group_mrp_manager') or
                self.env.user.has_group('ya_store_ro.group_ya_packing_admin')):
            raise UserError(_('Manufacturing Manager or YA Packing Admin required.'))
        if not self.delivery_date or not self.slot:
            raise UserError(_('Pilih Tanggal Kirim dan Slot.'))

        batches = self.env['ya.packing.batch'].search([
            ('delivery_date', '=', self.delivery_date),
            ('slot', '=', self.slot),
            ('state', '=', 'production_ok'),
        ])
        if len(batches) != 1:
            raise UserError(_(
                'Exactly one Produksi OK Packing batch required for %s / %s. '
                'Found %s. No stock transfers generated.'
            ) % (self.delivery_date, self.slot, len(batches)))
        batch = batches[0]
        links = batch.line_ids
        if not links or any(not link.mo_id for link in links):
            raise UserError(_('Packing batch is missing released MO links.'))
        mos = links.mapped('mo_id')
        if len(mos) != len(links) or any(mo.state != 'confirmed'
                                       for mo in mos):
            raise UserError(_(
                'Expected distinct MO in Confirmed status only per Packing SKU. '
                'Do not calculate once MO has started, finished, or been cancelled.'
            ))
        companies = mos.mapped('company_id')
        if len(companies) != 1:
            raise UserError(_('MO company mismatch; cannot combine CDC balances.'))
        company = companies[0]
        CDC = self.env['stock.warehouse'].search([
            ('company_id', '=', company.id),
            ('code', '=', 'CDC'),
        ])
        if len(CDC) != 1 or not CDC.lot_stock_id:
            raise UserError(_(
                'Exactly one CDC warehouse with code CDC and internal Stock '
                'location required. Check warehouse mapping first.'
            ))
        cdc = CDC[0]

        requirements = defaultdict(float)
        sources = defaultdict(set)
        warehouses = {}
        product_ids = set()
        move_count = 0
        for mo in mos:
            kitchen = mo.picking_type_id.warehouse_id
            if not kitchen or not kitchen.lot_stock_id or kitchen == cdc:
                raise UserError(_('MO %s missing distinct kitchen warehouse.')
                                % mo.name)
            if kitchen.company_id != company:
                raise UserError(_('MO %s kitchen company differs from MO company.')
                                % mo.name)
            warehouses[kitchen.id] = kitchen
            for move in mo.move_raw_ids:
                if move.state in ('cancel', 'done'):
                    continue
                if not move.product_id:
                    continue
                move_count += 1
                base_qty = move.product_uom._compute_quantity(
                    move.product_uom_qty, move.product_id.uom_id, round=False,
                )
                if base_qty < 0:
                    raise UserError(_('Negative raw component Qty on MO %s.')
                                    % mo.name)
                if not base_qty:
                    continue
                key = (kitchen.id, move.product_id.id)
                requirements[key] += base_qty
                sources[key].add(move.location_id.id)
                product_ids.add(move.product_id.id)
        if not requirements:
            raise UserError(_('No raw component moves in confirmed MOs.'))

        # A raw stock move may be routed from another location; detect it,
        # never silently assume the material must come from kitchen Stock.
        locations = self.env['stock.location']
        for kitchen in warehouses.values():
            children = set(locations.search([
                ('id', 'child_of', kitchen.lot_stock_id.id),
            ]).ids)
            invalid = [
                (key, loc_id)
                for key, locs in sources.items() if key[0] == kitchen.id
                for loc_id in locs if loc_id not in children
            ]
            if invalid:
                key, loc_id = invalid[0]
                raise UserError(_(
                    'MO raw move source is outside %s Stock for product %s: %s. '
                    'Validate kitchen routing first.'
                ) % (kitchen.display_name, key[1],
                     locations.browse(loc_id).complete_name))

        products = self.env['product.product'].browse(sorted(product_ids))
        product_by_id = {p.id: p for p in products}
        snapshots = {
            wh_id: _stock_for_warehouse(self.env, wh, product_ids)
            for wh_id, wh in warehouses.items()
        }
        cdc_stock = _stock_for_warehouse(self.env, cdc, product_ids)

        kitchen_commands = []
        grouped_cdc = defaultdict(lambda: {
            'required': 0.0, 'short_min': 0.0, 'short_max': 0.0,
            'kitchens': set(),
        })
        for (wh_id, product_id), need in sorted(requirements.items()):
            wh = warehouses[wh_id]
            physical, reserved = snapshots[wh_id].get(product_id, (0.0, 0.0))
            phys, free, short_min, short_max = shortage_bounds(
                need, physical, reserved,
            )
            product = product_by_id[product_id]
            if short_max <= 0:
                status = 'ready'
            elif short_min <= 0:
                status = 'review'
            else:
                status = 'short'
            kitchen_commands.append((0, 0, {
                'warehouse_id': wh_id,
                'product_id': product_id,
                'uom_id': product.uom_id.id,
                'required_qty': need,
                'on_hand_qty': physical,
                'reserved_qty': reserved,
                'free_qty': free,
                'short_min_qty': short_min,
                'short_max_qty': short_max,
                'status': status,
            }))
            grp = grouped_cdc[product_id]
            grp['required'] += need
            grp['short_min'] += short_min
            grp['short_max'] += short_max
            grp['kitchens'].add(wh_id)

        cdc_commands = []
        purchasing_count = reservation_review_count = 0
        for product_id, grp in sorted(grouped_cdc.items()):
            product = product_by_id[product_id]
            on_hand, reserved = cdc_stock.get(product_id, (0.0, 0.0))
            free = max(0.0, on_hand - reserved)
            gap_min, gap_max = cdc_shortage_bounds(
                [(grp['short_min'], grp['short_max'])], free,
            )
            if gap_min > 0:
                status = 'purchase'
                purchasing_count += 1
            elif grp['short_max'] > grp['short_min']:
                status = 'review'
                reservation_review_count += 1
            elif grp['short_max'] <= 0:
                status = 'ready'
            else:
                status = 'enough'
            cdc_commands.append((0, 0, {
                'product_id': product_id,
                'uom_id': product.uom_id.id,
                'kitchen_count': len(grp['kitchens']),
                'required_qty': grp['required'],
                'kitchen_short_min_qty': grp['short_min'],
                'kitchen_short_max_qty': grp['short_max'],
                'cdc_on_hand_qty': on_hand,
                'cdc_reserved_qty': reserved,
                'cdc_free_qty': free,
                'purchase_gap_min_qty': gap_min,
                'purchase_gap_max_qty': gap_max,
                'status': status,
            }))

        self.write({
            'state': 'preview',
            'batch_id': batch.id,
            'cdc_warehouse_id': cdc.id,
            'mo_count': len(mos),
            'kitchen_count': len(warehouses),
            'raw_move_count': move_count,
            'component_count': len(requirements),
            'product_count': len(grouped_cdc),
            'need_purchasing_count': purchasing_count,
            'reservation_review_count': reservation_review_count,
            'kitchen_line_ids': [(5, 0, 0)] + kitchen_commands,
            'cdc_line_ids': [(5, 0, 0)] + cdc_commands,
            'info': (
                'READ ONLY — Snapshot stok saat Hitung Kebutuhan. '
                'Kekurangan minimum = kebutuhan - stok fisik dapur; '
                'kekurangan maksimum = kebutuhan - stok bebas dapur. '
                'Selisih menunjukkan reservasi yang harus direkonsiliasi '
                'dengan MO. CDC Free adalah stok bersama semua dapur, '
                'dihitung hanya SEKALI per bahan. Belum membuat permintaan '
                'transfer, picking, reservasi, pembelian, atau mutasi stok. '
                'Periksa lot/FEFO dan transfer masuk sebelum pemenuhan.'
            ),
        })
        return self._reopen()


class YaMaterialRequirementKitchenLine(models.TransientModel):
    _name = 'ya.material.requirement.kitchen.line'
    _description = 'YA Material Requirement per Kitchen and Product'
    _order = 'warehouse_id, product_id'

    wizard_id = fields.Many2one(
        'ya.material.requirement.wizard', required=True, ondelete='cascade',
    )
    warehouse_id = fields.Many2one('stock.warehouse', required=True, readonly=True)
    product_id = fields.Many2one('product.product', required=True, readonly=True)
    uom_id = fields.Many2one('uom.uom', required=True, readonly=True)
    required_qty = fields.Float(string='Kebutuhan MO', readonly=True, digits='Product Unit of Measure')
    on_hand_qty = fields.Float(string='Stok Fisik', readonly=True, digits='Product Unit of Measure')
    reserved_qty = fields.Float(string='Reservasi Total', readonly=True, digits='Product Unit of Measure')
    free_qty = fields.Float(string='Stok Bebas', readonly=True, digits='Product Unit of Measure')
    short_min_qty = fields.Float(string='Kurang Minimum', readonly=True, digits='Product Unit of Measure')
    short_max_qty = fields.Float(string='Kurang Maksimum', readonly=True, digits='Product Unit of Measure')
    status = fields.Selection([
        ('ready', 'Stok Cukup'),
        ('review', 'Cek Reservasi'),
        ('short', 'Stok Dapur Kurang'),
    ], readonly=True)


class YaMaterialRequirementCdcLine(models.TransientModel):
    _name = 'ya.material.requirement.cdc.line'
    _description = 'YA Material Requirement CDC Consolidated Product'
    _order = 'product_id'

    wizard_id = fields.Many2one(
        'ya.material.requirement.wizard', required=True, ondelete='cascade',
    )
    product_id = fields.Many2one('product.product', required=True, readonly=True)
    uom_id = fields.Many2one('uom.uom', required=True, readonly=True)
    kitchen_count = fields.Integer(string='Jumlah Dapur', readonly=True)
    required_qty = fields.Float(string='Total Kebutuhan MO', readonly=True, digits='Product Unit of Measure')
    kitchen_short_min_qty = fields.Float(string='Kekurangan Dapur Min', readonly=True, digits='Product Unit of Measure')
    kitchen_short_max_qty = fields.Float(string='Kekurangan Dapur Max', readonly=True, digits='Product Unit of Measure')
    cdc_on_hand_qty = fields.Float(string='Stok Fisik CDC', readonly=True, digits='Product Unit of Measure')
    cdc_reserved_qty = fields.Float(string='Reservasi CDC', readonly=True, digits='Product Unit of Measure')
    cdc_free_qty = fields.Float(string='Stok Bebas CDC', readonly=True, digits='Product Unit of Measure')
    purchase_gap_min_qty = fields.Float(string='Potensi Kurang CDC Min', readonly=True, digits='Product Unit of Measure')
    purchase_gap_max_qty = fields.Float(string='Potensi Kurang CDC Max', readonly=True, digits='Product Unit of Measure')
    status = fields.Selection([
        ('ready', 'Dapur Cukup'),
        ('enough', 'CDC Berpotensi Cukup'),
        ('review', 'Cek Reservasi'),
        ('purchase', 'CDC Belum Cukup'),
    ], readonly=True)
