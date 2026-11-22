"""Static no-DB audit of YA Material Requirement addon; no Odoo import."""
import ast
from pathlib import Path
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1] / 'addons' / 'ya_material_requirement'
required = {
    '__init__.py': ['from . import models'],
    '__manifest__.py': [
        "'version': '19.0.3.0.0'",
        "'ya_store_ro'",
        "'views/material_requirement_views.xml'",
        "'views/material_requirement_batch_views.xml'",
        "'report/cdc_picking_list_report.xml'",
        "'security/ir.model.access.csv'",
    ],
    'models/__init__.py': ['from . import material_requirement',
                           'from . import material_requirement_batch'],
    'models/material_requirement_batch.py': [
        "_inherit = 'ya.packing.batch'",
        "TEST_DB = 'erp-yussyakmal-mrp-test'",
        "def action_mr_refresh(self):",
        "def action_mr_print(self):",
        "def _mr_calculate_wizard(self):",
        "def _mr_store_snapshot(self, wizard):",
        "_name = 'ya.material.requirement.snapshot.line'",
        "Line.search([('batch_id', '=', self.id)]).unlink()",
        "Line.create(values)",
        "if self.env.cr.dbname != TEST_DB:",
        "def _mr_reopen(self):",
    ],
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
        "delivery_date_label = fields.Char(",
        "strftime('%Y-%b-%d')",
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
        'view_ya_material_requirement_wizard_list',
        'action_ya_material_requirement_list',
        'action_ya_material_requirement_form',
        '<field name="view_mode">list,form</field>',
        'AUDIT SAJA',
        'PERINGATAN STOK CDC',
    ],
    'views/material_requirement_batch_views.xml': [
        'view_ya_material_batch_list',
        'view_ya_material_batch_form',
        'action_ya_material_batch',
        'menu_ya_material_requirement',
        'Material Requirement - Batch Produksi OK',
        '<field name="res_model">ya.packing.batch</field>',
        '<field name="view_mode">list,form</field>',
        '<field name="domain">[(\'state\', \'=\', \'production_ok\')]</field>',
        'create="false" edit="false" delete="false"',
        '<header>',
        'name="action_mr_refresh"',
        'name="action_mr_print"',
        'mr_kitchen_line_ids',
        'mr_cdc_line_ids',
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
        'model_ya_material_requirement_snapshot_line',
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
# Persistent model is allowed to update ONLY its own saved report snapshots.
# No stock, purchase, manufacturing, or warehouse operation can be invoked.
batch_source = (root / 'models/material_requirement_batch.py').read_text(encoding='utf-8')
batch_ast = ast.parse(batch_source)
for node in ast.walk(batch_ast):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr in (
                'button_validate', 'action_confirm', 'action_assign',
                '_action_done', 'action_done', '_update_available_quantity',
                'commit', 'sudo'):
            errors.append('UNSAFE BATCH METHOD: %s at line %s' %
                          (node.func.attr, node.lineno))
batch_view = (root / 'views/material_requirement_batch_views.xml').read_text(
    encoding='utf-8')
if batch_view.find('action_ya_material_batch') < 0:
    errors.append('BATCH LIST MISSING')
if '<footer>' in batch_view:
    errors.append('FORM BUTTONS MUST BE IN HEADER, NOT FOOTER')
if '<field name="res_model">ya.material.requirement.wizard</field>' in batch_view:
    errors.append('MENU MUST POINT TO EXISTING PACKING, NOT TRANSIENT WIZARD')
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
