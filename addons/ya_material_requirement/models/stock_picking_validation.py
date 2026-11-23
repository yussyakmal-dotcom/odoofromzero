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

    def button_validate(self):
        """Use Odoo native validation; prevent unwanted zero auto-fill/backorder."""
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
        """Cancel YA CDC shortages without a backorder; no global policy change."""
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
