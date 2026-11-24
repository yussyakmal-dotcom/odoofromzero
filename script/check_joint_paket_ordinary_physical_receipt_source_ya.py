"""Source-only preflight: same store Paket+ordinary combined DO full stock UAT.

NO Odoo connection, no DB access. Verify that the known successful
Paket-only UAT and standard CDC 10x seed remain unchanged.
"""
import ast
from pathlib import Path

root = Path(__file__).resolve().parents[1]
file = root / "script/test_package_joint_mixed_physical_do_receipt_rollback_ya.py"
seed_path = root / "script/dev_seed_cdc_material_10x_ya.py"
baseline_path = root / "script/test_package_12114_package_done_store_receipt_rollback_ya.py"
source = file.read_text(encoding="utf8")
seed = seed_path.read_text(encoding="utf8")
baseline = baseline_path.read_text(encoding="utf8")
tree = ast.parse(source, filename=str(file))
errors = []
for marker in (
    'assert env.cr.dbname == "erp-yussyakmal-mrp-test"',
    'date = "2026-11-24"',
    'slot = "S1"',
    'sku = "12114"',
    "with env.cr.savepoint():",
    "package_product = product",
    '("code", "=", "T_KD")',
    '("default_code", "=", "11999")',
    "created_ordinary_ro_ids",
    "manager_group = env.ref",
    '("delivery_date", "=", date)',
    '"planning_id": plan_line.planning_id.id',
    '"qty_requested": request_qty',
    "expected_allocations",
    "JOINT_PACKAGE_FIRST_AND_ORDINARY_PRORATA_PASS",
    "desired = max(current, 10 * shortage)",
    "quant.action_apply_inventory()",
    "NATIVE_CDC_KITCHEN_TRANSFER_ROLLBACK_PASS",
    "NATIVE_KITCHEN_MO_DONE_3_PASS",
    "NATIVE_MO_RAW_CONSUMPTION_DELTAS_PASS",
    "NATIVE_KITCHEN_TO_PCK_FG_TRANSFER_ROLLBACK_PASS",
    "PCK_PACKAGE_ASSEMBLY_MO_CONFIRMED_ROLLBACK_PASS",
    "PCK_NATIVE_ASSEMBLY_MO_DONE_PASS",
    "PCK_NATIVE_ASSEMBLY_COMPONENT_CONSUMPTION_PASS",
    "action_ya_generate_store_do()",
    "JOINT_ONE_NATIVE_DO_PER_STORE_PASS",
    "JOINT_SAME_STORE_PAKET_PLUS_ORDINARY_ON_ONE_DO_PASS",
    "JOINT_DO_QTY_PAKET_PRIORITY_AND_PRORATA_PASS",
    "JOINT_NATIVE_DISPATCH_TRANSIT_RECEIPTS_PASS",
    "JOINT_PCK_ONLY_UNALLOCATED_SURPLUS_10_REMAIN_PASS",
    "JOINT_DISPATCH_RECEIPT_STOCK_ROLLBACK_PASS",
    "ROLLBACK_FINISHED_STOCK_VERIFIED_PASS",
    "ROLLBACK_STOCK_OPNAME_AND_PICKINGS_VERIFIED_PASS",
    "JOINT_PAKET_AND_ORDINARY_PHYSICAL_STORE_RECEIPT_ROLLBACK_PASS",
    "env.cr.rollback()",
):
    if marker not in source:
        errors.append("MISSING: " + marker)
for marker in (
    "PACKAGE_12114_FULL_STORE_RECEIPT_ROLLBACK_PASS",
    "NATIVE_ONE_DO_ONE_RECEIPT_NO_DUPLICATES_PASS",
):
    if marker not in baseline:
        errors.append("BASELINE_CHANGED: " + marker)
for marker in (
    "TARGET_DATE = '2026-11-27'",
    "MULTIPLIER = 10",
    "quant.action_apply_inventory()",
    "env.cr.commit()",
):
    if marker not in seed:
        errors.append("SEED_CHANGED: " + marker)
for node in ast.walk(tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr in ("commit", "_update_available_quantity"):
            errors.append("UNSAFE_CALL: %s line %s" %
                          (node.func.attr, node.lineno))
print("SOURCE:", file)
print("ERROR_COUNT:", len(errors))
for message in errors:
    print("ERROR:", message)
if errors:
    raise SystemExit(1)
print("JOINT_PAKET_ORDINARY_PHYSICAL_STORE_RECEIPT_SOURCE_OK")
print("SOURCE_ONLY_NO_DB_CHANGES")
