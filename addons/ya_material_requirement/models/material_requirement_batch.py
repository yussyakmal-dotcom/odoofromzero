"""Existing Packing batches are the Material Requirement entrypoint.

Menu -> existing Produksi OK batch LIST -> selected batch FORM -> buttons.
No user-created audit wizard records. Refresh persists only report snapshot lines;
it never changes MOs, stock quants, pickings, transfers or Purchasing.
"""
from odoo import api, fields, models, _
from odoo.exceptions import UserError

TEST_DB = 'erp-yussyakmal-mrp-test'


class YaPackingBatchMaterialRequirement(models.Model):
    _inherit = 'ya.packing.batch'

    mr_kitchen_line_ids = fields.One2many(
        'ya.material.requirement.snapshot.line', 'batch_id',
        string='Kebutuhan Bahan per Dapur', readonly=True,
        domain=[('kind', '=', 'kitchen')],
    )
    mr_cdc_line_ids = fields.One2many(
        'ya.material.requirement.snapshot.line', 'batch_id',
        string='Ringkasan CDC per Bahan', readonly=True,
        domain=[('kind', '=', 'cdc')],
    )
    mr_pick_confirmation_ids = fields.One2many(
        'ya.cdc.pick.confirmation', 'batch_id',
        string='Konfirmasi Picking Fisik CDC', readonly=True,
    )
    mr_pick_confirmation_count = fields.Integer(
        string='Jumlah Dokumen Picking', compute='_compute_mr_pick_count',
    )

    @api.depends('mr_pick_confirmation_ids')
    def _compute_mr_pick_count(self):
        for batch in self:
            batch.mr_pick_confirmation_count = len(batch.mr_pick_confirmation_ids)

    def action_mr_open_pick_confirmations(self):
        """Explicit form action: create once per kitchen, then open existing list.

        Initial MO Qty is last printed Material Requirement snapshot. Actual
        physical Qty may be edited; excess must be documented as Special.
        Never creates or validates a stock.picking / stock.move.
        """
        self.ensure_one()
        self._mr_guard()
        if not self.mr_kitchen_line_ids:
            raise UserError(_('Hitung / Refresh Kebutuhan sebelum konfirmasi picking.'))
        # Never duplicate a kitchen picking document for the same MO batch.
        Confirmation = self.env['ya.cdc.pick.confirmation']
        existing = Confirmation.search([('batch_id', '=', self.id)])
        kitchens = {}
        for line in self.mr_kitchen_line_ids:
            if line.short_max_qty <= 0:
                continue
            if abs(line.short_max_qty - line.short_min_qty) > (
                    line.uom_id.rounding or 0.00001) / 2.0:
                raise UserError(_(
                    'Reservasi dapur membuat Qty Picking List tidak pasti. '
                    'Selesaikan cek reservasi lalu hitung ulang terlebih dahulu.'
                ))
            wh = line.warehouse_id
            kitchens.setdefault(wh.id, []).append(line)
        if not kitchens:
            raise UserError(_('Tidak ada material pada Picking List CDC.'))
        cdc = self.env['stock.warehouse'].search([
            ('company_id', '=', self.line_ids[0].mo_id.company_id.id),
            ('code', '=', 'CDC'),
        ])
        if len(cdc) != 1:
            raise UserError(_('Gudang CDC tidak unik / tidak ditemukan.'))
        for wh_id, lines in sorted(kitchens.items()):
            if existing.filtered(lambda doc: doc.warehouse_id.id == wh_id):
                continue
            Confirmation.with_context(ya_create_cdc_pick_confirmations=True).create({
                'batch_id': self.id,
                'warehouse_id': wh_id,
                'cdc_warehouse_id': cdc.id,
                'line_ids': [(0, 0, {
                    'product_id': line.product_id.id,
                    'uom_id': line.uom_id.id,
                    'requested_qty': line.short_min_qty,
                    'picked_qty': line.short_min_qty,
                }) for line in lines if line.short_min_qty > 0],
            })
        return {
            'type': 'ir.actions.act_window',
            'name': _('Konfirmasi Picking Fisik CDC - %s') % self.name,
            'res_model': 'ya.cdc.pick.confirmation',
            'view_mode': 'list,form',
            'domain': [('batch_id', '=', self.id)],
            'views': [
                (self.env.ref(
                    'ya_material_requirement.view_ya_cdc_pick_confirmation_list'
                ).id, 'list'),
                (self.env.ref(
                    'ya_material_requirement.view_ya_cdc_pick_confirmation_form'
                ).id, 'form'),
            ],
            'target': 'current',
        }

    mr_component_count = fields.Integer(
        string='Kombinasi Dapur-Bahan', compute='_compute_mr_stats',
    )
    mr_product_count = fields.Integer(
        string='Bahan Unik CDC', compute='_compute_mr_stats',
    )
    mr_cdc_shortage_count = fields.Integer(
        string='Bahan CDC Kurang', compute='_compute_mr_stats',
    )
    mr_last_refresh_label = fields.Char(
        string='Terakhir Hitung (YYYY-Mon-DD)',
        compute='_compute_mr_stats',
    )

    @api.depends('mr_kitchen_line_ids', 'mr_cdc_line_ids',
                 'mr_cdc_line_ids.status')
    def _compute_mr_stats(self):
        for batch in self:
            kitchens = batch.mr_kitchen_line_ids
            cdcs = batch.mr_cdc_line_ids
            batch.mr_component_count = len(kitchens)
            batch.mr_product_count = len(cdcs)
            batch.mr_cdc_shortage_count = len(
                cdcs.filtered(lambda item: item.status == 'cdc_short')
            )
            snapshots = (kitchens | cdcs).mapped('create_date')
            newest = max((item for item in snapshots if item), default=False)
            batch.mr_last_refresh_label = (
                fields.Datetime.context_timestamp(
                    batch, newest,
                ).strftime('%Y-%b-%d %H:%M') if newest else ''
            )

    def _mr_guard(self):
        self.ensure_one()
        if self.env.cr.dbname != TEST_DB:
            raise UserError(_('CDC Material Requirement is test DB only.'))
        if not (self.env.user.has_group('mrp.group_mrp_manager') or
                self.env.user.has_group('ya_store_ro.group_ya_packing_admin')):
            raise UserError(_('Access requires MRP Manager / YA Packing Admin.'))
        if self.state != 'production_ok':
            raise UserError(_('Only existing Produksi OK batches can be checked.'))

    def _mr_calculate_wizard(self):
        """Reuse validated MO/CDC calculation engine, hidden from menu/UI."""
        self._mr_guard()
        wizard = self.env['ya.material.requirement.wizard'].create({
            'delivery_date': self.delivery_date,
            'slot': self.slot,
        })
        wizard.action_calculate()
        if wizard.batch_id != self:
            raise UserError(_('Calculated MO batch differs from selected batch.'))
        return wizard

    def _mr_store_snapshot(self, wizard):
        """Save report lines on selected existing batch; never touch its write()."""
        self.ensure_one()
        Line = self.env['ya.material.requirement.snapshot.line']
        values = []
        kitchen_fields = (
            'required_qty', 'on_hand_qty', 'reserved_qty', 'free_qty',
            'short_min_qty', 'short_max_qty', 'status',
        )
        cdc_fields = (
            'required_qty', 'kitchen_count',
            'kitchen_short_min_qty', 'kitchen_short_max_qty',
            'cdc_on_hand_qty', 'cdc_reserved_qty', 'cdc_free_qty',
            'cdc_short_min_qty', 'cdc_short_max_qty', 'status',
        )
        for line in wizard.kitchen_line_ids:
            row = {
                'batch_id': self.id,
                'kind': 'kitchen',
                'warehouse_id': line.warehouse_id.id,
                'product_id': line.product_id.id,
                'uom_id': line.uom_id.id,
            }
            row.update({key: line[key] for key in kitchen_fields})
            values.append(row)
        for line in wizard.cdc_line_ids:
            row = {
                'batch_id': self.id,
                'kind': 'cdc',
                'product_id': line.product_id.id,
                'uom_id': line.uom_id.id,
            }
            row.update({key: line[key] for key in cdc_fields})
            values.append(row)
        if not values:
            raise UserError(_('No MO material components found.'))
        Line.search([('batch_id', '=', self.id)]).unlink()
        Line.create(values)

    def action_mr_refresh(self):
        """One click on the existing selected Packing batch FORM."""
        self.ensure_one()
        wizard = self._mr_calculate_wizard()
        self._mr_store_snapshot(wizard)
        return self._mr_reopen()

    def action_mr_print(self):
        """Print only from existing batch Form; recalculates stock for safety."""
        self.ensure_one()
        self._mr_guard()
        if not self.mr_kitchen_line_ids:
            raise UserError(_('Klik Hitung / Refresh Kebutuhan dahulu.'))
        wizard = self._mr_calculate_wizard()
        return wizard.action_print_picking_list()

    def _mr_reopen(self):
        return {
            'type': 'ir.actions.act_window',
            'name': _('Material Requirement - %s') % self.name,
            'res_model': 'ya.packing.batch',
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref(
                'ya_material_requirement.view_ya_material_batch_form'
            ).id, 'form')],
            'target': 'current',
        }


