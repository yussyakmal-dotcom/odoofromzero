"""Pure, read-only source guards for Packing's last Confirmed-RO correction.

No Odoo imports, database access, or mutations. Run:
    python3 script/check_packing_correction_source_readonly_ya.py
"""
import ast
import pathlib
import xml.etree.ElementTree as ET

root = pathlib.Path(__file__).resolve().parents[1] / 'addons' / 'ya_store_ro'
checks = {
    'models/store_ro.py': [
        'group_ya_packing_admin', 'packing_qty_correction_reason',
        'ya.store.ro.qty.audit', 'qty_before', 'qty_after',
        'production_ok', 'Only Packing Admin may edit Confirmed Qty',
    ],
    'wizard/packing_correction.py': [
        'group_ya_packing_admin', 'reason', 'action_apply',
        "('state', '=', 'confirmed')", 'production_ok',
    ],
    'security/packing_groups.xml': ['group_ya_packing_admin'],
    'security/ir.model.access.csv': [
        'model_ya_packing_qty_correction',
        'model_ya_store_ro_qty_audit',
    ],
    'views/packing_correction_views.xml': [
        'action_ya_packing_qty_correction', 'menu_ya_packing_qty_correction',
    ],
    '__manifest__.py': [
        'security/packing_groups.xml',
        'views/packing_correction_views.xml',
    ],
}
errors = []
for relative, tokens in checks.items():
    path = root / relative
    if not path.is_file():
        errors.append('MISSING ' + relative)
        continue
    data = path.read_text(encoding='utf-8')
    try:
        if path.suffix == '.py':
            ast.parse(data, filename=str(path))
        if path.suffix == '.xml':
            ET.fromstring(data)
    except (SyntaxError, ET.ParseError) as exc:
        errors.append('INVALID SOURCE %s: %s' % (relative, exc))
    for token in tokens:
        if token not in data:
            errors.append('MISSING TOKEN %s: %s' % (relative, token))
    print('SOURCE_CHECKED:', relative)

manifest = ast.literal_eval((root / '__manifest__.py').read_text(encoding='utf-8'))
print('ADDON_VERSION:', manifest.get('version'))
print('ERROR_COUNT:', len(errors))
for issue in errors:
    print(issue)
if errors:
    raise SystemExit(1)
print('PACKING_CORRECTION_SOURCE_OK')
