"""No Odoo connection: source gate for REAL native MO Done / FG / PCK rollback.

Guard existing first-stage test and original 10x seed unchanged.
Run as Feri from the Git repo root, never with sudo.
"""
import ast
from pathlib import Path

root = Path(__file__).resolve().parents[1]
target = root / "script/test_package_12114_mo_done_fg_assembly_rollback_ya.py"
old_seed = root / "script/dev_seed_cdc_material_10x_ya.py"
original = root / "script/test_package_12114_stock_10x_transfer_rollback_ya.py"
text = target.read_text(encoding="utf8")
baseline = original.read_text(encoding="utf8")
seed = old_seed.read_text(encoding="utf8")
tree = ast.parse(text, filename=str(target))
errors = []
for token in [
    'assert env.cr.dbname == "erp-yussyakmal-mrp-test"',
    'sku = "12114"',
    'date = "2026-11-24"',
    'slot = "S1"',
    "with env.cr.savepoint():",
    "desired = max(current, 10 * shortage)",
    "quant.action_apply_inventory()",
    "picking.with_context(",
    ").button_validate()",
    "own_mo_reserved",
    "NATIVE_CDC_KITCHEN_TRANSFER_ROLLBACK_PASS",
    "button_mark_done()",
    "skip_backorder=True",
    "NATIVE_KITCHEN_MO_DONE_3_PASS",
    "NATIVE_MO_RAW_CONSUMPTION_DELTAS_PASS",
    "NATIVE_MO_FINISHED_KITCHEN_STOCK_DELTAS_PASS",
    "action_ya_fg_move_to_packing()",
    "NATIVE_KITCHEN_TO_PCK_FG_TRANSFER_ROLLBACK_PASS",
    "NATIVE_FG_DOUBLE_CLICK_IDEMPOTENCE_PASS",
    "action_ya_create_package_assembly_mos()",
    "package_product = product",
    "assert package_product.id == demand.product_id.id",
    "if d.product_id.id == package_product.id",
    "assert assembly.product_id.id == package_product.id",
    "precision_rounding=package_product.uom_id.rounding",
    '"PCK_ASSEMBLY_ACTUAL:"',
    '"PCK_ASSEMBLY_EXPECTED:"',
    "PCK_PACKAGE_ASSEMBLY_MO_CONFIRMED_ROLLBACK_PASS",
    "PCK_PACKAGE_ASSEMBLY_DOUBLE_CLICK_IDEMPOTENCE_PASS",
    "ROLLBACK_FINISHED_STOCK_VERIFIED_PASS",
    "ROLLBACK_STOCK_OPNAME_AND_PICKINGS_VERIFIED_PASS",
    "PACKAGE_12114_MO_DONE_FG_ASSEMBLY_ROLLBACK_PASS",
    "env.cr.rollback()",
]:
    if token not in text:
        errors.append("MISSING: " + token)
for token in [
    'print("NATIVE_CDC_KITCHEN_TRANSFER_ROLLBACK_PASS")',
    'print("POST_TRANSFER_DIAGNOSTIC_COUNT:", len(shortages))',
    "AUTO_RESERVED_FOR_TEST_MO_COMBINATIONS:",
]:
    if token not in baseline:
        errors.append("BASELINE_STOCK_TEST_CHANGED: " + token)
for token in [
    "TARGET_DATE = '2026-11-27'",
    "TARGET_SLOT = 'S1'",
    "MULTIPLIER = 10",
    "quant.action_apply_inventory()",
    "env.cr.commit()",
]:
    if token not in seed:
        errors.append("ORIGINAL_10X_SEED_CHANGED: " + token)
# Never allow the kitchen raw loop variable 'product' to be used again
# as the expected FINAL Paket SKU once PCK assembly is evaluated.
assembly_section = text.split('print("PCK_ASSEMBLY_EXPECTED:"', 1)
if len(assembly_section) != 2:
    errors.append("MISSING: assembly expected product comparison block")
else:
    comparison = assembly_section[1].split('assert assembly.bom_id.id', 1)[0]
    if "product.id" in comparison.replace("package_product.id", ""):
        errors.append("SHADOWED_EXPECTED_PACKAGE_PRODUCT_ID")
    if "product.uom_id" in comparison.replace("package_product.uom_id", ""):
        errors.append("SHADOWED_EXPECTED_PACKAGE_UOM")
for node in ast.walk(tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr in (
            "commit", "_update_available_quantity", "sudo_company"
        ):
            errors.append("FORBIDDEN_CALL: %s line %d" %
                          (node.func.attr, node.lineno))
print("SOURCE:", target)
print("ERROR_COUNT:", len(errors))
for item in errors:
    print("ERROR:", item)
if errors:
    raise SystemExit(1)
print("PAKET_MO_DONE_FG_PCK_ASSEMBLY_SOURCE_OK")
print("SOURCE_ONLY_NO_DB_CHANGES")
