"""Read-only source preflight for Confirmed RO -> Pre Produksi -> Produksi OK/MO.

Does not import Odoo, connect to databases, create MO, or mutate records.
"""
import ast
from pathlib import Path
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1] / 'addons' / 'ya_store_ro'
checks = {
    'models/store_ro.py': [
        "packing_batch_id = fields.Many2one(",
        "RO already entered Pre Produksi or Produksi OK.",
        "RO cannot return to Confirmed queue.",
        'ya_stage_or_reset_packing',
        'action_open_packing_selected',
    ],
    'models/packing_batch.py': [
        "('pre_production', 'Pre Produksi')",
        "('production_ok', 'Produksi OK')",
        "state = fields.Selection(related='batch_id.state'",
        'action_generate_selected_mo',
        "Pre Produksi and Produksi OK cannot be deleted.",
        "set(selected.ids) != set(batch.line_ids.ids)",
        "set(current.ids) != set(batch.ro_ids.ids)",
        'lock_ro_slot(self.env.cr, batch.delivery_date, batch.slot)',
        "self.env['mrp.production'].create({",
        "batch.sudo().with_context(ya_release_production_batch=True).write(",
        'mo.action_confirm()',
        "'state': 'production_ok'",
    ],
    'wizard/packing_preview.py': [
        'def action_move_to_preproduction',
        'self.action_preview()',
        "'state': 'pre_production'",
        "orders.sudo().with_context(ya_stage_or_reset_packing=True).write(",
        "'ya_store_ro.view_ya_packing_preproduction_line_list'",
    ],
    'wizard/packing_correction.py': [
        "('packing_batch_id', '=', False)",
        "Pre Produksi / Produksi OK: corrections are closed.",
    ],
    'views/packing_preview_views.xml': [
        'name="action_move_to_preproduction"',
        'Pindahkan ke Pre Produksi',
    ],
    'views/packing_batch_views.xml': [
        'action_ya_packing_preproduction',
        'action_generate_selected_mo',
        'view_ya_packing_preproduction_line_list',
        'menu_ya_packing_preproduction',
    ],
    'views/packing_ro_selection_views.xml': [
        "('packing_batch_id','=',False)",
        "('state','=','confirmed')",
    ],
    '__manifest__.py': [
        "'version': '19.0.6.1.0'",
        "'views/packing_batch_views.xml'",
    ],
}
errors = []
for name, tokens in checks.items():
    path = root / name
    if not path.exists():
        errors.append('MISSING: ' + name)
        continue
    data = path.read_text(encoding='utf8')
    if path.suffix == '.py':
        try:
            parsed = ast.parse(data, filename=str(path))
            if name.endswith('packing_preview.py'):
                imports = {alias.name for node in ast.walk(parsed)
                           if isinstance(node, ast.ImportFrom) and node.module == 'odoo'
                           for alias in node.names}
                if 'api' not in imports:
                    errors.append('IMPORT MISSING: odoo.api')
        except SyntaxError as error:
            errors.append('PYTHON: %s: %s' % (name, error))
    if path.suffix == '.xml':
        try:
            ET.parse(path)
        except ET.ParseError as error:
            errors.append('XML: %s: %s' % (name, error))
    for token in tokens:
        if token not in data:
            errors.append('TOKEN: %s: %s' % (name, token))
    print('SOURCE_CHECK:', name)
wizard = (root / 'wizard/packing_preview.py').read_text(encoding='utf8')
if 'def action_production_ok_generate_mo' in wizard:
    errors.append('WIZARD STILL CREATES MO DIRECTLY')
if 'from odoo import api, fields, models, _' not in wizard:
    errors.append('MISSING API IMPORT')
print('ERROR_COUNT:', len(errors))
for error in errors:
    print(error)
if errors:
    raise SystemExit(1)
print('PACKING_PREPRODUCTION_SOURCE_OK')
