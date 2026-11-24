"""Source-only: frozen Paket demand -> exactly one SKU MO, per-store DO.

No Odoo import, no RO/stock/picking/MO side effects.
"""
import importlib.util
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = root / "addons/ya_package_store_ro/models/package_finish_rules.py"
spec = importlib.util.spec_from_file_location("ya_finish_pure", source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
plan = module.group_package_finish_demands

rows = [
    {"product_id": 901, "store_id": 11, "qty": 3},
    {"product_id": 901, "store_id": 22, "qty": 2},
    {"product_id": 902, "store_id": 22, "qty": 4},
    {"product_id": 901, "store_id": 11, "qty": 1},
]
result = plan(rows)
assert result["assembly_mo_qty"] == {901: 6, 902: 4}, result
assert result["store_do_qty"] == {
    11: {901: 4}, 22: {901: 2, 902: 4},
}, result
assert result["total_package_qty"] == 10
print("PACKAGE_ONE_MO_PER_SKU_PASS")
print("PACKAGE_DO_PER_STORE_QTY_PASS")

rev = plan(list(reversed(rows)))
assert rev == result
assert plan([]) == {
    "assembly_mo_qty": {}, "store_do_qty": {}, "total_package_qty": 0}
print("PACKAGE_ORDER_INDEPENDENT_PASS")

for bad in (
    [{"product_id": 1, "store_id": 11, "qty": 0}],
    [{"product_id": 0, "store_id": 11, "qty": 1}],
    [{"product_id": 1, "store_id": -1, "qty": 1}],
    [{"product_id": 1, "store_id": 11, "qty": 0.5}],
    [{"product_id": 1, "store_id": True, "qty": 1}],
):
    try:
        plan(bad)
        raise AssertionError("Invalid Paket Qty/source was accepted: %s" % bad)
    except module.PackageFinishError:
        pass
print("PACKAGE_INVALID_FINISH_DEMAND_REJECT_PASS")
print("PACKAGE_ASSEMBLY_DISPATCH_PURE_ALL_PASS")
print("SOURCE_ONLY_NO_DB_CHANGES")
