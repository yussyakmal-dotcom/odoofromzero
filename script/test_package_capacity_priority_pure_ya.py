"""Source-only test: Paket-first kitchen capacity and rounded surplus to stores.

This validates OWNER INTENDED surplus rule using historical prorata helper.
The ordinary RO source now distributes BoM rounding surplus; however source
unit tests do NOT prove that Odoo's test database/UI has been upgraded/UATed.
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
ordinary = load("ya_ordinary_allocation", root / "addons/ya_store_ro/models/allocation_rules.py")
plan = rules.plan_kitchen_capacity_with_package_priority

# User's exact rule: 15 gross demand; one kitchen BoM yields 10;
# 2 BoM batches => 20. Protect Paket 5, fulfill stores' original 10,
# share 5 rounding surplus in proportion to store RO 4:6 => +2 and +3.
rounded = plan(5, {11: 4, 22: 6}, 10, 20)
assert rounded["status"] == "ok", rounded
assert rounded["qty_production"] == 20
assert rounded["package_component_qty_protected"] == 5
assert rounded["direct_qty_requested"] == 10
assert rounded["direct_qty_allocated"] == 15
assert rounded["qty_surplus_distributed"] == 5
assert rounded["qty_surplus"] == 0
assert rounded["store_allocations"] == {
    11: {"requested": 4, "allocated": 6, "shortage": 0, "surplus": 2},
    22: {"requested": 6, "allocated": 9, "shortage": 0, "surplus": 3},
}, rounded

# When whole-batch capacity can cover Paket but not direct stores,
# protect Paket first, then prorate ONLY the remaining direct budget.
limited = plan(5, {11: 4, 22: 6}, 1, 12)
assert limited["status"] == "prorated_direct_only", limited
assert limited["qty_production"] == 12
assert limited["package_component_qty_protected"] == 5
assert limited["direct_qty_allocated"] == 7
assert limited["direct_qty_shortage"] == 3
assert limited["qty_surplus_distributed"] == 0
assert limited["store_allocations"] == {
    11: {"requested": 4, "allocated": 3, "shortage": 1, "surplus": 0},
    22: {"requested": 6, "allocated": 4, "shortage": 2, "surplus": 0},
}

# Planning Max 10 permits only one kitchen BoM of 10, not two.
rounded_limited = plan(5, {11: 10}, 10, 10)
assert rounded_limited["qty_production"] == 10
assert rounded_limited["package_component_qty_protected"] == 5
assert rounded_limited["direct_qty_allocated"] == 5
assert rounded_limited["direct_qty_shortage"] == 5

# All capacity protected by Paket, ordinary store gets zero.
all_package = plan(5, {11: 8}, 1, 5)
assert all_package["store_allocations"][11] == {
    "requested": 8, "allocated": 0, "shortage": 8, "surplus": 0}

# Cannot cover protected Paket: no executable MO.
blocked = plan(6, {11: 10}, 1, 5)
assert blocked["status"] == "blocked_package_capacity", blocked
assert blocked["qty_production"] == 0
assert blocked["package_component_shortage"] == 6
assert blocked["capacity_if_unblocked"] == 5

# Huge kitchen BoM rounding surplus: do not strand it when a shop
# requested the SKU. The shop receives its order PLUS round-up surplus.
large_batch = plan(2, {11: 1}, 5, 5)
assert (large_batch["qty_production"], large_batch["package_component_qty_protected"],
        large_batch["direct_qty_allocated"], large_batch["qty_surplus_distributed"],
        large_batch["qty_surplus"]) == (5, 2, 3, 2, 0), large_batch
assert large_batch["store_allocations"][11] == {
    "requested": 1, "allocated": 3, "shortage": 0, "surplus": 2}

# Owner clarification: even if automatic RO prorata has no recipient,
# Packing sends the leftover to a store through separate native internal
# transfer. Preserve 10 produced: Paket consumes 5, internal transfer gets 5.
no_store = plan(5, {}, 10, 10)
assert no_store["status"] == "ok", no_store
assert no_store["qty_production"] == 10
assert no_store["package_component_qty_protected"] == 5
assert no_store["qty_surplus_distributed"] == 0
assert no_store["qty_surplus"] == 5
assert no_store["qty_pending_internal_transfer"] == 5
assert no_store["store_allocations"] == {}
assert (no_store["package_component_qty_protected"] +
        no_store["qty_pending_internal_transfer"]) == no_store["qty_production"]
# If Paket needs exactly the kitchen BoM output, no store is needed.
exact_package = plan(10, {}, 10, 10)
assert exact_package["status"] == "ok", exact_package
assert exact_package["qty_production"] == 10
assert exact_package["package_component_qty_protected"] == 10
assert exact_package["qty_surplus"] == 0
# Remaining component units may be distributed to a real ordering store.
has_store = plan(5, {11: 1}, 10, 10)
assert has_store["status"] == "ok", has_store
assert has_store["qty_production"] == 10
assert has_store["store_allocations"][11] == {
    "requested": 1, "allocated": 5, "shortage": 0, "surplus": 4}
assert has_store["qty_surplus"] == 0

# No-Paket baseline: compare against original historical surplus-prorata
# helper when max capacity permits whole rounded demand, and the
# shared capacity-shortage helper when max is insufficient.
for demands in ({11: 10}, {11: 4, 22: 6},
                {11: 1, 22: 2, 33: 3}, {11: 0, 22: 7}):
    for batch in (1, 2, 5, 10):
        for cap in (0, 1, 3, 5, 10, 15, 25):
            old_qty, old_rows, old_status = ordinary.allocate_capacity_prorata(
                demands, batch, cap)
            actual = plan(0, demands, batch, cap)
            assert actual["qty_production"] == old_qty, (
                demands, batch, cap, actual)
            if old_status == "ok":
                hist_qty, hist_rows = ordinary.allocate_surplus_prorata(demands, batch)
                assert hist_qty == old_qty
                for store in demands:
                    assert actual["store_allocations"][store]["allocated"] == hist_rows[store]["allocated"]
                    assert actual["store_allocations"][store]["surplus"] == hist_rows[store]["surplus"]
                    assert actual["store_allocations"][store]["shortage"] == 0
                assert actual["qty_surplus"] == 0
            else:
                for store in demands:
                    assert actual["store_allocations"][store]["allocated"] == old_rows[store]["allocated"]
                    assert actual["store_allocations"][store]["shortage"] == old_rows[store]["shortage"]
                    assert actual["store_allocations"][store]["surplus"] == 0
                assert actual["status"] == {
                    "prorated": "prorated_direct_only",
                    "blocked": "blocked",
                }[old_status]

# Reject invalid source quantities and store IDs.
for args in (
    (1.5, {11: 1}, 1, 10),
    (1, {0: 1}, 1, 10),
    (1, {11: -1}, 1, 10),
    (1, {11: 1}, 0, 10),
    (1, {11: 1}, 1, -10),
):
    try:
        plan(*args)
        raise AssertionError("Expected rejection: %r" % (args,))
    except rules.PackageDemandError:
        pass

print("PACKAGE_CAPACITY_PRIORITY_PURE_PASS")
print("NO_PACKAGE_HISTORICAL_SURPLUS_RULE_TEST_PASS")
print("PACKING_INTERNAL_TRANSFER_FALLBACK_TEST_PASS")
print("NOTE: ordinary RO SOURCE now distributes surplus; test DB Odoo upgrade/UAT still pending.")
print("SOURCE_ONLY: no RO, MO, stock, Odoo DB or allocations changed.")
