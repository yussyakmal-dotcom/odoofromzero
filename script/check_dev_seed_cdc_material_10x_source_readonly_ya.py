"""Static source-only guard for DEV CDC inventory adjustment, no Odoo import."""
import ast
from pathlib import Path

path = Path(__file__).with_name('dev_seed_cdc_material_10x_ya.py')
source = path.read_text(encoding='utf-8')
tree = ast.parse(source, filename=str(path))
must = [
    "EXPECTED_DB = 'erp-yussyakmal-mrp-test'",
    "TARGET_DATE = '2026-11-27'",
    "TARGET_SLOT = 'S1'",
    "MULTIPLIER = 10",
    "APPLY_TOKEN = 'YES_I_CONFIRM_TEST_DB'",
    "env.cr.dbname != EXPECTED_DB",
    "if not APPLY:",
    "env.cr.rollback()",
    "env.cr.commit()",
    "('code', '=', 'CDC')",
    "('state', '=', 'production_ok')",
    "mo.state != 'confirmed'",
    "mo.move_raw_ids",
    "move.product_uom._compute_quantity(",
    "('location_id', 'child_of', wh.lot_stock_id.id)",
    "quant.reserved_quantity",
    "if reserved > 0:",
    "p.tracking != 'none'",
    "existing =",
    "with_context(inventory_mode=True)",
    "'inventory_quantity': desired",
    "quant.action_apply_inventory()",
    "POST_ADJUST_MISMATCH",
    "APPLY_COMMITTED_TEST_DB_ONLY",
    "PREVIEW_ONLY_OK",
]
missing = [item for item in must if item not in source]
# Required mutation interfaces must be limited to inventory-mode stock.quant.
banned = {'sudo', '_update_available_quantity', '_action_done',
          'button_validate', 'action_confirm', 'action_assign'}
for node in ast.walk(tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr in banned:
            missing.append('FORBIDDEN: %s line %s' % (node.func.attr, node.lineno))
print('SOURCE:', path)
print('ERROR_COUNT:', len(missing))
for err in missing:
    print('ERROR:', err)
if missing:
    raise SystemExit(1)
print('DEV_CDC_10X_SOURCE_OK')
