"""Run python3 script/test_package_demand_buckets_pure_ya.py; no Odoo DB."""
from pathlib import Path
import importlib.util

path = Path(__file__).resolve().parents[1] / "addons/ya_store_ro/models/package_priority_rules.py"
spec = importlib.util.spec_from_file_location("package_priority_rules_ya", path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

plan = module.compute_package_first_demand(
    {"Y": 10, "Z": 10}, {"X": 5},
    {"X": {"Y": 1, "Z": 1, "CONS": 2, "BOX": 1}},
    {"Y": "MANUFACTURED_KITCHEN", "Z": "MANUFACTURED_KITCHEN",
     "CONS": "PCK_STOCK_STANDARD_FLOW", "BOX": "PCK_STOCK_STANDARD_FLOW"},
)
assert plan["gross_kitchen_demand"] == {"Y": 15, "Z": 15}
assert plan["package_kitchen_protected"] == {"Y": 5, "Z": 5}
assert plan["package_packing_stock_requirements"] == {"CONS": 10, "BOX": 5}
assert plan["direct_store_finished"] == {"Y": 10, "Z": 10}
assert plan["package_store_finished"] == {"X": 5}
assert module.allocate_kitchen_capacity_package_first(5, {1: 4, 2: 6}, 12) == {
    "protected_required": 5, "protected_from_supply": 5,
    "protected_shortage": 0, "available_after_package": 7,
    "direct_requested": 10, "direct_possible": 7, "direct_shortage": 3,
}
assert module.allocate_kitchen_capacity_package_first(5, {1: 10}, 3)["protected_shortage"] == 2
assert module.compute_package_first_demand({"Y": 10}, {}, {}, {"Y": "MANUFACTURED_KITCHEN"})[
    "gross_kitchen_demand"] == {"Y": 10}
multi = module.compute_package_first_demand(
    {}, {"X": 3, "W": 2},
    {"X": {"Y": 2}, "W": {"Y": 1, "Z": 3}},
    {"Y": "MANUFACTURED_KITCHEN", "Z": "MANUFACTURED_KITCHEN"},
)
assert multi["gross_kitchen_demand"] == {"Y": 8, "Z": 6}
mixed = module.compute_package_first_demand(
    {"Y": 4}, {"P": 2}, {"P": {"Y": 3, "BUY": 2, "PRINT": 1}},
    {"Y": "MANUFACTURED_KITCHEN",
     "BUY": "PCK_STOCK_STANDARD_FLOW", "PRINT": "PCK_STOCK_STANDARD_FLOW"},
)
assert mixed["gross_kitchen_demand"] == {"Y": 10}
assert mixed["package_packing_stock_requirements"] == {"BUY": 4, "PRINT": 2}
for data in [
    ({"BUY": 1}, {}, {}, {"BUY": "PCK_STOCK_STANDARD_FLOW"}),
    ({}, {"X": 1}, {}, {}),
    ({}, {"X": 1}, {"X": {"Y": 0}}, {"Y": "FINISHED_KITCHEN"}),
    ({}, {"X": 1}, {"X": {"Y": 1.5}}, {"Y": "FINISHED_KITCHEN"}),
    ({}, {"X": 1}, {"X": {"Y": 1}}, {"Y": "NESTED_PACKAGE"}),
]:
    try:
        module.compute_package_first_demand(*data)
        raise AssertionError("expected explicit failure for invalid BoM")
    except module.PackageDemandError:
        pass
print("PACKAGE_DEMAND_BUCKETS_PURE_PASS")
print("SOURCE_ONLY: no Odoo RO, MO, stock or allocations were changed.")
