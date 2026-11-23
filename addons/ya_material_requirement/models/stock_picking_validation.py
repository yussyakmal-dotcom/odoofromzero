"""Guard native Odoo 19 Validate for YA CDC physical picking transfers ONLY.

No override affects non-YA standard stock.picking records.
The linked YA CDC picking is the authoritative source for the transfer,
which has already been recorded and confirmed in the YA workflow.
Users may reduce native transfer Qty to reflect an actual discrepancy.
No backorder is allowed for these YA transfers.
Strictly test DB.
"""
from collections import defaultdict

from markupsafe import Markup, escape
from odoo import models, _
from odoo.exceptions import UserError
from odoo.tools import float_compare


TEST_DB = 'erp-yussyakmal-mrp-test'


class YaCdcStockPickingValidation(models.Model):
    _inherit = 'stock.picking'

    def _ya_cdc_linked_transfers(self):
        """Discover native YA CDC transfers, read-only, regardless of user ACL.

        Native Inventory warehouse staff may validate a picking even when
        their account does not have the YA Packing Admin group.
        sudo is restricted to reading the link; NO stock write is sudoed.
        """
        if not self:
            return self.browse()
        linked_ids = self.env['ya.cdc.pick.confirmation'].sudo().search([
            ('internal_transfer_id', 'in', self.ids),
        ]).mapped('internal_transfer_id').ids
        return self.filtered(lambda picking: picking.id in linked_ids)

    def _ya_check_cdc_validation(self):
        """Reject zero/overship before native Odoo 19 draft auto-fill runs.

        Odoo 19 stock.picking.button_validate() fills Draft stock.move
        Quantity=Demand if its Quantity was zero. Blocking here prevents a
        phantom transfer for a physically missing SKU. Partial transfers
        are allowed, but their remaining demand must be cancelled rather
        than sent as a backorder, preserving the original YA pick document.
        """
        for picking in self:
            source_doc = self.env['ya.cdc.pick.confirmation'].sudo().search([
                ('internal_transfer_id', '=', picking.id),
                ('state', '=', 'confirmed'),
            ], limit=1)
            if not source_doc or source_doc.internal_transfer_id.id != picking.id:
                raise UserError(_('Missing confirmed YA CDC source document.'))
            source = source_doc.cdc_warehouse_id.lot_stock_id
            dest = source_doc.warehouse_id.lot_stock_id
            if (picking.state in ('done', 'cancel') or
                    picking.company_id.id != source_doc.company_id.id or
                    picking.picking_type_id.id != source_doc.cdc_warehouse_id.int_type_id.id or
                    picking.location_id.id != source.id or
                    picking.location_dest_id.id != dest.id):
                raise UserError(_(
                    'CDC transfer must keep original company, source CDC, '
                    'destination kitchen and Internal Operation Type. '
                    'Check transfer %s.'
                ) % picking.display_name)
            if not picking.move_ids:
                raise UserError(_('CDC Internal Transfer has no product lines.'))
            approved = {
                line.product_id.id: line.picked_qty
                for line in source_doc.line_ids
                if line.picked_qty > 0
            }
            demand_total = defaultdict(float)
            qty_total = defaultdict(float)
            product_names = {}
            missing = []
            excess = []
            invalid = []
            has_positive = False
            for move in picking.move_ids:
                if move.state == 'cancel':
                    continue
                if move.state == 'done':
                    raise UserError(_(
                        'Transfer has a product already Done: %s.'
                    ) % move.product_id.display_name)
                if (move.location_id.id != source.id or move.location_dest_id.id != dest.id):
                    raise UserError(_(
                        'Changed source/destination for %s is not allowed '
                        'in YA CDC transfer.'
                    ) % move.product_id.display_name)
                product = move.product_id
                product_names[product.id] = product.display_name
                demand_total[product.id] += move.product_uom._compute_quantity(
                    move.product_uom_qty, product.uom_id, round=False,
                )
                qty_total[product.id] += move.product_uom._compute_quantity(
                    move.quantity, product.uom_id, round=False,
                )
                rounding = move.product_uom.rounding or 0.00001
                demand = move.product_uom_qty
                qty = move.quantity
                if float_compare(demand, 0, precision_rounding=rounding) < 0 or (
                        float_compare(qty, 0, precision_rounding=rounding) < 0):
                    invalid.append(move.product_id.display_name)
                elif float_compare(qty, 0, precision_rounding=rounding) == 0:
                    if float_compare(demand, 0, precision_rounding=rounding) > 0:
                        missing.append(move.product_id.display_name)
                elif float_compare(
                        qty, demand, precision_rounding=rounding) > 0:
                    excess.append(move.product_id.display_name)
                else:
                    has_positive = True
            approval_errors = []
            for pid in set(demand_total) | set(qty_total):
                product = self.env['product.product'].browse(pid)
                approved_qty = approved.get(pid, 0.0)
                rounding = product.uom_id.rounding or 0.00001
                if (float_compare(demand_total[pid], approved_qty,
                                  precision_rounding=rounding) > 0 or
                        float_compare(qty_total[pid], approved_qty,
                                      precision_rounding=rounding) > 0):
                    approval_errors.append(product_names[pid])
            if approval_errors:
                raise UserError(_(
                    'Qty/Demand exceeds confirmed CDC physical picking or '
                    'uses an unapproved SKU: %s. '
                    'Correct native transfer; never add unauthorized '
                    'Special Transfer quantity during Validate.'
                ) % ', '.join(approval_errors[:15]))
            if invalid:
                raise UserError(_(
                    'CDC transfer has negative Demand/Qty for: %s. '
                    'Correct these lines before Validate.'
                ) % ', '.join(invalid[:15]))
            if missing:
                raise UserError(_(
                    'VALIDATE DIBLOKIR: Qty = 0/kosong sementara Demand > 0 '
                    'untuk: %s. Odoo 19 dapat otomatis mengisi Qty nol '
                    'dengan Demand. Periksa fisik dan hapus baris yang '
                    'benar-benar tidak dikirim dari dokumen transfer, '
                    'atau koreksi bersama admin gudang. '
                    'Data kebutuhan awal tetap tersimpan di Konfirmasi Picking CDC.'
                ) % ', '.join(missing[:15]))
            if excess:
                raise UserError(_(
                    'Qty aktual melebihi Demand untuk: %s. '
                    'Periksa dan sesuaikan Demand/otorisasi Special Transfer '
                    'sebelum Validate.'
                ) % ', '.join(excess[:15]))
            if not has_positive:
                raise UserError(_('Tidak ada Qty positif yang boleh ditransfer.'))

            # Conservative negative-stock guard. Native Odoo can process a
            # manually entered Done Qty without requiring a complete quant
            # reservation. Compare total CDC physical quantities against this
            # transfer plus ALL OTHER outstanding CDC move-line claims, not
            # only stock.quant.free (which already includes this picking's
            # own reservations). Never claim stock in another warehouse.
            Quant = self.env['stock.quant'].sudo()
            MoveLine = self.env['stock.move.line'].sudo()
            for product_id, requested in qty_total.items():
                product = self.env['product.product'].browse(product_id)
                if float_compare(
                        requested, 0.0,
                        precision_rounding=product.uom_id.rounding) <= 0:
                    continue
                domain = [
                    ('product_id', '=', product_id),
                    ('location_id', 'child_of', source.id),
                    ('location_id.usage', '=', 'internal'),
                    ('company_id', '=', picking.company_id.id),
                ]
                physical_quants = Quant.search(domain)
                physical_qty = sum(physical_quants.mapped('quantity'))
                others = MoveLine.search([
                    ('picking_id', '!=', picking.id),
                    ('state', 'not in', ('done', 'cancel')),
                    ('product_id', '=', product_id),
                    ('location_id', 'child_of', source.id),
                    ('company_id', '=', picking.company_id.id),
                    ('quantity', '>', 0),
                ])
                other_claims = sum(
                    line.quantity_product_uom for line in others
                )
                if float_compare(
                        requested + other_claims, physical_qty,
                        precision_rounding=product.uom_id.rounding) > 0:
                    raise UserError(_(
                        'STOK CDC TIDAK CUKUP untuk %(product)s: '
                        'Qty transfer %(qty).3f, komitmen transfer lain '
                        '%(claims).3f, stok fisik CDC %(physical).3f. '
                        'Tidak boleh Validate sampai stok diperbaiki '
                        'atau Qty fisik disesuaikan.'
                    ) % {
                        'product': product.display_name,
                        'qty': requested,
                        'claims': other_claims,
                        'physical': physical_qty,
                    })

    def _ya_check_direct_mr_validation(self):
        """Small Validate guard for NEW MO→native CDC transfers only.

        No custom confirmation document. Physical Qty may be below Demand;
        the gap is cancelled in _action_done (YA no-backorder). All additions
        for Special Transfer must be reflected in native Demand and Qty.
        """
        for picking in self:
            batch = picking.ya_mr_batch_id
            kitchen = picking.ya_mr_kitchen_id
            # A transfer may be validated after the Packing batch leaves
            # production_ok; check its original linkage, not a moving batch
            # status. Creating a NEW transfer still requires confirmed MOs.
            if not batch or not kitchen:
                raise UserError(_(
                    'YA CDC transfer has an invalid MO batch or destination.'
                ))
            company = kitchen.company_id
            cdc = self.env['stock.warehouse'].search([
                ('company_id', '=', company.id), ('code', '=', 'CDC'),
            ])
            if (len(cdc) != 1 or picking.state in ('done', 'cancel') or
                    picking.company_id != company or
                    picking.picking_type_id != cdc.int_type_id or
                    picking.location_id != cdc.lot_stock_id or
                    picking.location_dest_id != kitchen.lot_stock_id):
                raise UserError(_(
                    'Periksa rute CDC → Dapur, perusahaan, dan Operation Type '
                    'pada transfer %s sebelum Validate.'
                ) % picking.display_name)
            if not picking.move_ids:
                raise UserError(_('Internal Transfer CDC tidak memiliki bahan.'))
            quantities = defaultdict(float)
            nonzero = False
            for move in picking.move_ids:
                if move.state == 'cancel':
                    continue
                if (move.state == 'done' or
                        move.location_id != cdc.lot_stock_id or
                        move.location_dest_id != kitchen.lot_stock_id):
                    raise UserError(_(
                        'Baris bahan %s sudah Done atau lokasi berubah.'
                    ) % move.product_id.display_name)
                rounding = move.product_uom.rounding or 0.00001
                demand, qty = move.product_uom_qty, move.quantity
                if float_compare(demand, 0, precision_rounding=rounding) < 0 or (
                        float_compare(qty, 0, precision_rounding=rounding) < 0):
                    raise UserError(_(
                        'Demand/Qty negatif tidak diperbolehkan untuk %s.'
                    ) % move.product_id.display_name)
                if (float_compare(demand, 0,
                                  precision_rounding=rounding) > 0 and
                        float_compare(qty, 0,
                                      precision_rounding=rounding) == 0):
                    raise UserError(_(
                        'VALIDATE DIBLOKIR: Qty = 0 pada %s tetapi Demand '
                        'masih ada. Odoo bisa mengisi Qty nol otomatis. '
                        'Periksa barang dan koreksi/hapus baris yang '
                        'tidak dikirim dahulu.'
                    ) % move.product_id.display_name)
                if float_compare(qty, demand,
                                 precision_rounding=rounding) > 0:
                    raise UserError(_(
                        'Qty > Demand pada %s. Koreksi Demand serta Qty '
                        'dan catat Special Transfer bila diperlukan.'
                    ) % move.product_id.display_name)
                if float_compare(qty, 0,
                                 precision_rounding=rounding) > 0:
                    nonzero = True
                    quantities[move.product_id.id] += (
                        move.product_uom._compute_quantity(
                            qty, move.product_id.uom_id, round=False
                        )
                    )
            if not nonzero:
                raise UserError(_('Tidak ada Qty positif untuk dipindahkan.'))

            # Conservative nonnegative-stock check: include this transfer's
            # total Qty and other outstanding move-line claims, but never
            # subtract this transfer's own reservation a second time.
            Quants = self.env['stock.quant'].sudo()
            MoveLines = self.env['stock.move.line'].sudo()
            for product_id, qty in quantities.items():
                product = self.env['product.product'].browse(product_id)
                physical = sum(Quants.search([
                    ('product_id', '=', product_id),
                    ('company_id', '=', company.id),
                    ('location_id', 'child_of', cdc.lot_stock_id.id),
                    ('location_id.usage', '=', 'internal'),
                ]).mapped('quantity'))
                others = MoveLines.search([
                    ('picking_id', '!=', picking.id),
                    ('state', 'not in', ('done', 'cancel')),
                    ('product_id', '=', product_id),
                    ('company_id', '=', company.id),
                    ('location_id', 'child_of', cdc.lot_stock_id.id),
                    ('quantity', '>', 0),
                ])
                other_claims = sum(
                    line.quantity_product_uom for line in others
                )
                if float_compare(
                        qty + other_claims, physical,
                        precision_rounding=product.uom_id.rounding) > 0:
                    raise UserError(_(
                        'Stok CDC kurang untuk %(product)s. '
                        'Qty %(qty).3f + komitmen lain %(other).3f '
                        '> stok CDC %(physical).3f. Koreksi sebelum Validate.'
                    ) % {
                        'product': product.display_name,
                        'qty': qty,
                        'other': other_claims,
                        'physical': physical,
                    })

    def button_validate(self):
        """Use native Odoo validation for every transfer, with YA-only guards."""
        direct = self.filtered(lambda p: p.ya_mr_batch_id)
        if direct:
            if self.env.cr.dbname != TEST_DB or len(self) != 1:
                raise UserError(_(
                    'Validate direct YA CDC transfers individually on MRP test DB only.'
                ))
            self._ya_check_direct_mr_validation()
            return super(
                YaCdcStockPickingValidation,
                self.with_context(skip_backorder=True),
            ).button_validate()
        linked = self._ya_cdc_linked_transfers()
        if not linked:
            return super().button_validate()
        if self.env.cr.dbname != TEST_DB:
            raise UserError(_('YA CDC validation is allowed on the MRP test DB only.'))
        # Bulk validation mixing YA and ordinary transfers is deliberately
        # blocked: a single context cannot safely impose NO BACKORDER on some
        # transfers but leave the remainder with normal Odoo policy.
        if len(self) != 1:
            raise UserError(_(
                'Validate YA CDC Internal Transfers one document at a time.'
            ))
        self._ya_check_cdc_validation()
        # Native _pre_action_done_hook may propose a backorder wizard. The
        # YA workflow explicitly does not allow backorders; we skip only the
        # backorder wizard while retaining native sanity checks.
        # The _action_done override below enforces cancel_backorder=True even
        # if operation type is configured as create_backorder=always.
        return super(
            YaCdcStockPickingValidation,
            self.with_context(skip_backorder=True),
        ).button_validate()

    def _action_done(self):
        """No backorder on YA CDC only; ordinary pickings are untouched."""
        direct = self.filtered(lambda p: p.ya_mr_batch_id)
        if direct:
            if self.env.cr.dbname != TEST_DB or len(direct) != len(self):
                raise UserError(_(
                    'YA CDC direct transfer must complete separately on test DB.'
                ))
            self._ya_check_direct_mr_validation()
            shortage_notes = {}
            for picking in self:
                shortages = []
                for move in picking.move_ids:
                    if move.state in ('done', 'cancel'):
                        continue
                    if float_compare(
                            move.quantity, move.product_uom_qty,
                            precision_rounding=move.product_uom.rounding) < 0:
                        shortages.append(
                            '%s: Demand %.3f %s, Qty aktual %.3f %s' % (
                                move.product_id.display_name,
                                move.product_uom_qty, move.product_uom.name,
                                move.quantity, move.product_uom.name,
                            )
                        )
                shortage_notes[picking.id] = shortages
            result = super(
                YaCdcStockPickingValidation,
                self.with_context(cancel_backorder=True),
            )._action_done()
            for picking in self:
                if picking.state == 'done' and shortage_notes[picking.id]:
                    picking.message_post(
                        body=Markup('<pre>%s</pre>') % escape(
                            'YA CDC: selisih dikirim tanpa backorder.\n'
                            + '\n'.join(shortage_notes[picking.id])
                        ),
                        subtype_xmlid='mail.mt_note',
                    )
            return result
        linked = self._ya_cdc_linked_transfers()
        if not linked:
            return super()._action_done()
        if self.env.cr.dbname != TEST_DB:
            raise UserError(_('YA CDC stock transfer is test database only.'))
        if len(linked) != len(self):
            raise UserError(_(
                'Do not complete YA CDC and unrelated transfers together.'
            ))
        self._ya_check_cdc_validation()

        shortages = defaultdict(list)
        for picking in self:
            for move in picking.move_ids:
                if move.state in ('cancel', 'done'):
                    continue
                rounding = move.product_uom.rounding or 0.00001
                if float_compare(move.quantity, move.product_uom_qty,
                                 precision_rounding=rounding) < 0:
                    diff = move.product_uom_qty - move.quantity
                    shortages[picking.id].append(
                        '%s: Demand %.3f %s, Qty %.3f %s, selisih %.3f %s' % (
                            move.product_id.display_name,
                            move.product_uom_qty, move.product_uom.name,
                            move.quantity, move.product_uom.name,
                            diff, move.product_uom.name,
                        )
                    )

        # Respect all other native Odoo validation checks, inventory valuation
        # and move-line processing. Force only the no-backorder decision for
        # these YA-linked internal pickings.
        result = super(
            YaCdcStockPickingValidation,
            self.with_context(cancel_backorder=True),
        )._action_done()
        for picking in self:
            if picking.state == 'done' and shortages[picking.id]:
                # Audit discrepancy separately from original confirmed
                # physical CDC picked quantities and DO NOT create a new MO.
                detail = (
                    'YA CDC No Backorder - Selisih Qty Transfer:\n'
                    + '\n'.join(shortages[picking.id])
                    + '\nKekurangan dibatalkan, bukan dibuat Backorder.'
                )
                picking.message_post(
                    body=Markup('<pre>%s</pre>') % escape(detail),
                    subtype_xmlid='mail.mt_note',
                )
        return result
