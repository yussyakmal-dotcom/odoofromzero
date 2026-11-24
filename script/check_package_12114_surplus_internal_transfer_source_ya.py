"""Source-only preflight for UAT surplus transfer AFTER native Paket receipt.

Use real full Paket E2E and explicitly selected destination T_BAN for
16 unallocated finished units; do not add those units to any RO or DO.
"""
import ast
from pathlib import Path

base = Path(__file__).resolve().parents[1]
source_path = base / "script/test_package_12114_surplus_internal_transfer_rollback_ya.py"
baseline_path = base / "script/test_package_12114_package_done_store_receipt_rollback_ya.py"
original_seed_path = base / "script/dev_seed_cdc_material_10x_ya.py"
source = source_path.read_text("utf8")
baseline = baseline_path.read_text("utf8")
seed = original_seed_path.read_text("utf8")
ast_tree = ast.parse(source, filename=str(source_path))
errors = []

must_have = [
    'assert env.cr.dbname == "erp-yussyakmal-mrp-test"',
    "with env.cr.savepoint():",
    "package_product = product",
    "desired = max(current, 10 * shortage)",
    "quant.action_apply_inventory()",
    "own_mo_reserved",
    "NATIVE_KITCHEN_MO_DONE_3_PASS",
    "NATIVE_KITCHEN_TO_PCK_FG_TRANSFER_ROLLBACK_PASS",
    "PCK_NATIVE_ASSEMBLY_MO_DONE_PASS",
    "PCK_NATIVE_ASSEMBLY_COMPONENT_CONSUMPTION_PASS",
    "NATIVE_STORE_RECEIPT_T_BAN_DONE_PASS",
    "NATIVE_ONE_DO_ONE_RECEIPT_NO_DUPLICATES_PASS",
    'surplus_destination_store.code == "T_BAN"',
    "surplus_destination_store.lot_stock_id.id",
    '"UAT-ROLLBACK-EXPLICIT-SURPLUS-12114-TO-%s"',
    "pck.int_type_id",
    '"picking_type_id": operation.id', # native PCK internal picking type
    "surplus_picking.action_confirm()",
    "move.write({\"quantity\": move.product_uom_qty})",
    "NATIVE_PCK_SURPLUS_INTERNAL_TRANSFER_DONE_PASS",
    "NATIVE_SURPLUS_QTY_16_AND_PCK_ZERO_LEFTOVERS_PASS",
    "NO_FAKE_SURPLUS_RO_OR_EXTRA_DO_PASS",
    "ROLLBACK_SURPLUS_PICKING_AND_STORE_STOCK_VERIFIED_PASS",
    "PACKAGE_12114_SURPLUS_INTERNAL_TRANSFER_ROLLBACK_PASS",
    "env.cr.rollback()",
]
for token in must_have:
    if token not in source:
        errors.append("MISSING: " + token)
for token in (
    "PACKAGE_12114_FULL_STORE_RECEIPT_ROLLBACK_PASS",
    "NATIVE_ONE_DO_ONE_RECEIPT_NO_DUPLICATES_PASS",
):
    if token not in baseline:
        errors.append("BASELINE_MODIFIED: " + token)
for token in (
    "TARGET_DATE = '2026-11-27'",
    "MULTIPLIER = 10",
    "quant.action_apply_inventory()",
    "env.cr.commit()",
):
    if token not in seed:
        errors.append("ORIGINAL_SEED_MODIFIED: " + token)
for node in ast.walk(ast_tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr in ("commit", "_update_available_quantity"):
            errors.append("UNSAFE_FUNCTION_CALL: %s at %s" %
                          (node.func.attr, node.lineno))
print("SOURCE:", source_path)
print("ERROR_COUNT:", len(errors))
for error in errors:
    print("ERROR:", error)
if errors:
    raise SystemExit(1)
print("PAKET_SURPLUS_NATIVE_INTERNAL_TRANSFER_SOURCE_OK")
print("SOURCE_ONLY_NO_DB_CHANGES")
