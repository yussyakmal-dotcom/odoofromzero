import base64
import re
import uuid
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from io import BytesIO

from odoo import fields, models, _
from odoo.exceptions import UserError
from ..models.capacity_rules import closest_batch_multiple

try:
    from openpyxl import load_workbook
except ImportError:
    load_workbook = None

PRODUCT_RE = re.compile(r'^\[([^\[\]]+)\]\s+(.+)$')
MAX_BYTES = 10 * 1024 * 1024
MAX_ROWS = 25000


def norm(value):
    return ' '.join(str(value or '').strip().split())


class YaProductionPlanningImport(models.TransientModel):
    _name = 'ya.production.planning.import'
    _description = 'Import Production Capacity XLSX'

    delivery_date = fields.Date(required=True, default=fields.Date.context_today)
    slot = fields.Selection([('S1', 'S1 - 05.00 WIB'),
                             ('S2', 'S2 - 09.00 WIB'),
                             ('S3', 'S3 - 11.00 WIB')], required=True)
    file = fields.Binary(required=True, attachment=False)
    filename = fields.Char()
    state = fields.Selection([('upload', 'Upload'), ('preview', 'Preview')],
                             required=True, default='upload')
    preview_line_ids = fields.One2many('ya.production.planning.import.line', 'wizard_id')
    report = fields.Text(readonly=True)
    errors = fields.Text(readonly=True)
    line_count = fields.Integer(readonly=True)

    def _reopen(self):
        return {'type': 'ir.actions.act_window', 'res_model': self._name,
                'res_id': self.id, 'view_mode': 'form', 'target': 'new'}

    def _parse(self):
        self.ensure_one()
        if not load_workbook:
            raise UserError(_('The openpyxl package is missing.'))
        if not (self.filename or '').lower().endswith('.xlsx'):
            raise UserError(_('Upload a .xlsx file.'))
        try:
            content = base64.b64decode(self.file, validate=True)
        except Exception:
            raise UserError(_('Invalid XLSX upload encoding.'))
        if len(content) > MAX_BYTES or not content.startswith(b'PK'):
            raise UserError(_('Invalid XLSX file or file exceeds 10 MB.'))
        try:
            workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
        except Exception as exc:
            raise UserError(_('Cannot open XLSX: %s') % str(exc))
        errors, parsed, sheet_map = [], [], []
        try:
            if 'info' not in workbook.sheetnames:
                return [], ['Missing info sheet'], []
            info = workbook['info']
            head = tuple(norm(x) for x in next(info.iter_rows(
                min_row=1, max_row=1, max_col=3, values_only=True)))
            if head != ('NO', 'Sheet', 'Code Dapur'):
                errors.append('info!A1:C1 must be NO | Sheet | Code Dapur')
            seen_sheets, seen_codes = set(), set()
            for rownum, cells in enumerate(info.iter_rows(
                    min_row=2, max_col=3, values_only=True), start=2):
                if all(not norm(x) for x in cells):
                    continue
                _, sheet, code = cells
                sheet, code = norm(sheet), norm(code)
                if not sheet or not code:
                    errors.append('info row %s: missing sheet or kitchen code' % rownum)
                    continue
                if sheet in seen_sheets or code in seen_codes:
                    errors.append('info row %s: repeated sheet or kitchen code' % rownum)
                    continue
                seen_sheets.add(sheet)
                seen_codes.add(code)
                if sheet not in workbook.sheetnames:
                    errors.append('info row %s: sheet %s not found' % (rownum, sheet))
                    continue
                sheet_map.append((sheet, code))
            unknown = set(workbook.sheetnames) - {'info'} - seen_sheets
            if unknown:
                errors.append('Unlisted sheets: ' + ', '.join(sorted(unknown)))
            if not sheet_map:
                errors.append('No kitchen sheets listed')
            for sheet, code in sheet_map:
                ws = workbook[sheet]
                header = tuple(norm(x) for x in next(ws.iter_rows(
                    min_row=1, max_row=1, max_col=4, values_only=True)))
                if header != ('DAPUR', 'Product', 'Max', 'Unit'):
                    errors.append('%s: expected DAPUR | Product | Max | Unit' % sheet)
                    continue
                seen_refs, labels = set(), set()
                for rownum, cells in enumerate(ws.iter_rows(
                        min_row=2, max_col=4, values_only=True), start=2):
                    if all(not norm(x) for x in cells):
                        continue
                    if len(parsed) >= MAX_ROWS:
                        errors.append('XLSX exceeds %s rows' % MAX_ROWS)
                        break
                    dapur, product, max_qty, unit = cells
                    dapur, product, unit = norm(dapur), norm(product), norm(unit)
                    if not dapur:
                        errors.append('%s!A%s: DAPUR required' % (sheet, rownum))
                    else:
                        labels.add(dapur)
                    match = PRODUCT_RE.fullmatch(product)
                    if not match:
                        errors.append('%s!B%s: expected [Reference] Product Name' % (sheet, rownum))
                        continue
                    reference, name = match.group(1).strip(), match.group(2).strip()
                    if reference in seen_refs:
                        errors.append('%s!B%s: repeated Reference %s' % (sheet, rownum, reference))
                    seen_refs.add(reference)
                    try:
                        if max_qty is None or norm(max_qty) == '':
                            raise ValueError()
                        value = Decimal(str(max_qty))
                        if not value.is_finite() or value < 0 or value != value.to_integral_value():
                            raise ValueError()
                        if value > 2147483647:
                            raise ValueError()
                    except (ValueError, InvalidOperation):
                        errors.append('%s!C%s: Max must be a nonnegative whole number' % (sheet, rownum))
                        continue
                    if not unit:
                        errors.append('%s!D%s: Unit required' % (sheet, rownum))
                    parsed.append({'sheet': sheet, 'code': code, 'row': rownum,
                                   'dapur': dapur, 'reference': reference,
                                   'name': name, 'max': int(value), 'unit': unit})
                if len(labels) > 1:
                    errors.append('%s: inconsistent DAPUR names' % sheet)
            if not parsed:
                errors.append('No SKU data found')
            return parsed, errors, sheet_map
        finally:
            workbook.close()

    def _validate_master(self, parsed, sheet_map):
        errors, resolved = [], []
        wc_model = self.env['mrp.workcenter'].with_context(active_test=False)
        product_model = self.env['product.product'].with_context(active_test=False)
        uom_model = self.env['uom.uom'].with_context(active_test=False)
        workcenters = defaultdict(list)
        for wc in wc_model.search([('code', 'in', [code for _, code in sheet_map])]):
            workcenters[wc.code].append(wc)
        for _, code in sheet_map:
            matches = workcenters[code]
            if len(matches) != 1 or not matches[0].active:
                errors.append('info: code %s must match exactly one active Work Center' % code)
        product_map = defaultdict(list)
        for product in product_model.search([('default_code', 'in', list({
                r['reference'] for r in parsed}))]):
            product_map[product.default_code].append(product)
        uom_map = defaultdict(list)
        for uom in uom_model.search([('name', 'in', list({
                r['unit'] for r in parsed}))]):
            uom_map[uom.name].append(uom)
        # The spreadsheet's Unit is the finished-good UoM on the BoM header.
        # Warehouse on the BoM must match the DAPUR value in that sheet.
        bom_map = defaultdict(list)
        bom_model = self.env['mrp.bom'].with_context(active_test=False)
        for bom in bom_model.search([('type', '=', 'normal')]):
            if not bom.picking_type_id or not bom.picking_type_id.warehouse_id:
                continue
            warehouse = norm(bom.picking_type_id.warehouse_id.name).casefold()
            key = ('variant', bom.product_id.id) if bom.product_id else (
                'template', bom.product_tmpl_id.id)
            bom_map[(key, warehouse)].append(bom)
        for row in parsed:
            where = '%s!%s' % (row['sheet'], row['row'])
            products = product_map[row['reference']]
            units = uom_map[row['unit']]
            if len(products) != 1 or not products[0].active:
                errors.append('%s: reference %s is missing, ambiguous or inactive' % (
                    where, row['reference']))
                continue
            product = products[0]
            if norm(product.name).casefold() != norm(row['name']).casefold():
                errors.append('%s: product name does not match Odoo for %s' % (
                    where, row['reference']))
            if len(units) != 1:
                errors.append('%s: Unit %s missing or ambiguous' % (where, row['unit']))
                continue
            warehouse = norm(row['dapur']).casefold()
            candidates = (
                bom_map.get((('variant', product.id), warehouse), [])
                + bom_map.get((('template', product.product_tmpl_id.id), warehouse), [])
            )
            if len(candidates) != 1:
                errors.append(
                    '%s: expected exactly one BoM for reference %s at %s; found %s'
                    % (where, row['reference'], row['dapur'], len(candidates)))
                continue
            bom = candidates[0]
            if units[0] != bom.product_uom_id:
                errors.append(
                    '%s: Unit %s differs from BoM output UoM %s (stock UoM: %s)'
                    % (where, row['unit'], bom.product_uom_id.display_name,
                       product.uom_id.display_name))
                continue
            centers = workcenters[row['code']]
            if len(centers) != 1 or not centers[0].active:
                continue
            try:
                adjusted = closest_batch_multiple(row['max'], bom.product_qty)
            except ValueError as exc:
                errors.append('%s: SKU %s: %s' % (where, row['reference'], exc))
                continue
            resolved.append(dict(
                row, requested_max=row['max'], max=adjusted,
                bom_qty=bom.product_qty, bom_id=bom.id,
                adjusted=(row['max'] != adjusted),
                product_id=product.id, uom_id=units[0].id,
                workcenter_id=centers[0].id,
            ))
        return resolved, errors

    def action_validate_preview(self):
        self.ensure_one()
        parsed, errors, sheet_map = self._parse()
        resolved, extra = self._validate_master(parsed, sheet_map)
        errors += extra
        self.preview_line_ids.unlink()
        if errors:
            self.write({'state': 'upload', 'errors': '\n'.join(errors[:250]),
                        'report': '%s validation error(s); showing first 250' % len(errors),
                        'line_count': 0})
            return self._reopen()
        existing = self.env['ya.production.planning'].search([
            ('delivery_date', '=', self.delivery_date),
            ('slot', '=', self.slot),
            ('kitchen_code', 'in', [code for _, code in sheet_map]),
        ])
        existing_by_code = {p.kitchen_code: p for p in existing}
        expected = {'create': [], 'replace': [], 'skip': []}
        for sheet, code in sheet_map:
            plan = existing_by_code.get(code)
            action = ('skip' if plan and plan.state == 'published'
                      else 'replace' if plan else 'create')
            expected[action].append(code)
        lines = [(0, 0, {
            'sheet': r['sheet'], 'kitchen_code': r['code'],
            'source_row': r['row'], 'reference': r['reference'],
            'product_id': r['product_id'], 'requested_max': r['requested_max'],
            'max_capacity': r['max'], 'bom_qty': r['bom_qty'],
            'bom_id': r['bom_id'], 'adjusted': r['adjusted'],
            'uom_id': r['uom_id'], 'workcenter_id': r['workcenter_id'],
        }) for r in resolved]
        adjusted_rows = [
            '%s!%s SKU %s: %s -> %s (BoM %s)' %
            (r['sheet'], r['row'], r['reference'], r['requested_max'],
             r['max'], r['bom_qty']) for r in resolved if r['adjusted']
        ]
        self.write({'preview_line_ids': lines, 'state': 'preview', 'errors': False,
                    'report': (
                        '%s kitchens; %s SKU lines. PREVIEW ONLY.\n'
                        'CREATE Draft: %s\nREPLACE Draft: %s\n'
                        'SKIP Published (unchanged): %s\\n'
                        'MAX BATCH ADJUSTMENTS: %s\\n%s'
                    ) % (len(sheet_map), len(resolved),
                         ', '.join(expected['create']) or '-',
                         ', '.join(expected['replace']) or '-',
                         ', '.join(expected['skip']) or '-',
                         len(adjusted_rows),
                         '\\n'.join(adjusted_rows[:25]) +
                         ('\\n...see preview rows for more changes'
                          if len(adjusted_rows) > 25 else '')),
                    'line_count': len(resolved)})
        return self._reopen()

    def action_save_draft(self):
        self.ensure_one()
        if self.state != 'preview' or not self.preview_line_ids:
            raise UserError(_('Validate & Preview first.'))
        parsed, errors, sheet_map = self._parse()
        resolved, extra = self._validate_master(parsed, sheet_map)
        errors += extra
        frozen = {(r.kitchen_code, r.reference, r.requested_max,
                   r.max_capacity, r.bom_qty, r.bom_id.id,
                   r.uom_id.id, r.product_id.id) for r in self.preview_line_ids}
        current = {(r['code'], r['reference'], r['requested_max'],
                    r['max'], r['bom_qty'], r['bom_id'],
                    r['uom_id'], r['product_id']) for r in resolved}
        if errors or len(resolved) != len(self.preview_line_ids) or frozen != current:
            raise UserError(_('Uploaded file/master changed since Preview; validate again. %s')
                            % '; '.join(errors[:5]))
        grouped = defaultdict(list)
        for row in resolved:
            grouped[row['code']].append(row)
        plan_model = self.env['ya.production.planning']
        existing = plan_model.search([
            ('delivery_date', '=', self.delivery_date),
            ('slot', '=', self.slot),
            ('kitchen_code', 'in', [code for _, code in sheet_map]),
        ])
        existing_by_code = {p.kitchen_code: p for p in existing}
        # The full upload is one atomic transaction. Published records are
        # skipped; only Draft records in this workbook are replaced.
        batch = str(uuid.uuid4())
        result = {'create': [], 'replace': [], 'skip': []}
        for sheet, code in sheet_map:
            rows = grouped[code]
            plan = existing_by_code.get(code)
            if plan and plan.state == 'published':
                result['skip'].append(code)
                continue
            if not rows:
                raise UserError(_('Kitchen %s has no SKU rows') % code)
            lines = [(0, 0, {'product_id': r['product_id'],
                             'reference': r['reference'], 'max_capacity': r['max'],
                             'uom_id': r['uom_id'], 'bom_id': r['bom_id'],
                             'source_sheet': r['sheet'],
                             'source_row': r['row']}) for r in rows]
            vals = {'workcenter_id': rows[0]['workcenter_id'],
                    'upload_filename': self.filename or '', 'import_batch': batch,
                    'line_ids': [(5, 0, 0)] + lines}
            if plan:
                plan.write(vals)
                result['replace'].append(code)
            else:
                plan_model.create(dict(
                    vals, delivery_date=self.delivery_date, slot=self.slot,
                    kitchen_code=code))
                result['create'].append(code)
        message = (
            'Created Draft: %s. Replaced Draft: %s. '
            'Skipped Published (unchanged): %s.'
        ) % (
            ', '.join(result['create']) or '-',
            ', '.join(result['replace']) or '-',
            ', '.join(result['skip']) or '-',
        )
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Production Planning Upload'),
                'message': message,
                'type': 'success',
                'sticky': True,
                'next': {
                    'type': 'ir.actions.act_window',
                    'name': _('Production Planning'),
                    'res_model': 'ya.production.planning',
                    'view_mode': 'list,form',
                    'views': [(False, 'list'), (False, 'form')],
                    'domain': [
                        ('delivery_date', '=', self.delivery_date),
                        ('slot', '=', self.slot),
                    ],
                    'target': 'current',
                },
            },
        }


class YaProductionPlanningImportLine(models.TransientModel):
    _name = 'ya.production.planning.import.line'
    _description = 'Preview Line for Production Planning'
    _order = 'kitchen_code, id'

    wizard_id = fields.Many2one('ya.production.planning.import', required=True,
                                ondelete='cascade')
    sheet = fields.Char(readonly=True)
    kitchen_code = fields.Char(readonly=True)
    source_row = fields.Integer(readonly=True)
    product_id = fields.Many2one('product.product', readonly=True)
    reference = fields.Char(readonly=True)
    requested_max = fields.Integer(string='Excel Max', readonly=True)
    max_capacity = fields.Integer(string='Adjusted Max', readonly=True)
    bom_qty = fields.Float(string='BoM Output Qty', readonly=True)
    adjusted = fields.Boolean(string='Adjusted?', readonly=True)
    bom_id = fields.Many2one('mrp.bom', readonly=True)
    uom_id = fields.Many2one('uom.uom', readonly=True)
    workcenter_id = fields.Many2one('mrp.workcenter', readonly=True)
