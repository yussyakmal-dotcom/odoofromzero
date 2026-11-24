"""Pure test: aggregate cross-kitchen Paket RO with ordinary RO in one slot.

No Odoo import, DB, stock, MO, source RO or GL writes.
Run: python3 script/test_package_joint_slot_pure_ya.py
"""
import importlib.util
from pathlib import Path

root = Path(__file__).resolve().parents[1]


def load(name, rel):
    spec = importlib.util.spec_from_file_location(name, root / rel)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base = load("ya_package_priority_base",
            "addons/ya_store_ro/models/package_priority_rules.py")
joint = load("ya_package_joint_slot",
             "addons/ya_package_store_ro/models/joint_slot_rules.py")
plan = lambda direct, package, specs: joint.plan_joint_slot(
    direct, package, specs, base.plan_kitchen_capacity_with_package_priority)


specs = {
    101: dict(planning_id=1001, kitchen_code="D01",
              bom_id=201, bom_output=10, max_capacity=30),
    102: dict(planning_id=1002, kitchen_code="D02",
              bom_id=202, bom_output=10, max_capacity=30),
}
direct = [
    dict(product_id=101, store_id=11, qty=4, ro_id=301),
    dict(product_id=101, store_id=22, qty=6, ro_id=302),
    dict(product_id=102, store_id=11, qty=4, ro_id=303),
    dict(product_id=102, store_id=22, qty=6, ro_id=304),
]
pkg = [dict(product_id=901, store_id=22, qty=5, ro_id=401, components=[
    dict(product_id=101, qty_per_package=1, source_kind="KITCHEN"),
    dict(product_id=102, qty_per_package=1, source_kind="KITCHEN"),
    dict(product_id=501, qty_per_package=0.5, source_kind="PCK"),
])]
r = plan(direct, pkg, specs)
assert r["package_store_delivery"] == [
    {"store_id": 22, "product_id": 901, "qty": 5}], r
assert r["pck_stock_requirements"] == {501: 2.5}
assert r["package_component_trace"] == {901: {101: 5, 102: 5}}
assert r["total_kitchen_mo_qty"] == 40
assert r["total_pending_internal_transfer"] == 0
assert not r["warnings"], r["warnings"]
for item in r["kitchen_mo_plans"]:
    assert item["qty_production"] == 20 and item["package_component_qty"] == 5
    assert item["direct_store_requested"] == 10
    assert item["store_allocations"] == {
        11: {"requested": 4, "allocated": 6, "shortage": 0, "surplus": 2},
        22: {"requested": 6, "allocated": 9, "shortage": 0, "surplus": 3},
    }, item
print("JOINT_SLOT_PAKET_FIRST_PRORATA_PASS")

# Without packages, ordinary RO is correctly rounded/prorated; no fake Paket.
ordinary = plan(direct, [], specs)
assert ordinary["package_store_delivery"] == []
assert ordinary["total_kitchen_mo_qty"] == 20
assert all(x["qty_production"] == 10 for x in ordinary["kitchen_mo_plans"])
assert ordinary["total_pending_internal_transfer"] == 0
print("JOINT_SLOT_ORDINARY_NO_PACKAGE_PASS")

# Paket alone, kitchen BoM 10 outputs, component demand 5:
# 5 units remain tracked for separate PCK->store internal transfer.
only_package = plan([], pkg, specs)
assert only_package["total_kitchen_mo_qty"] == 20
assert only_package["total_pending_internal_transfer"] == 10
assert all(x["qty_pending_internal_transfer"] == 5
           for x in only_package["kitchen_mo_plans"])
assert all(x["package_component_qty"] == 5
           for x in only_package["kitchen_mo_plans"])
print("JOINT_SLOT_INTERNAL_TRANSFER_FALLBACK_PASS")

# Shared components of two package SKUs in different stores are summed
# BEFORE a kitchen MO is planned; a single SKU still gets one MO.
pkg2 = dict(product_id=902, store_id=11, qty=2, ro_id=402, components=[
    dict(product_id=101, qty_per_package=2, source_kind="KITCHEN"),
    dict(product_id=102, qty_per_package=1, source_kind="KITCHEN"),
])
two = plan([], pkg + [pkg2], specs)
assert len(two["kitchen_mo_plans"]) == 2
assert two["package_component_trace"][901] == {101: 5, 102: 5}
assert two["package_component_trace"][902] == {101: 4, 102: 2}
assert {x["product_id"]: x["package_component_qty"] for x in
        two["kitchen_mo_plans"]} == {101: 9, 102: 7}
assert sorted(x["product_id"] for x in two["package_store_delivery"]) == [901, 902]
print("JOINT_SLOT_MULTIPLE_PACKAGES_SHARED_COMPONENT_PASS")

# Published Planning Max below gross request: package requirements still
# protected; only ordinary shop allocation is reduced.
limited = {sku: dict(data, max_capacity=10) for sku, data in specs.items()}
short = plan(direct, pkg, limited)
assert all(x["qty_production"] == 10 for x in short["kitchen_mo_plans"])
assert all(x["package_component_qty"] == 5 for x in short["kitchen_mo_plans"])
assert all(sum(y["allocated"] for y in x["store_allocations"].values()) == 5
           for x in short["kitchen_mo_plans"])
print("JOINT_SLOT_PACKAGE_CAPACITY_PRIORITY_PASS")

# A single-kitchen package in Paket category is reported for master
# recategorization, rather than secretly manufacturing a fake second kitchen.
one_kitchen = plan([], [dict(
    product_id=903, store_id=11, qty=1, components=[
        dict(product_id=101, qty_per_package=1, source_kind="KITCHEN")
    ])], specs)
assert any("fewer than 2" in warning for warning in one_kitchen["warnings"])
print("JOINT_SLOT_ONE_KITCHEN_CATEGORY_ADVISORY_PASS")

for bad in (
    [dict(product_id=904, store_id=11, qty=2, components=[])],
    [dict(product_id=904, store_id=11, qty=2, components=[
        dict(product_id=101, qty_per_package=0.5, source_kind="KITCHEN"),
        dict(product_id=102, qty_per_package=1, source_kind="KITCHEN"),
    ])],
    [dict(product_id=904, store_id=11, qty=2, components=[
        dict(product_id=999, qty_per_package=1, source_kind="KITCHEN"),
    ])],
):
    try:
        plan([], bad, specs)
        raise AssertionError("Expected a missing/invalid kitchen component rule")
    except joint.JointSlotError:
        pass
print("JOINT_SLOT_INVALID_INPUT_REJECT_PASS")
print("JOINT_SLOT_PURE_ALL_PASS")
print("SOURCE_ONLY_NO_DB_CHANGES")
