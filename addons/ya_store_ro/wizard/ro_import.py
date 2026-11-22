"""Import a YA_STORE_RO_V1 workbook into Draft Store RO.

Preview is transient. Save is atomic. No stock move, allocation or production.
"""
import base64
from decimal import Decimal, InvalidOperation
from io import BytesIO

from odoo import fields, models, _
from odoo.exceptions import UserError

try:
    from openpyxl import load_workbook
except ImportError:
    load_workbook = None


def cleaned(value):
    return ' '.join(str(value or '').strip().split())


class YaStoreROImport(models.TransientModel):
    _name = 'ya.store.ro.import'
    _description = 'Upload Store RO XLSX'

    file = fields.Binary(required=True, attachment=False)
    filename = fields.Char()
    state = fields.Selection([('upload', 'Upload'), ('preview', 'Preview')],
                             default='upload', required=True)
    planning_id = fields.Many2one('ya.production.planning', readonly=True)
    store_warehouse_id = fields.Many2one('stock.warehouse', readonly=True)
    preview_line_ids = fields.One2many('ya.store.ro.import.line', 'wizard_id')
    report = fields.Text(readonly=True)
    errors = fields.Text(readonly=True)

    def _reopen(self):
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'res_id': self.id, 'view_mode': 'form',
                'views': [(False, 'form')], 'target': 'new'}

    def _read_validated(self):
        self.ensure_one()
        if not load_workbook:
            raise UserError(_('openpyxl is missing.'))
        if not (self.filename or '').lower().endswith('.xlsx'):
            raise UserError(_('Select an XLSX file.'))
        try:
            data = base64.b64decode(self.file, validate=True)
        except (TypeError, ValueError):
            raise UserError(_('Invalid XLSX binary.'))
        if len(data) > 10 * 1024 * 1024 or not data.startswith(b'PK'):
            raise UserError(_('Invalid XLSX or file larger than 10 MB.'))
        try:
            book = load_workbook(BytesIO(data), read_only=True, data_only=True)
        except Exception as exc:
            raise UserError(_('Cannot open XLSX: %s') % exc)
        try:
            if set(book.sheetnames) != {'info', 'RO'}:
                raise UserError(_('Expected exactly two sheets: info and RO.'))
            info_rows = list(book['info'].iter_rows(min_col=1, max_col=2, values_only=True))
            if not info_rows or tuple(cleaned(x) for x in info_rows[0]) != ('Field', 'Value'):
                raise UserError(_('Invalid info header.'))
            props = {}
            for key, value in info_rows[1:]:
                label = cleaned(key)
                if not label:
                    continue
                if label in props:
                    raise UserError(_('Duplicate info key: %s') % label)
                props[label] = value
            if props.get('Template Type') != 'YA_STORE_RO_V1':
                raise UserError(_('Invalid RO Template Type.'))
            try:
                plan_id = int(props['Planning ID'])
                store_id = int(props['Store Warehouse ID'])
            except (ValueError, TypeError, KeyError):
                raise UserError(_('Invalid Planning ID or Store Warehouse ID.'))
            plan = self.env['ya.production.planning'].browse(plan_id).exists()
            store = self.env['stock.warehouse'].browse(store_id).exists()
            if not plan or plan.state != 'published' or not store or not store.active:
                raise UserError(_('Planning must be Published, and store must be active.'))
            expected_info = {
                'Delivery Date': fields.Date.to_string(plan.delivery_date),
                'Slot': plan.slot,
                'Kitchen Code': plan.kitchen_code,
                'Store Code': store.code or '',
                'Store Name': store.name,
            }
            for key, expected in expected_info.items():
                if cleaned(props.get(key)) != cleaned(expected):
                    raise UserError(_('Template info mismatch: %s') % key)
            ws = book['RO']
            header = next(ws.iter_rows(min_row=1, max_row=1, max_col=3, values_only=True))
            if tuple(cleaned(x) for x in header) != ('Reference', 'Nama Produk', 'Qty Pesan'):
                raise UserError(_('Expected Reference | Nama Produk | Qty Pesan.'))
            eligible = {r.reference: r for r in plan.line_ids if r.max_capacity > 0}
            if not eligible:
                raise UserError(_('No published eligible SKU in Planning.'))
            rows = []
            seen = set()
            for row_no, cols in enumerate(ws.iter_rows(min_row=2, max_col=3, values_only=True), 2):
                if all(x is None or cleaned(x) == '' for x in cols):
                    continue
                ref, title, entered = cols
                ref = cleaned(ref)
                if ref in seen or ref not in eligible:
                    raise UserError(_('RO row %s: duplicate or unlisted Reference %s') % (row_no, ref))
                seen.add(ref)
                source = eligible[ref]
                if cleaned(title) != cleaned(source.product_id.name):
                    raise UserError(_('RO row %s: name does not match Published Planning for %s') % (row_no, ref))
                try:
                    qty = Decimal('0') if entered is None or cleaned(entered) == '' else Decimal(str(entered))
                    if not qty.is_finite() or qty < 0 or qty != qty.to_integral_value() or qty > 2147483647:
                        raise ValueError()
                except (InvalidOperation, ValueError):
                    raise UserError(_('RO row %s: Qty Pesan must be a nonnegative whole number.') % row_no)
                rows.append({'reference': ref, 'product_id': source.product_id.id,
                             'uom_id': source.uom_id.id, 'qty_requested': int(qty)})
            if set(eligible) != seen:
                missing = sorted(set(eligible) - seen)
                raise UserError(_('Missing SKU rows from template: %s') % ', '.join(missing[:15]))
            return plan, store, rows
        finally:
            book.close()

    def action_validate_preview(self):
        self.ensure_one()
        if not self.env.user.has_group('mrp.group_mrp_manager'):
            raise UserError(_('Only a Manufacturing Manager can upload RO in this phase.'))
        try:
            plan, store, rows = self._read_validated()
            existing = self.env['ya.store.ro'].search([
                ('planning_id', '=', plan.id),
                ('store_warehouse_id', '=', store.id)], limit=1)
            if existing and existing.state == 'confirmed':
                raise UserError(_('An RO for this store/jadwal is Confirmed; re-upload is blocked.'))
        except UserError as exc:
            self.write({'state': 'upload', 'errors': str(exc), 'report': False})
            return self._reopen()
        self.preview_line_ids.unlink()
        self.write({
            'planning_id': plan.id, 'store_warehouse_id': store.id,
            'preview_line_ids': [(0, 0, row) for row in rows],
            'errors': False, 'state': 'preview',
            'report': '%s SKU rows; total Qty Pesan %s. %s. No RO changes yet.' % (
                len(rows), sum(r['qty_requested'] for r in rows),
                'REPLACE existing Draft' if existing else 'CREATE new Draft'),
        })
        return self._reopen()

    def action_save_draft(self):
        self.ensure_one()
        if not self.env.user.has_group('mrp.group_mrp_manager'):
            raise UserError(_('Only a Manufacturing Manager can save RO in this phase.'))
        if self.state != 'preview' or not self.preview_line_ids:
            raise UserError(_('Run Validate & Preview first.'))
        plan, store, rows = self._read_validated()
        preview = {(r.reference, r.product_id.id, r.uom_id.id, r.qty_requested)
                   for r in self.preview_line_ids}
        current = {(r['reference'], r['product_id'], r['uom_id'], r['qty_requested']) for r in rows}
        if plan != self.planning_id or store != self.store_warehouse_id or preview != current or len(rows) != len(self.preview_line_ids):
            raise UserError(_('Template or Published Planning changed since Preview. Validate again.'))
        model = self.env['ya.store.ro']
        existing = model.search([('planning_id', '=', plan.id),
                                 ('store_warehouse_id', '=', store.id)], limit=1)
        if existing and existing.state != 'draft':
            raise UserError(_('RO already Confirmed; cannot overwrite.'))
        vals = {'source_filename': self.filename or '',
                'line_ids': [(5, 0, 0)] + [(0, 0, row) for row in rows]}
        if existing:
            existing.write(vals)
            ro = existing
        else:
            ro = model.create(dict(vals, planning_id=plan.id,
                                   store_warehouse_id=store.id))
        return {'type': 'ir.actions.act_window',
                'res_model': 'ya.store.ro', 'res_id': ro.id,
                'view_mode': 'form', 'views': [(False, 'form')], 'target': 'current'}


class YaStoreROImportLine(models.TransientModel):
    _name = 'ya.store.ro.import.line'
    _description = 'RO XLSX Preview Line'

    wizard_id = fields.Many2one('ya.store.ro.import', required=True, ondelete='cascade')
    reference = fields.Char(readonly=True)
    product_id = fields.Many2one('product.product', readonly=True)
    uom_id = fields.Many2one('uom.uom', readonly=True)
    qty_requested = fields.Integer(string='Qty Pesan', readonly=True)
