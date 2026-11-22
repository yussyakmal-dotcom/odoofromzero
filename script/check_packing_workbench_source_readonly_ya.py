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
        "not self.env.context.get('ya_applied_qty_corrections')",
        'lock_ro_slot(self.env.cr, delivery_date, self.slot)',
        "packing_qty_correction_reason=item.reason.strip()",
        "return self.with_context(ya_applied_qty_corrections=True).action_preview()",
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
        'class="alert alert-danger"',
        'PERINGATAN KAPASITAS!',
        'PRORATA KAPASITAS:',
        'name="accept_shortage"',
        'name="qty_shortage"',
        'decoration-danger="capacity_status == \'blocked\'"',
        'decoration-success="capacity_status == \'ok\'"',
        'invisible="state != \'preview\' or blocked_count == 0"',
        'BLOKIR: Planning Max kurang dari 1 batch BoM.',
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
        "'version': '19.0.8.1.0'",
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
preview_ast = ast.parse(preview, filename='wizard/packing_preview.py')
preview_methods = [
    node for cls in preview_ast.body if isinstance(cls, ast.ClassDef)
    and cls.name == 'YaPackingPreview'
    for node in cls.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    and node.name == 'action_preview'
]
if len(preview_methods) != 1:
    errors.append('MISSING/AMBIGUOUS action_preview METHOD')
else:
    method = preview_methods[0]
    assignments = [
        node for node in ast.walk(method)
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == 'source_line_values'
                for t in node.targets)
    ]
    appends = [
        node for node in ast.walk(method)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr == 'append'
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == 'source_line_values'
    ]
    if len(assignments) != 1 or not appends or not isinstance(assignments[0].value, ast.List):
        errors.append('PREVIEW SOURCE LINE LIST MUST BE INITIALIZED ONCE')
    elif assignments[0].lineno >= min(node.lineno for node in appends):
        errors.append('PREVIEW SOURCE LINE LIST INITIALIZED AFTER FIRST APPEND')

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
