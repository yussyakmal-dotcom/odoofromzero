"""Preflight new Packing Production OK + standard MO integration (NO DB writes).

Run from repo root:
 python3 script/check_ya_store_ro_source_readonly.py
 python3 script/check_packing_generate_mo_source_readonly_ya.py

This verifies Python syntax, XML shape, and critical guard tokens, but does
NOT substitute for Odoo module upgrade or UI transaction tests.
"""
import ast
from pathlib import Path
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1] / 'addons' / 'ya_store_ro'
checks = {
    'models/packing_batch.py': [
        "_name = 'ya.packing.batch'",
        "UNIQUE(delivery_date, slot)",
        "UNIQUE(batch_id, planning_id, product_id)",
        "UNIQUE(ya_packing_batch_line_id)",
        "_inherit = 'mrp.production'",
        "def unlink(self):",
    ],
    'models/packing_lock.py': ['pg_advisory_xact_lock', 'hashtext'],
    'models/store_ro.py': [
        'lock_ro_slot(self.env.cr, self.delivery_date, self.slot)',
        'lock_ro_slot(self.env.cr, ro.delivery_date, ro.slot)',
        "'ya.packing.batch'",
        "def _compute_production_ok(self):",
    ],
    'wizard/packing_preview.py': [
        'def action_production_ok_generate_mo(self):',
        'lock_ro_slot(self.env.cr, delivery_date, self.slot)',
        'self.action_preview()',
        "if self.blocked_count:",
        "self.env['mrp.production'].create({",
        'mo.action_confirm()',
        "line.with_context(ya_create_production_batch=True).write({'mo_id': mo.id})",
    ],
    'views/packing_batch_views.xml': [
        'view_ya_packing_batch_form', 'mo_id', 'allocation_ids',
        'menu_ya_packing_batch',
    ],
    'views/packing_preview_views.xml': [
        'action_production_ok_generate_mo',
        'Produksi OK + Generate MO',
        'confirm=',
    ],
    'security/ir.model.access.csv': [
        'model_ya_packing_batch',
        'model_ya_packing_batch_line',
        'model_ya_packing_batch_allocation',
    ],
    '__manifest__.py': [
        '19.0.5.1.0',
        'views/packing_batch_views.xml',
        'views/packing_ro_selection_views.xml',
    ],
}
errors = []
for rel, tokens in checks.items():
    p = root / rel
    if not p.is_file():
        errors.append('MISSING FILE: ' + rel)
        continue
    data = p.read_text(encoding='utf8')
    for token in tokens:
        if token not in data:
            errors.append('MISSING SAFETY TOKEN: %s -> %s' % (rel, token))
    try:
        if p.suffix == '.py':
            ast.parse(data, filename=str(p))
        if p.suffix == '.xml':
            ET.parse(p)
    except (SyntaxError, ET.ParseError) as exc:
        errors.append('SOURCE INVALID: %s -> %s' % (rel, exc))
    print('SOURCE_OK:', rel)

manifest = ast.literal_eval((root / '__manifest__.py').read_text(encoding='utf8'))
declared = set(manifest['data'])
for rel in ('views/packing_batch_views.xml', 'views/packing_preview_views.xml'):
    if rel not in declared:
        errors.append('VIEW NOT IN MANIFEST: ' + rel)
print('ERROR_COUNT:', len(errors))
for error in errors:
    print(error)
if errors:
    raise SystemExit(1)
print('PACKING_GENERATE_MO_SOURCE_OK')