class YaMaterialRequirementSnapshotLine(models.Model):
    _name = 'ya.material.requirement.snapshot.line'
    _description = 'YA Material Requirement snapshot attached to Packing batch'
    _order = 'kind, warehouse_id, product_id, id'
    _rec_name = 'product_id'

    batch_id = fields.Many2one(
        'ya.packing.batch', required=True, index=True, readonly=True,
        ondelete='cascade',
    )
    kind = fields.Selection(
        [('kitchen', 'Dapur'), ('cdc', 'CDC')],
        required=True, readonly=True, index=True,
    )
    warehouse_id = fields.Many2one('stock.warehouse', readonly=True)
    product_id = fields.Many2one('product.product', readonly=True, required=True)
    uom_id = fields.Many2one('uom.uom', readonly=True, required=True)
    required_qty = fields.Float(string='Kebutuhan MO', readonly=True,
                                digits='Product Unit of Measure')
    on_hand_qty = fields.Float(string='Stok Fisik Dapur', readonly=True,
                               digits='Product Unit of Measure')
    reserved_qty = fields.Float(string='Reservasi Dapur', readonly=True,
                                digits='Product Unit of Measure')
    free_qty = fields.Float(string='Stok Bebas Dapur', readonly=True,
                            digits='Product Unit of Measure')
    short_min_qty = fields.Float(string='Kurang Minimum', readonly=True,
                                 digits='Product Unit of Measure')
    short_max_qty = fields.Float(string='Kurang Maksimum', readonly=True,
                                 digits='Product Unit of Measure')
    kitchen_count = fields.Integer(string='Jumlah Dapur', readonly=True)
    kitchen_short_min_qty = fields.Float(string='Kurang Dapur Min', readonly=True,
                                        digits='Product Unit of Measure')
    kitchen_short_max_qty = fields.Float(string='Kurang Dapur Max', readonly=True,
                                        digits='Product Unit of Measure')
    cdc_on_hand_qty = fields.Float(string='Stok Fisik CDC', readonly=True,
                                   digits='Product Unit of Measure')
    cdc_reserved_qty = fields.Float(string='Reservasi CDC', readonly=True,
                                    digits='Product Unit of Measure')
    cdc_free_qty = fields.Float(string='Stok Bebas CDC', readonly=True,
                                digits='Product Unit of Measure')
    cdc_short_min_qty = fields.Float(string='Kurang CDC Min', readonly=True,
                                     digits='Product Unit of Measure')
    cdc_short_max_qty = fields.Float(string='Kurang CDC Max', readonly=True,
                                     digits='Product Unit of Measure')
    status = fields.Selection([
        ('ready', 'Cukup'),
        ('review', 'Cek Reservasi'),
        ('short', 'Dapur Kurang'),
        ('enough', 'CDC Cukup'),
        ('cdc_short', 'CDC Kurang - Info Gudang'),
    ], readonly=True)
