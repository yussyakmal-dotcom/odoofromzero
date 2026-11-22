"""Static no-DB audit of YA Material Requirement addon; no Odoo import."""
import ast
from pathlib import Path
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1] / 'addons' / 'ya_material_requirement'
required = {
    '__init__.py': ['from . import models'],
    '__manifest__.py': [
        "'version': '19.0.2.0.0'",
        "'ya_store_ro'",
        "'views/material_requirement_views.xml'",
        "'report/cdc_picking_list_report.xml'",
        "'security/ir.model.access.csv'",
    ],
    'models/__init__.py': ['from . import material_requirement'],
    'models/material_rules.py': [
        'def shortage_bounds(',
        'def cdc_shortage_bounds(',
        'sum(float(row[0]) for row in kitchen_shortages)',
    ],
    'models/material_requirement.py': [
        "TEST_DB = 'erp-yussyakmal-mrp-test'",
        'self.env.cr.dbname != TEST_DB',
        "_name = 'ya.material.requirement.wizard'",
        "_name = 'ya.material.requirement.kitchen.line'",
        "_name = 'ya.material.requirement.cdc.line'",
        "('state', '=', 'production_ok')",
        "any(mo.state != 'confirmed'",
        "move.product_uom._compute_quantity(",
        "move.product_uom_qty",
        "move.product_id.uom_id",
        "mo.move_raw_ids",
        "('code', '=', 'CDC')",
        "quant.quantity",
        "quant.reserved_quantity",
        "('location_id', 'child_of', root.id)",
        'shortage_bounds(',
        'cdc_shortage_bounds(',
        "'kitchen_line_ids': [(5, 0, 0)] + kitchen_commands",
        "'cdc_line_ids': [(5, 0, 0)] + cdc_commands",
        "'cdc_shortage_count': cdc_shortage_count",
        "'cdc_short_min_qty': gap_min",
        "'cdc_short_max_qty': gap_max",
        "status = 'cdc_short'",
        "DI LUAR alur ini",
        "def action_print_picking_list(self):",
        "def _get_print_picking_groups(self):",
        "self.action_calculate()",
        "if self.cdc_shortage_count:",
        "action_report_ya_cdc_picking_list",

    ],
    'views/material_requirement_views.xml': [
        'menu_ya_material_requirement',
        'ya_production_planning.menu_ya_capacity_root',
        'view_ya_material_requirement_wizard_form',
        'Kebutuhan Bahan per Dapur',
        'Ringkasan CDC per Bahan',
        'Hitung / Refresh Kebutuhan',
        'Cetak Picking List CDC (Draft)',
        'AUDIT SAJA',
        'PERINGATAN STOK CDC',
    ],
    'report/cdc_picking_list_report.xml': [
        'action_report_ya_cdc_picking_list',
        'report_ya_cdc_picking_list_document',
        'CDC PICKING LIST',
        'Qty Disiapkan',
        'CEK RESERVASI',
    ],
    'security/ir.model.access.csv': [
        'model_ya_material_requirement_wizard',
        'model_ya_material_requirement_kitchen_line',
        'model_ya_material_requirement_cdc_line',
    ],
}
errors = []
for rel, needles in required.items():
    path = root / rel
    if not path.is_file():
        errors.append('MISSING FILE: '+rel)
        continue
    text = path.read_text(encoding='utf-8')
    for needle in needles:
        if needle not in text:
            errors.append('TOKEN: %s -> %s' % (rel, needle))
    try:
        if path.suffix == '.py':
            ast.parse(text, filename=str(path))
        elif path.suffix == '.xml':
            ET.parse(path)
    except (SyntaxError, ET.ParseError) as exc:
        errors.append('SOURCE_INVALID: %s -> %s' % (rel, exc))
    print('SOURCE_OK:', rel)
model = (root / 'models/material_requirement.py').read_text(encoding='utf-8')
parsed = ast.parse(model)
for node in ast.walk(parsed):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr in ('create', 'unlink', 'button_validate',
                              'action_confirm', 'action_assign', '_action_done',
                              'action_done', 'commit'):
            errors.append('UNSAFE MODEL MUTATION: %s at line %s' %
                          (node.func.attr, node.lineno))
# Only self (the transient wizard) can be written. No picking / MO / stock writes.
for node in ast.walk(parsed):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr == 'write':
            if not isinstance(node.func.value, ast.Name) or node.func.value.id != 'self':
                errors.append('UNSAFE NON-WIZARD WRITE at line %s' % node.lineno)
for needle in ('need_purchasing_count', 'purchase_gap_min_qty',
               'purchase_gap_max_qty', "status = 'purchase'"):
    if needle in model:
        errors.append('UNWANTED PROCUREMENT FIELD IN CDC-ONLY FLOW: '+needle)
print('ERROR_COUNT:', len(errors))
for err in errors:
    print(err)
if errors:
    raise SystemExit(1)
print('MATERIAL_REQUIREMENT_SOURCE_OK')
