"""Source-only safety preflight for the rollback-only CDC 10x Paket UAT.

This tool reads repo source and makes NO Odoo or DB calls.
"""
import ast
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / "script/test_package_12114_stock_10x_transfer_rollback_ya.py"
original = root / "script/dev_seed_cdc_material_10x_ya.py"
text = target.read_text(encoding="utf-8")
source = original.read_text(encoding="utf-8")
tree = ast.parse(text, filename=str(target))
errors = []
expected = [
    'assert env.cr.dbname == "erp-yussyakmal-mrp-test"',
    'sku = "12114"',
    'date = "2026-11-24"',
    'slot = "S1"',
    'with env.cr.savepoint():',
    'desired = max(current, 10 * shortage)',
    'rounding_method="UP"',
    '"inventory_quantity": desired',
    "quant.action_apply_inventory()",
    '"code", "=", "CDC"',
    "picking.action_confirm()",
    "picking.with_context(",
    ").button_validate()",
    "env.cr.rollback()",
    "ROLLBACK_STOCK_OPNAME_AND_PICKINGS_VERIFIED_PASS",
    '"TRANSFER_DONE:"',
    '"PHYSICAL:"',
    '"RESERVED:"',
    '"FREE:"',
    "POST_TRANSFER_DIAGNOSTIC_COUNT:",
    "float_compare(",
    "env.invalidate_all()",
    "transfer_done_by_key",
    "PACKAGE_12114_10X_OPNAME_TRANSFER_ROLLBACK_PASS",
]
for token in expected:
    if token not in text:
        errors.append("MISSING: " + token)
for token in (
    "MULTIPLIER = 10",
    "quant.action_apply_inventory()",
    "env.cr.commit()",
    "TARGET_DATE = '2026-11-27'",
    "TARGET_SLOT = 'S1'",
):
    if token not in source:
        errors.append("ORIGINAL_SEED_CHANGED_OR_MISSING: " + token)
for node in ast.walk(tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr in ("commit", "_update_available_quantity"):
            errors.append("FORBIDDEN CALL %s on line %s" %
                          (node.func.attr, node.lineno))
if "YO_DEV_CDC_STOCK_APPLY" in text:
    errors.append("Unexpected apply token")
print("SOURCE:", str(target))
print("ERROR_COUNT:", len(errors))
for error in errors:
    print("ERROR:", error)
if errors:
    raise SystemExit(1)
print("PAKET_CDC_10X_ROLLBACK_SOURCE_OK")
print("SOURCE_ONLY_NO_DB_CHANGES")
