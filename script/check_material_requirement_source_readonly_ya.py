"""Static no-DB audit of YA Material Requirement addon; no Odoo import."""
import ast
from pathlib import Path
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1] / 'addons' / 'ya_material_requirement'
required = {
    '__init__.py': ['from . import models'],
    '__manifest__.py': [
        "'version': '19.0.5.0.1'",
        "'ya_store_ro'",
        "'views/material_requirement_views.xml'",
        "'views/material_requirement_batch_views.xml'",
        "'views/cdc_pick_confirmation_views.xml'",
        "'report/cdc_picking_list_report.xml'",
        "'security/ir.model.access.csv'",
    ],
    'models/__init__.py': ['from . import material_requirement',
                           'from . import material_requirement_batch',
                           'from . import cdc_pick_confirmation'],
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
    'models/cdc_pick_confirmation.py': [
        "_name = 'ya.cdc.pick.confirmation'",
        "_name = 'ya.cdc.pick.confirmation.line'",
        "TEST_DB = 'erp-yussyakmal-mrp-test'",
        "def action_confirm_qty(self):",
        "def _compute_special_qty(self):",
        "if is_extra and not line.special_transfer:",
        "if is_extra and not (line.special_reason or '').strip():",
        "'state': 'confirmed'",
        "special_reference = fields.Char(",
        "internal_transfer_id = fields.Many2one(",
        "def action_create_internal_transfer(self):",
        "def action_open_internal_transfer(self):",
        "if self.internal_transfer_id:",
        "if self.state != 'confirmed':",
        "'stock.group_stock_manager'",
        "'SELECT id FROM ya_cdc_pick_confirmation WHERE id = %s FOR UPDATE'",
        "'SELECT id FROM stock_warehouse WHERE id = %s FOR UPDATE'",
        "picking_type = cdc.int_type_id",
        "picking_type.code != 'internal'",
        "'origin': origin",
        "'product_uom_qty': qty",
        "'location_id': source.id",
        "'location_dest_id': dest.id",
        "picking = Picking.create(picking_vals)",
        "Move.create([",
        "ya_link_cdc_internal_transfer=True",
        "('state', '=', 'confirmed')",
        "('location_id', 'child_of', self.cdc_warehouse_id.lot_stock_id.id)",
        "'SELECT id FROM stock_warehouse WHERE id = %s FOR UPDATE'",
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
        'name="action_mr_open_pick_confirmations"',
        'mr_kitchen_line_ids',
        'mr_cdc_line_ids',
    ],
    'views/cdc_pick_confirmation_views.xml': [
        'view_ya_cdc_pick_confirmation_list',
        'view_ya_cdc_pick_confirmation_form',
        'Konfirmasi Qty Picking',
        'special_qty',
        'special_transfer',
        'special_reason',
        'special_reference',
        'internal_transfer_id',
        'name="action_create_internal_transfer"',
        'name="action_open_internal_transfer"',
        '<header>',
        'create="false"',
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
        'model_ya_cdc_pick_confirmation',
        'model_ya_cdc_pick_confirmation_line',
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
# Standard Odoo picking/move creation is permitted ONLY in an explicit action
# and only as Draft (no action_confirm, action_assign, button_validate, etc).
# This source audit does not prove correct runtime behavior in Odoo.
const_required_guards = [
    'def action_create_internal_transfer(self):',
    "if self.state != 'confirmed':",
    "'stock.group_stock_manager'",
    "'origin': origin",
    "('origin', '=', origin)",
    "'internal_transfer_id': picking.id",
]
confirm_source = (root / 'models/cdc_pick_confirmation.py').read_text(
    encoding='utf-8')
for needle in const_required_guards:
    if needle not in confirm_source:
        errors.append('MISSING TRANSFER SAFETY GUARD: '+needle)

# Odoo 19 deployed stock.move rejects 'name'. Inspect the actual payload
# AST rather than matching other legitimate name fields in model/notes.
for node in ast.walk(ast.parse(confirm_source)):
    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
        continue
    if (node.func.attr == 'append'
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == 'move_values'):
        for arg in node.args:
            if not isinstance(arg, ast.Dict):
                continue
            keys = [
                key.value for key in arg.keys
                if isinstance(key, ast.Constant) and isinstance(key.value, str)
            ]
            if 'name' in keys:
                errors.append(
                    "OD00_19_INVALID_FIELD: stock.move 'name' in transfer payload"
                )
            required_move_fields = {
                'product_id', 'product_uom', 'product_uom_qty',
                'location_id', 'location_dest_id', 'company_id',
            }
            if not required_move_fields.issubset(keys):
                errors.append(
                    'MISSING_REQUIRED_STOCK_MOVE_FIELDS: %s'
                    % sorted(required_move_fields.difference(keys))
                )
if 'move_fields = set(Move._fields)' not in confirm_source:
    errors.append('MISSING_RUNTIME_STOCK_MOVE_SCHEMA_GUARD')
if "picking.action_confirm(" in confirm_source or "picking.button_validate(" in confirm_source:
    errors.append('FORBIDDEN AUTOMATIC STOCK TRANSFER CONFIRM/VALIDATE')
# Confirmation is a document, not an inventory write. Reject any stock
# reservation, transfer validation or explicit DB commits in this source.
confirmation = (root / 'models/cdc_pick_confirmation.py').read_text(encoding='utf-8')
confirmation_ast = ast.parse(confirmation)
for node in ast.walk(confirmation_ast):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr in (
                'button_validate', '_action_done', 'action_done',
                '_update_available_quantity', 'action_assign',
                'action_confirm', 'commit', 'sudo'):
            errors.append('UNSAFE CONFIRMATION METHOD: %s line %s' %
                          (node.func.attr, node.lineno))
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
