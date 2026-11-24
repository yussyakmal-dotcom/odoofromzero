"""Read-only Python source gate for mixed Paket/ordinary surplus UAT.

No Odoo connection or database mutation. The UAT target exclusively uses
erp-yussyakmal-mrp-test and reuses fully-proven native manufacturing/DO flows.
"""
import ast
from pathlib import Path

repo = Path(__file__).resolve().parents[1]
target = repo / "script/test_package_joint_mixed_surplus_final_rollback_ya.py"
baseline = repo / "script/test_package_joint_mixed_physical_do_receipt_rollback_ya.py"
original_seed = repo / "script/dev_seed_cdc_material_10x_ya.py"
text = target.read_text(encoding="utf8")
old = baseline.read_text(encoding="utf8")
seed = original_seed.read_text(encoding="utf8")
tree = ast.parse(text, filename=str(target))
errors = []
required = (
    'assert env.cr.dbname == "erp-yussyakmal-mrp-test"',
    'date = "2026-11-24"',
    'slot = "S1"',
    'sku = "12114"',
    "with env.cr.savepoint():",
    "package_product = product",
    "JOINT_PACKAGE_FIRST_AND_ORDINARY_PRORATA_PASS",
    "quant.action_apply_inventory()",
    "NATIVE_CDC_KITCHEN_TRANSFER_ROLLBACK_PASS",
    "NATIVE_KITCHEN_MO_DONE_3_PASS",
    "NATIVE_KITCHEN_TO_PCK_FG_TRANSFER_ROLLBACK_PASS",
    "PCK_NATIVE_ASSEMBLY_MO_DONE_PASS",
    "JOINT_ONE_NATIVE_DO_PER_STORE_PASS",
    "JOINT_SAME_STORE_PAKET_PLUS_ORDINARY_ON_ONE_DO_PASS",
    "JOINT_NATIVE_DISPATCH_TRANSIT_RECEIPTS_PASS",
    "JOINT_PCK_ONLY_UNALLOCATED_SURPLUS_10_REMAIN_PASS",
    'surplus_destination_store = ordinary_store',
    'surplus_destination_store.code == "T_KD"',
    '"12014": 6.0, "12019": 4.0',
    '"picking_type_id": surplus_operation.id',
    "surplus_picking.action_confirm()",
    'move.write({"quantity": move.product_uom_qty})',
    "JOINT_SURPLUS_NATIVE_INTERNAL_TRANSFER_DONE_PASS",
    "JOINT_PCK_NO_SURPLUS_FROM_THIS_BATCH_PASS",
    "JOINT_NO_FAKE_SURPLUS_RO_OR_EXTRA_DO_PASS",
    "JOINT_SURPLUS_PICKING_AND_STORE_ROLLBACK_PASS",
    "JOINT_DISPATCH_RECEIPT_STOCK_ROLLBACK_PASS",
    "ROLLBACK_STOCK_OPNAME_AND_PICKINGS_VERIFIED_PASS",
    "JOINT_PAKET_ORDINARY_FULL_SURPLUS_CLEARED_ROLLBACK_PASS",
    "env.cr.rollback()",
)
for marker in required:
    if marker not in text:
        errors.append("MISSING: " + marker)
for marker in (
    "JOINT_PAKET_AND_ORDINARY_PHYSICAL_STORE_RECEIPT_ROLLBACK_PASS",
    "JOINT_NATIVE_DISPATCH_TRANSIT_RECEIPTS_PASS",
):
    if marker not in old:
        errors.append("BASELINE_MODIFIED: " + marker)
for marker in (
    "TARGET_DATE = '2026-11-27'",
    "MULTIPLIER = 10",
    "quant.action_apply_inventory()",
    "env.cr.commit()",
):
    if marker not in seed:
        errors.append("ORIGINAL_STOCK_SEED_MODIFIED: " + marker)
for node in ast.walk(tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr in ("commit", "_update_available_quantity"):
            errors.append("FORBIDDEN_CALL: %s line %s" %
                          (node.func.attr, node.lineno))
print("SOURCE:", target)
print("ERROR_COUNT:", len(errors))
for error in errors:
    print("ERROR:", error)
if errors:
    raise SystemExit(1)
print("JOINT_PAKET_ORDINARY_SURPLUS_FINAL_SOURCE_OK")
print("SOURCE_ONLY_NO_DB_CHANGES")
