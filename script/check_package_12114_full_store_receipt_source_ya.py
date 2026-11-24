"""Source-only safety gate for Paket 12114 native receipt rollback test.

Never accesses Odoo/database. It prevents test execution if critical
invariants, native workflow calls or rollback controls disappear.
"""
import ast
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / "script/test_package_12114_package_done_store_receipt_rollback_ya.py"
baseline = root / "script/test_package_12114_mo_done_fg_assembly_rollback_ya.py"
seed = root / "script/dev_seed_cdc_material_10x_ya.py"
text = target.read_text(encoding="utf-8")
baseline_text = baseline.read_text(encoding="utf-8")
seed_text = seed.read_text(encoding="utf-8")
tree = ast.parse(text, filename=str(target))
errors = []

for token in (
    'assert env.cr.dbname == "erp-yussyakmal-mrp-test"',
    'sku = "12114"',
    'date = "2026-11-24"',
    'slot = "S1"',
    "with env.cr.savepoint():",
    "package_product = product",
    "desired = max(current, 10 * shortage)",
    "quant.action_apply_inventory()",
    "picking.action_confirm()",
    ").button_validate()",
    "own_mo_reserved",
    "NATIVE_CDC_KITCHEN_TRANSFER_ROLLBACK_PASS",
    "button_mark_done()",
    "NATIVE_KITCHEN_MO_DONE_3_PASS",
    "NATIVE_MO_RAW_CONSUMPTION_DELTAS_PASS",
    "action_ya_fg_move_to_packing()",
    "NATIVE_KITCHEN_TO_PCK_FG_TRANSFER_ROLLBACK_PASS",
    "action_ya_create_package_assembly_mos()",
    "PCK_PACKAGE_ASSEMBLY_MO_CONFIRMED_ROLLBACK_PASS",
    "assembly.action_assign()",
    "PCK_NATIVE_ASSEMBLY_MO_DONE_PASS",
    "PCK_NATIVE_ASSEMBLY_COMPONENT_CONSUMPTION_PASS",
    "PCK_KITCHEN_SURPLUS_REQUIRES_SEPARATE_TRANSFER:",
    "action_ya_generate_store_do()",
    "PCK_PAKET_STORE_DO_DEMAND_AND_IDEMPOTENCE_PASS",
    "PCK_TO_TRANSIT_PAKET_DISPATCH_DONE_PASS",
    "TRANSIT_TO_STORE_NATIVE_RECEIPT_CREATED_PASS",
    "NATIVE_STORE_RECEIPT_T_BAN_DONE_PASS",
    "NATIVE_ONE_DO_ONE_RECEIPT_NO_DUPLICATES_PASS",
    "ROLLBACK_PAKET_PCK_TRANSIT_STORE_VERIFIED_PASS",
    "ROLLBACK_FINISHED_STOCK_VERIFIED_PASS",
    "ROLLBACK_STOCK_OPNAME_AND_PICKINGS_VERIFIED_PASS",
    "PACKAGE_12114_FULL_STORE_RECEIPT_ROLLBACK_PASS",
    "env.cr.rollback()",
):
    if token not in text:
        errors.append("MISSING: " + token)

for token in (
    "PCK_PACKAGE_ASSEMBLY_DOUBLE_CLICK_IDEMPOTENCE_PASS",
    "ROLLBACK_FINISHED_STOCK_VERIFIED_PASS",
):
    if token not in baseline_text:
        errors.append("BASELINE_UAT_CHANGED: " + token)

for token in (
    "MULTIPLIER = 10",
    "TARGET_DATE = '2026-11-27'",
    "TARGET_SLOT = 'S1'",
    "quant.action_apply_inventory()",
    "env.cr.commit()",
):
    if token not in seed_text:
        errors.append("ORIGINAL_SEED_CHANGED: " + token)

for node in ast.walk(tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr in ("commit", "_update_available_quantity"):
            errors.append("FORBIDDEN_CALL: %s line %s" %
                          (node.func.attr, node.lineno))

# This test is package-only. It must not use a fake ordinary RO or silently
# route 16 surplus kitchen units to an arbitrary store.
if '("planning_id", "=", ' in text:
    errors.append("UNEXPECTED_SYNTHETIC_PLANNING")
if "YA_DEV_CDC_STOCK_APPLY" in text:
    errors.append("UNEXPECTED_PERSISTENT_STOCK_SEED")
print("SOURCE:", target)
print("ERROR_COUNT:", len(errors))
for error in errors:
    print("ERROR:", error)
if errors:
    raise SystemExit(1)
print("PAKET_12114_FULL_RECEIPT_ROLLBACK_SOURCE_OK")
print("SOURCE_ONLY_NO_DB_CHANGES")
