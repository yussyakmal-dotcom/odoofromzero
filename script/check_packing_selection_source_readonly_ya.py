"""Static no-DB preflight for Packing Confirmed RO list -> selected SKU wizard."""
from pathlib import Path
import ast
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1] / 'addons' / 'ya_store_ro'
checks = {
    'models/store_ro.py': (
        'def action_open_packing_selected',
        "'default_selected_ro_ids'",
        "if any(ro.state != 'confirmed' for ro in orders)",
        'Select RO with the SAME Tanggal Kirim and Slot.',
    ),
    'wizard/packing_preview.py': (
        'from odoo import api, fields, models, _',
        'selected_ro_ids = fields.Many2many(',
        'orders = self.selected_ro_ids.exists()',
        'set(orders.ids) != set(current_all.ids)',
        'Produksi OK requires ALL Confirmed RO',
    ),
    'views/packing_ro_selection_views.xml': (
        'action_ya_packing_confirmed_ro',
        'action_open_packing_selected',
        "('state','=','confirmed')",
        'menu_ya_packing_preview',
    ),
    'views/packing_preview_views.xml': (
        'selected_ro_ids',
        'selected_count',
        'action_production_ok_generate_mo',
    ),
    '__manifest__.py': (
        "'version': '19.0.5.1.0'",
        'views/packing_ro_selection_views.xml',
    ),
}
errors = []
for rel, required in checks.items():
    f = root / rel
    if not f.is_file():
        errors.append('MISSING: ' + rel)
        continue
    data = f.read_text(encoding='utf8')
    if f.suffix == '.py':
        try:
            ast.parse(data, filename=str(f))
        except SyntaxError as exc:
            errors.append('SYNTAX %s: %s' % (rel, exc))
    elif f.suffix == '.xml':
        try:
            ET.parse(f)
        except ET.ParseError as exc:
            errors.append('XML %s: %s' % (rel, exc))
    for item in required:
        if item not in data:
            errors.append('TOKEN %s: %s' % (rel, item))
    print('CHECKED:', rel)
# Menu must open selectable Confirmed RO action, never wizard directly.
root_xml = ET.parse(root / 'views/packing_ro_selection_views.xml').getroot()
menus = [n for n in root_xml.iter('menuitem')
         if n.get('id') == 'menu_ya_packing_preview']
if len(menus) != 1 or menus[0].get('action') != 'action_ya_packing_confirmed_ro':
    errors.append('PACKING_MENU_WRONG_ACTION')
print('ERROR_COUNT:', len(errors))
for issue in errors:
    print(issue)
if errors:
    raise SystemExit(1)
print('PACKING_SELECTION_SOURCE_OK')
