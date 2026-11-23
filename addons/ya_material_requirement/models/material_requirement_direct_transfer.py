"""Simple MO → CDC internal transfer bridge (TEST DB only).

Use the existing confirmed-MO Material Requirement calculator. No new picking
confirmation document, custom transfer model, or custom PDF: Odoo's native
stock.picking is the operational source of truth and prints standard reports.

Historical CDC picking confirmation records remain intact for audit.
"""
from collections import defaultdict

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare


TEST_DB = 'erp-yussyakmal-mrp-test'


class YaMrDirectStockPicking(models.Model):
    _inherit = 'stock.picking'

    ya_mr_batch_id = fields.Many2one(
        'ya.packing.batch', string='YA Material Requirement Batch',
        readonly=True, copy=False, index=True, ondelete='restrict',
    )
    ya_mr_kitchen_id = fields.Many2one(
        'stock.warehouse', string='YA Dapur Tujuan',
        readonly=True, copy=False, index=True,
    )

    _ya_mr_unique_batch_kitchen = models.Constraint(
        'UNIQUE(ya_mr_batch_id, ya_mr_kitchen_id)',
        'An Internal Transfer already exists for this YA batch and kitchen.',
    )


class YaMrDirectBatch(models.Model):
    _inherit = 'ya.packing.batch'

    mr_native_transfer_ids = fields.One2many(
        'stock.picking', 'ya_mr_batch_id',
        string='Internal Transfers Odoo', readonly=True,
    )
    mr_native_transfer_count = fields.Integer(
        string='Jumlah Internal Transfer',
        compute='_compute_mr_native_transfer_count',
    )

    @api.depends('mr_native_transfer_ids',
                 'mr_pick_confirmation_ids.internal_transfer_id')
    def _compute_mr_native_transfer_count(self):
        for batch in self:
            native = batch.mr_native_transfer_ids
            historical = batch.mr_pick_confirmation_ids.mapped(
                'internal_transfer_id')
            batch.mr_native_transfer_count = len(native | historical)

    def _mr_related_native_pickings(self):
        self.ensure_one()
        return (self.mr_native_transfer_ids |
                self.mr_pick_confirmation_ids.mapped('internal_transfer_id'))

    def action_mr_open_native_transfers(self):
        """Existing native Odoo Internal Transfer LIST → selected native FORM."""
        self.ensure_one()
        self._mr_guard()
        pickings = self._mr_related_native_pickings()
        if not pickings:
            raise UserError(_(
                'No existing Internal Transfer for this batch. '
                'Click Buat Internal Transfers Odoo from the batch form.'
            ))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Internal Transfers CDC - %s') % self.name,
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('id', 'in', pickings.ids)],
            'target': 'current',
            'context': {'create': False},
        }

    def action_mr_generate_native_transfers(self):
        """Generate one standard Internal Transfer per kitchen from confirmed MO.

        No CDC picking confirmation record and no custom transfer report.
        Demand = full confirmed-MO raw material requirement for this batch, regardless\n        of kitchen buffer levels, reserved quantities or other outstanding\n        transfers. Qty initially matches Demand for
        available UNTRACKED exact-bin products; stock reservation is native
        Odoo behavior (may show Ready before Validate).
        Never confirm/validate or move any stock in this action.
        """
        self.ensure_one()
        self._mr_guard()
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise UserError(_(
                'Inventory Administrator (Stock Manager) is required to '
                'generate native CDC Internal Transfers.'
            ))
        # Serialize double clicks for the same packing batch.
        self.env.cr.execute(
            'SELECT id FROM ya_packing_batch WHERE id = %s FOR UPDATE',
            [self.id],
        )
        # Respect previously generated transfer documents; never create a
        # second picking from already-issued physical CDC picking.
        historical = self.mr_pick_confirmation_ids
        existing = self.mr_native_transfer_ids
        if existing:
            # A partial/modified transfer set should not be silently
            # regenerated from freshly changed MO net requirements.
            return self.action_mr_open_native_transfers()
        if historical:
            transferred = historical.mapped('internal_transfer_id')
            if transferred:
                return self.action_mr_open_native_transfers()
            raise UserError(_(
                'Batch ini masih memiliki dokumen Konfirmasi Picking CDC '
                'dari alur lama tanpa Internal Transfer. '
                'Periksa/reconcile bersama admin sebelum menggunakan '
                'alur baru tanpa mengganti dokumen yang sudah diterbitkan.'
            ))

        # This protects against double-click creation of the SAME batch document,
        # NOT against legitimate separate transfers or warehouse buffer build-up.
        Picking = self.env['stock.picking']
        origin_prefix = 'YA-MR-%s-CDC-' % self.id
        orphan = Picking.search([
            ('origin', '=like', origin_prefix + '%'),
        ], limit=1)
        if orphan:
            raise UserError(_(
                'Internal Transfer for this SAME batch already exists (%s). '
                'Open that document; create any additional shipment via native SOP.'
            ) % orphan.display_name)

        # Reuse confirmed-MO, kitchen/CDC stock calculation in the existing
        # module; no independent BoM or MO quantity calculations.
        wizard = self._mr_calculate_wizard()
        self._mr_store_snapshot(wizard)
        # Inventory availability and MO reservations are informative only.
        # CDC fulfils issued transfers via native Odoo + warehouse SOP;
        # shortage is NOT a reason to suppress the transfer document.

        cdc = wizard.cdc_warehouse_id
        if not cdc or cdc.code != 'CDC':
            raise UserError(_('CDC warehouse was not found.'))
        source = cdc.lot_stock_id
        operation = cdc.int_type_id
        if (not source or source.usage != 'internal' or
                not operation or operation.code != 'internal' or
                operation.company_id != cdc.company_id or
                operation.warehouse_id != cdc):
            raise UserError(_(
                'CDC stock location or native Internal Transfer '
                'Operation Type is invalid.'
            ))

        grouped = defaultdict(list)
        for line in wizard.kitchen_line_ids:
            qty = line.required_qty
            if float_compare(qty, 0,
                             precision_rounding=line.uom_id.rounding) <= 0:
                continue
            if (line.product_id.uom_id != line.uom_id or
                    (line.product_id.company_id and
                     line.product_id.company_id != cdc.company_id)):
                raise UserError(_(
                    'Invalid product UoM/company for %s.'
                ) % line.product_id.display_name)
            if ('is_storable' in line.product_id._fields and
                    not line.product_id.is_storable):
                raise UserError(_('Non-storable material: %s.')
                                % line.product_id.display_name)
            grouped[line.warehouse_id.id].append(line)
        if not grouped:
            raise UserError(_(
                'Tidak ada kebutuhan bahan dari MO Confirmed untuk ditransfer.'
            ))

        Move = self.env['stock.move'].with_company(cdc.company_id)
        Picking = Picking.with_company(cdc.company_id)
        required_move_fields = {
            'picking_id', 'product_id', 'product_uom', 'product_uom_qty',
            'location_id', 'location_dest_id', 'company_id', 'quantity',
        }
        if not required_move_fields.issubset(Move._fields):
            raise UserError(_(
                'This Odoo version is missing stock.move fields: %s.'
            ) % ', '.join(sorted(required_move_fields - set(Move._fields))))
        Quant = self.env['stock.quant'].with_company(cdc.company_id)
        for wh_id in sorted(grouped):
            kitchen = self.env['stock.warehouse'].browse(wh_id)
            dest = kitchen.lot_stock_id
            if (kitchen == cdc or kitchen.company_id != cdc.company_id or
                    not dest or dest.usage != 'internal' or dest == source):
                raise UserError(_(
                    'Invalid CDC to kitchen destination: %s.'
                ) % kitchen.display_name)
            origin = origin_prefix + (kitchen.code or str(kitchen.id))
            vals = {
                'ya_mr_batch_id': self.id,
                'ya_mr_kitchen_id': kitchen.id,
                'picking_type_id': operation.id,
                'location_id': source.id,
                'location_dest_id': dest.id,
                'company_id': cdc.company_id.id,
                'origin': origin,
            }
            if 'note' in Picking._fields:
                vals['note'] = (
                    'YA MO batch %s | Tanggal Kirim %s | Slot %s | '
                    'CDC → %s. Demand adalah total kebutuhan bahan MO Confirmed, '\n                    'tanpa pemotongan buffer dapur atau outstanding transfer. '
                    'Picking Operations / Delivery Slip gunakan Print '
                    'standar Odoo. Koreksi Qty aktual sebelum Validate; '
                    'Special Transfer tambahan dicatat pada note dan '
                    'Demand/Qty di dokumen standar ini.'
                ) % (self.name,
                     self.delivery_date.strftime('%Y-%b-%d'),
                     self.slot, kitchen.display_name)
            picking = Picking.create(vals)
            move_values = [{
                'picking_id': picking.id,
                'product_id': line.product_id.id,
                'product_uom': line.uom_id.id,
                'product_uom_qty': line.required_qty,
                'location_id': source.id,
                'location_dest_id': dest.id,
                'company_id': cdc.company_id.id,
            } for line in grouped[wh_id]]
            moves = Move.create(move_values)
            move_by_product = {move.product_id.id: move for move in moves}
            if len(move_by_product) != len(move_values):
                raise UserError(_(
                    'Duplicate SKU detected in kitchen transfer. '
                    'No Internal Transfer saved.'
                ))
            for line in grouped[wh_id]:
                product = line.product_id
                qty = line.required_qty
                # No FEFO/lot requirement is enabled by this addon.
                # Tracked/Sublocation material must be reviewed in native UI.
                if product.tracking != 'none':
                    continue
                quants = Quant.search([
                    ('product_id', '=', product.id),
                    ('location_id', '=', source.id),
                    ('company_id', '=', cdc.company_id.id),
                    ('lot_id', '=', False),
                    ('package_id', '=', False),
                    ('owner_id', '=', False),
                ])
                free = sum(
                    max(0.0, q.quantity - q.reserved_quantity)
                    for q in quants
                )
                if float_compare(
                        qty, free,
                        precision_rounding=product.uom_id.rounding) > 0:
                    # Demand is still filled. Warehouse must correct
                    # actual Qty/stock location before native Validate.
                    continue
                move = move_by_product[product.id]
                move.write({'quantity': qty})
                move.invalidate_recordset(['quantity', 'state'])
                if (float_compare(
                        move.quantity, qty,
                        precision_rounding=product.uom_id.rounding) != 0 or
                        move.state in ('done', 'cancel')):
                    raise UserError(_(
                        'Odoo native Qty prefill mismatch for %s. '
                        'No Internal Transfer was saved.'
                    ) % product.display_name)
        return self.action_mr_open_native_transfers()
