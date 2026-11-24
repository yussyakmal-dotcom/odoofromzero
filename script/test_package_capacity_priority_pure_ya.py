"""Source-only no-DB tests: kitchen MO capacity protects Paket before shops.

Run python3 script/test_package_capacity_priority_pure_ya.py.
"""
from pathlib import Path
import importlib.util

root = Path(__file__).resolve().parents[1]
def load(module_name, source):
    spec = importlib.util.spec_from_file_location(module_name, source)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

rules = load("ya_package_priority", root / "addons/ya_store_ro/models/package_priority_rules.py")
legacy = load("ya_ordinary_allocation", root / "addons/ya_store_ro/models/allocation_rules.py")
plan = rules.plan_kitchen_capacity_with_package_priority

# 10 direct Y + 5 Y from Paket, 12 unit capacity, one-unit manufacturing.
a = plan(5, {11: 4, 22: 6}, 1, 12)
assert a["status"] == "prorated_direct_only", a
assert a["qty_production"] == 12
assert a["package_component_qty_protected"] == 5
assert a["package_component_shortage"] == 0
assert a["direct_qty_allocated"] == 7
assert a["direct_qty_shortage"] == 3
assert a["qty_surplus"] == 0
assert a["store_allocations"] == {
    11: {"requested": 4, "allocated": 3, "shortage": 1},
    22: {"requested": 6, "allocated": 4, "shortage": 2},
}, a

# All kitchen capacity is consumed by Paket; ordinary RO becomes shortage.
b = plan(5, {11: 8}, 1, 5)
assert b["package_component_qty_protected"] == 5
assert b["store_allocations"][11] == {
    "requested": 8, "allocated": 0, "shortage": 8}

# Not even the entire package bucket fits: BLOCK and emit no executable MO.
c = plan(6, {11: 10}, 1, 5)
assert c["status"] == "blocked_package_capacity", c
assert c["qty_production"] == 0 and c["package_component_qty_protected"] == 0
assert c["package_component_shortage"] == 6
assert c["capacity_if_unblocked"] == 5

# Rounded BoM output must not be allocated as extra store orders.
d = plan(2, {11: 1}, 5, 5)
assert (d["qty_production"], d["package_component_qty_protected"],
        d["direct_qty_allocated"], d["qty_surplus"]) == (5, 2, 1, 2), d
assert d["store_allocations"][11]["allocated"] == 1

# Three kitchen BoM batches available; demand needs four: protect Paket.
e = plan(9, {11: 6, 22: 6}, 5, 15)
assert e["qty_production"] == 15 and e["package_component_qty_protected"] == 9
assert e["direct_qty_allocated"] == 6
assert e["store_allocations"][11]["allocated"] == 3
assert e["store_allocations"][22]["allocated"] == 3

# Without Paket, new algorithm must reproduce legacy store allocations and
# production quantity for all ordinary no-Paket scenarios.
for demands in ({11: 10}, {11: 4, 22: 6}, {11: 1, 22: 2, 33: 3}):
    for batch in (1, 2, 5, 10):
        for cap in (0, 1, 3, 5, 10, 15, 25):
            old_produced, old_alloc, old_status = legacy.allocate_capacity_prorata(
                demands, batch, cap)
            new = plan(0, demands, batch, cap)
            assert new["qty_production"] == old_produced, (demands, batch, cap)
            for store in demands:
                assert new["store_allocations"][store]["allocated"] == (
                    old_alloc[store]["allocated"]), (demands, batch, cap, new)
                assert new["store_allocations"][store]["shortage"] == (
                    old_alloc[store]["shortage"]), (demands, batch, cap, new)
            assert new["qty_surplus"] == (
                old_produced - sum(x["allocated"] for x in old_alloc.values())
            ), (demands, batch, cap, new)
            assert new["status"] == {
                "ok": "ok", "prorated": "prorated_direct_only",
                "blocked": "blocked",
            }[old_status]

# Reject malformed Qty, nonpositive batch and invalid store IDs.
for args in (
    (1.5, {11: 1}, 1, 10),
    (1, {0: 1}, 1, 10),
    (1, {11: -1}, 1, 10),
    (1, {11: 1}, 0, 10),
    (1, {11: 1}, 1, -10),
):
    try:
        plan(*args)
        raise AssertionError("Expected explicit Qty failure: %r" % (args,))
    except rules.PackageDemandError:
        pass

print("PACKAGE_CAPACITY_PRIORITY_PURE_PASS")
print("NO_PACKAGE_REGRESSION_PASS")
print("SOURCE_ONLY: no RO, MO, stock, Odoo DB or allocations changed.")
