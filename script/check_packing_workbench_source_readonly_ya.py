"""Source-only safety check: one Packing entry, inline Qty + audit, Pre Produksi -> MO.

This is a static source check, NOT an Odoo upgrade or end-to-end test.
"""
import ast
from pathlib import Path
import xml.etree.ElementTree as ET

addon = Path(__file__).resolve().parents[1] / 'addons' / 'ya_store_ro'
files = {
    'wizard/packing_preview.py': [
        'from odoo import api, fields, models, _',
        'source_line_ids = fields.One2many(',
        'class YaPackingPreviewSourceLine(models.TransientModel):',
        'def action_apply_corrections(self):',
        'lock_ro_slot(self.env.cr, delivery_date, self.slot)',
        "packing_qty_correction_reason=item.reason.strip()",
        "return self.action_preview()",
        'def action_move_to_preproduction(self):',
        "if any(row.new_qty != row.old_qty for row in self.source_line_ids)",
    ],
    'views/packing_preview_views.xml': [
        'Koreksi Qty RO - Sebelum Pre Produksi',
        'name="source_line_ids"',
        'name="new_qty"',
        'name="reason"',
        'name="action_apply_corrections"',
        'Simpan Koreksi Qty + Recalculate',
        'name="action_move_to_preproduction"',
    ],
    'security/ir.model.access.csv': [
        'model_ya_packing_preview_source_line',
    ],
    'views/packing_ro_selection_views.xml': [
        'name="action_open_packing_selected"',
        'name="action_open_packing_preproduction"',
        'name="action_open_packing_done"',
    ],
    'models/store_ro.py': [
        "def action_open_packing_preproduction(self, *args, **kwargs):",
        "def action_open_packing_done(self, *args, **kwargs):",
        'RO already entered Pre Produksi or Produksi OK.',
    ],
    'models/packing_batch.py': [
        'def action_generate_selected_mo(self, *args, **kwargs):',
        "self.env['mrp.production'].create({",
        'mo.action_confirm()',
        "'state': 'production_ok'",
    ],
    'views/packing_batch_views.xml': [
        'action_open_packing_queue',
        'action_open_packing_preproduction',
        'action_open_packing_done',
        'name="action_generate_selected_mo"',
        '<field name="active" eval="False"/>',
    ],
    '__manifest__.py': [
        "'version': '19.0.7.0.0'",
    ],
}
errors = []
for name, tokens in files.items():
    path = addon / name
    if not path.is_file():
        errors.append('MISSING: ' + name)
        continue
    body = path.read_text(encoding='utf8')
    for token in tokens:
        if token not in body:
            errors.append('MISSING TOKEN: ' + name + ' -> ' + token)
    if path.suffix == '.py':
        try:
            ast.parse(body, filename=str(path))
        except SyntaxError as exc:
            errors.append('PYTHON: %s: %s' % (name, exc))
    if path.suffix == '.xml':
        try:
            ET.parse(path)
        except ET.ParseError as exc:
            errors.append('XML: %s: %s' % (name, exc))
    print('SOURCE_CHECK:', name)
preview = (addon / 'wizard/packing_preview.py').read_text(encoding='utf8')
if "self.env['mrp.production'].create({" in preview:
    errors.append('PREVIEW MUST NOT CREATE MO')
if 'def action_production_ok_generate_mo' in preview:
    errors.append('DIRECT MO BUTTON STILL PRESENT')
menu = ET.parse(addon / 'views/packing_ro_selection_views.xml').getroot()
entry = [x for x in menu.iter('menuitem')
         if x.get('id') == 'menu_ya_packing_preview']
if len(entry) != 1 or entry[0].get('action') != 'action_ya_packing_confirmed_ro':
    errors.append('PACKING ENTRY MENU MUST OPEN CONFIRMED RO QUEUE')
print('ERROR_COUNT:', len(errors))
for err in errors:
    print(err)
if errors:
    raise SystemExit(1)
print('PACKING_WORKBENCH_SOURCE_OK')
