"""CDC physical picking confirmation per existing Packing batch and kitchen.

Explicit operator action; keeps MO demand separate from Special Transfer.
Confirmed sheets may EXPLICITLY create a single standard stock.picking DRAFT
with native stock.move quantities; no auto-confirm, assign, reserve or validate.
Warehouse must check lot/FEFO, routes and actual availability before validation.
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
    internal_transfer_id = fields.Many2one(
        'stock.picking', string='Internal Transfer Odoo',
        readonly=True, copy=False, ondelete='restrict',
        help='Native Odoo Internal Transfer generated from this confirmed sheet, '
             'created in Draft only; no automatic stock reservation or movement.',
    )
    confirmed_by = fields.Many2one('res.users', readonly=True)
    confirmed_at = fields.Datetime(readonly=True)
    confirmed_at_label = fields.Char(
        string='Waktu Konfirmasi (YYYY-Mon-DD)', compute='_compute_confirm_label')
    info = fields.Text(readonly=True,
        default='Qty Picking Aktual boleh melebihi kebutuhan MO hanya dengan '
                'Special Transfer dan alasan; cantumkan referensi bila ada. '
                'Tambahan tidak menambah Qty MO. '
                'Konfirmasi Qty sendiri tidak membuat transfer. '
                'Sesudah Confirmed, klik Buat Internal Transfer (Draft). '
                'Validasi transfer dilakukan terpisah oleh tim gudang.')

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
        allowed_transfer_link = (
            self.env.context.get('ya_link_cdc_internal_transfer')
            and set(vals) == {'internal_transfer_id'}
            and bool(vals.get('internal_transfer_id'))
            and all(doc.state == 'confirmed' and not doc.internal_transfer_id
                    for doc in self)
        )
        if allowed_transfer_link:
            return super().write(vals)
        if 'internal_transfer_id' in vals:
            raise UserError(_('Internal Transfer link can only be written by its button.'))
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


    def _open_internal_transfer(self):
        """Open Odoo's standard stock.picking form, not a custom transfer UI."""
        self.ensure_one()
        if not self.internal_transfer_id:
            raise UserError(_('No Internal Transfer linked to this picking sheet.'))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Internal Transfer CDC → %s') % self.warehouse_id.display_name,
            'res_model': 'stock.picking',
            'res_id': self.internal_transfer_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_open_internal_transfer(self):
        self.ensure_one()
        _guard_db(self.env)
        _guard_role(self.env)
        return self._open_internal_transfer()

    def action_create_internal_transfer(self):
        """Create ONE native Internal Transfer DRAFT from confirmed physical Qty.

        No confirm/assign/validation, reservation or stock change here.
        Confirmed special excess remains separate from MO demand in the
        immutable CDC picking sheet, with the breakdown also in transfer notes.
        """
        self.ensure_one()
        _guard_db(self.env)
        _guard_role(self.env)
        if not self.env.user.has_group('stock.group_stock_manager'):
            raise UserError(_(
                'Only Inventory Administrator (Stock Manager) may create '
                'a standard Internal Transfer from confirmed CDC picking.'
            ))
        # Serialize double clicks / different sessions for this exact record.
        self.env.cr.execute(
            'SELECT id FROM ya_cdc_pick_confirmation WHERE id = %s FOR UPDATE',
            [self.id],
        )
        self.invalidate_recordset(['internal_transfer_id', 'state'])
        if self.internal_transfer_id:
            return self._open_internal_transfer()
        if self.state != 'confirmed':
            raise UserError(_('Confirm Qty Picking before creating Internal Transfer.'))
        if self.batch_id.state != 'production_ok' or not self.line_ids:
            raise UserError(_('Source Packing batch or confirmed lines are invalid.'))
        cdc, kitchen = self.cdc_warehouse_id, self.warehouse_id
        source, dest = cdc.lot_stock_id, kitchen.lot_stock_id
        if (cdc.code != 'CDC' or cdc == kitchen or
                cdc.company_id != kitchen.company_id or
                self.company_id != cdc.company_id or
                not source or not dest or source == dest or
                source.usage != 'internal' or dest.usage != 'internal'):
            raise UserError(_('Invalid CDC → kitchen locations or company.'))
        picking_type = cdc.int_type_id
        if (not picking_type or picking_type.code != 'internal' or
                picking_type.warehouse_id != cdc or
                picking_type.company_id != self.company_id):
            raise UserError(_(
                'CDC Internal Transfer operation type is missing or mismatched. '
                'Check Warehouse CDC → Operation Types before proceeding.'
            ))
        origin = 'YA-CDC-PICK-%s / %s' % (self.id, self.batch_id.name)
        Picking = self.env['stock.picking'].with_company(self.company_id)
        Move = self.env['stock.move'].with_company(self.company_id)
        # An unlinked native picking with our deterministic origin is NOT safe
        # to adopt: force reconciliation rather than making a second transfer.
        duplicate = Picking.search([
            ('company_id', '=', self.company_id.id),
            ('origin', '=', origin),
        ], limit=1)
        if duplicate:
            raise UserError(_(
                'Native Internal Transfer %s already uses this picking origin. '
                'Reconcile existing transfer and link before creating another.'
            ) % duplicate.display_name)

        # Prevent double transfer of a separately executed Special Transfer.
        # An optional Special reference may name an external REQUEST instead;
        # only references to actual, non-cancelled stock.pickings are blocked.
        for line in self.line_ids:
            ref = (line.special_reference or '').strip()
            if not ref or not line.special_transfer:
                continue
            existing_special = Picking.search([
                ('company_id', '=', self.company_id.id),
                ('state', '!=', 'cancel'),
                '|', ('name', '=', ref), ('origin', '=', ref),
            ], limit=1)
            if existing_special:
                raise UserError(_(
                    'Special Transfer reference %s already belongs to Odoo '
                    'transfer %s. Reconcile it first to avoid double dispatch.'
                ) % (ref, existing_special.display_name))

        # The CDC warehouse lock serializes all transfers created by this
        # feature. Stock may still change via native Odoo operations: the
        # warehouse MUST recheck stock before validating the draft.
        self.env.cr.execute(
            'SELECT id FROM stock_warehouse WHERE id = %s FOR UPDATE',
            [cdc.id],
        )
        pending = self.search([
            ('cdc_warehouse_id', '=', cdc.id),
            ('state', '=', 'confirmed'),
            ('id', '!=', self.id),
        ])
        needed = defaultdict(float)
        for line in self.line_ids:
            if line.picked_qty > 0:
                needed[line.product_id.id] += line.picked_qty
        if not needed:
            raise UserError(_('No positive picked quantities to transfer.'))
        for doc in pending:
            # Count outgoing claims not yet transferred as well as native
            # transfer drafts/waiting/assigned, conservatively. Completed
            # transfers are already deducted from actual stock quantities.
            if doc.internal_transfer_id and doc.internal_transfer_id.state in (
                    'done', 'cancel'):
                continue
            for line in doc.line_ids:
                if line.picked_qty > 0 and line.product_id.id in needed:
                    needed[line.product_id.id] += line.picked_qty
        Quant = self.env['stock.quant'].with_company(self.company_id)
        for product_id, qty in needed.items():
            product = self.env['product.product'].browse(product_id)
            quants = Quant.search([
                ('product_id', '=', product_id),
                ('location_id', 'child_of', source.id),
                ('location_id.usage', '=', 'internal'),
                ('company_id', '=', self.company_id.id),
            ])
            free = max(0.0, sum(
                q.quantity - q.reserved_quantity for q in quants
            ))
            if float_compare(
                    qty, free, precision_rounding=product.uom_id.rounding) > 0:
                raise UserError(_(
                    'CDC available stock insufficient for %(product)s: '
                    'unfulfilled picking claims %(required).3f, '
                    'free CDC stock %(free).3f. Check prior transfers, '
                    'reservations and special transfer Qty.'
                ) % {
                    'product': product.display_name,
                    'required': qty, 'free': free,
                })

        notes = [
            'YA CDC Physical Picking %s' % self.name,
            'Confirmed: %s' % (self.confirmed_at_label or '-'),
            'From %s to %s; original MO Qty is NOT modified.' % (
                cdc.display_name, kitchen.display_name,
            ),
        ]
        move_values = []
        for line in self.line_ids:
            qty = line.picked_qty
            if float_compare(qty, 0.0,
                             precision_rounding=line.uom_id.rounding) <= 0:
                continue
            mo_qty = min(qty, line.requested_qty)
            special_qty = max(0.0, qty - line.requested_qty)
            if float_compare(
                    special_qty, 0.0,
                    precision_rounding=line.uom_id.rounding) <= 0:
                mo_qty, special_qty = qty, 0.0
            if special_qty and (
                    not line.special_transfer or
                    not (line.special_reason or '').strip()):
                raise UserError(_(
                    'Missing Special Transfer authorization for %s.'
                ) % line.product_id.display_name)
            note = '%s: Qty Fisik %s %s; MO %s; Special %s' % (
                line.product_id.display_name,
                qty, line.uom_id.name, mo_qty, special_qty,
            )
            if special_qty:
                note += ' | Alasan: %s' % (line.special_reason or '').strip()
                if line.special_reference:
                    note += ' | Ref: %s' % line.special_reference.strip()
            notes.append(note)
            move_values.append({
                # Odoo 19 stock.move has no 'name' field in the deployed
                # registry. The product is identified by product_id and
                # the detailed MO/Special breakdown stays in picking notes.
                'product_id': line.product_id.id,
                'product_uom': line.uom_id.id,
                'product_uom_qty': qty,
                'location_id': source.id,
                'location_dest_id': dest.id,
                'company_id': self.company_id.id,
            })
        if not move_values:
            raise UserError(_('No transferable positive Qty on confirmation.'))
        # Validate field compatibility BEFORE creating stock.picking, so a
        # future Odoo schema difference fails cleanly with no draft orphans.
        move_fields = set(Move._fields)
        invalid_move_keys = set().union(*(set(row) for row in move_values))
        invalid_move_keys.add('picking_id')
        invalid_move_keys -= move_fields
        if invalid_move_keys:
            raise UserError(_(
                'Stock Move fields unsupported in this Odoo version: %s. '
                'Please contact Odoo administrator before retrying.'
            ) % ', '.join(sorted(invalid_move_keys)))
        picking_vals = {
            'picking_type_id': picking_type.id,
            'location_id': source.id,
            'location_dest_id': dest.id,
            'company_id': self.company_id.id,
            'origin': origin,
        }
        if 'note' in Picking._fields:
            picking_vals['note'] = '\n'.join(notes)
        picking = Picking.create(picking_vals)
        moves = Move.create([
            dict(values, picking_id=picking.id) for values in move_values
        ])
        # Odoo 19: stock.move.quantity is the sum of stock.move.line
        # quantities, and writing it invokes standard native reservation
        # behavior. Feri requested Demand=Qty initial for bulk transfers.
        # Only prefill materials with NO lot/serial tracking and adequate
        # free stock in the EXACT CDC source bin: never invent lot, bin,
        # owner or package and never bypass FEFO. For anything else keep
        # the Qty blank for native warehouse review and lot/bin selection.
        if 'quantity' not in Move._fields:
            raise UserError(_(
                'Odoo stock.move Quantity field is missing. '
                'Internal Transfer was not created; contact administrator.'
            ))
        prefilled = 0
        manual = []
        Quant = self.env['stock.quant'].with_company(self.company_id)
        for move, values in zip(moves, move_values):
            qty = values['product_uom_qty']
            product = move.product_id
            if product.tracking != 'none':
                manual.append(product.display_name)
                continue
            strict_quants = Quant.search([
                ('product_id', '=', product.id),
                ('location_id', '=', source.id),
                ('company_id', '=', self.company_id.id),
                ('lot_id', '=', False),
                ('package_id', '=', False),
                ('owner_id', '=', False),
            ])
            strict_free = sum(max(0.0, q.quantity - q.reserved_quantity)
                              for q in strict_quants)
            if float_compare(
                    qty, strict_free,
                    precision_rounding=product.uom_id.rounding) > 0:
                manual.append(product.display_name)
                continue
            # This writes actual stock.move.line quantity in Odoo 19, which
            # may reserve stock immediately, even while picking is Draft.
            # No action_confirm/assign/validate is called.
            move.write({'quantity': qty})
            if (float_compare(
                    move.quantity, qty,
                    precision_rounding=product.uom_id.rounding) != 0 or
                    move.state != 'draft'):
                raise UserError(_(
                    'Odoo did not preserve Draft Demand=Qty for %s. '
                    'Transaction rolled back; check stock configuration.'
                ) % product.display_name)
            prefilled += 1
        if manual and 'note' in Picking._fields:
            previous_note = picking.note or ''
            picking.note = previous_note + '\\n' + (
                'Qty perlu diisi manual (lot/FEFO/bin/stok): %s'
                % ', '.join(manual)
            )
        self.with_context(ya_link_cdc_internal_transfer=True).write({
            'internal_transfer_id': picking.id,
        })
        # Do not call picking.action_confirm, action_assign or button_validate.
        # Warehouse handles FEFO/lot, reservation, transit route and receipt
        # in Odoo Inventory after reviewing the generated DRAFT.
        return self._open_internal_transfer()


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
