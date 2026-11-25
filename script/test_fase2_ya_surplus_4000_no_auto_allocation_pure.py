"""Pure non-deployed regression for OWNER'S high overproduction scenario.

Demonstrates 300 authorized pcs vs one 4300-pc kitchen BoM batch.
Legacy Paket/RO planner DOES prorate all 4000 surplus to original stores,
whereas proposed Fase2 FINAL Packing guard keeps all extras in PCK,
requiring separate owner decision. This deliberately does NOT modify
legacy Fase1 allocator or install/upgrade any Odoo addon.
"""
import importlib.util
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "addons"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


legacy = load("ya_legacy_unsafe_excess_demo",
              root / "ya_store_ro/models/package_priority_rules.py")
safe = load("ya_final_surplus_gate_demo",
            root / "ya_sale_production_capacity/models/packing_surplus_guard_rules.py")

# Reproduce the exact *business class* of unwanted distribution in current
# source, NOT claim that such quantities have actually been dispatched.
current = legacy.plan_kitchen_capacity_with_package_priority(
    package_need=0,
    direct_by_store={11: 300},
    bom_output=4300,
    max_capacity=4300,
)
assert current["qty_production"] == 4300, current
assert current["store_allocations"][11]["requested"] == 300
assert current["store_allocations"][11]["allocated"] == 4300
assert current["store_allocations"][11]["surplus"] == 4000
assert current["qty_surplus_distributed"] == 4000
print("LEGACY_AUTO_PRORATA_EXCESS_4000_RISK_REPRODUCED_PASS")
print("LEGACY_REQUESTED_300_AUTOMATIC_ALLOCATION_4300_SOURCE_ONLY")

# Native PCK physical 4400 and RESERVED 100, actual available/free 4300.
# Explicit SO and Paket component tiers + ordinary RO consume just 300.
orders = [
    {"sku":101,"tier":"SO_DIRECT","source_id":1,
     "recipient_id":111,"qty_open":100},
    {"sku":101,"tier":"SO_PAKET_COMPONENT","source_id":2,
     "recipient_id":112,"qty_open":50},
    {"sku":101,"tier":"RO_PAKET_COMPONENT","source_id":3,
     "recipient_id":211,"qty_open":50},
    {"sku":101,"tier":"RO_STORE","source_id":4,
     "recipient_id":212,"qty_open":100},
]
result = safe.preview_only_authorized_entitlements(
    pck_stock_by_sku={101: {"physical":4400, "reserved":100}},
    open_entitlements=orders,
)
assert result["qty_open_authorized_per_sku"] == {101:300}, result
assert sum(x["qty_preview_allocated"] for x in
           result["allocation_rows"]) == 300
assert all(x["qty_surplus_allocated"] == 0
           for x in result["allocation_rows"])
assert result["qty_unallocated_pck_per_sku"] == {101:4000}
assert result["automatic_surplus_to_store_or_so"] == 0
assert result["requires_separate_owner_decision_for_surplus"]
assert result["operator_final_do_not_created"]
print("FASE2_SURPLUS_4000_REMAINS_AT_PCK_NOT_AUTO_ALLOCATED_PASS")
print("NATIVE_HISTORIC_RESERVED_100_NOT_REUSED_PASS")

# Shorter stock requires explicit recipient priority/shortage decision,
# not arbitrary redistribution to another store.
def expect_block(label, stock, rows, match):
    try:
        safe.preview_only_authorized_entitlements(
            pck_stock_by_sku=stock, open_entitlements=rows)
    except safe.SurplusAllocationError as e:
        assert match in str(e), (label, str(e))
        print(label+"_PASS")
    else:
        raise AssertionError(label+"_UNSAFE_ACCEPTED")


expect_block(
    "SO_AND_PAKET_SHORTAGE_REJECTED",
    {101:{"physical":299,"reserved":0}}, orders,
    "STOP_UNDERSTOCK")
expect_block(
    "WRONG_SKU_STOCK_CANNOT_FILL_SHORT",
    {101:{"physical":299,"reserved":0},
     999:{"physical":4000,"reserved":0}},
    orders, "STOP_UNDERSTOCK")
expect_block(
    "DUPLICATE_ENTITLEMENT_REJECTED",
    {101:{"physical":4400,"reserved":100}},
    orders + [dict(orders[0])], "Duplicated entitlement")
expect_block(
    "UNAPPROVED_DESTINATION_REJECTED",
    {101:{"physical":4400,"reserved":100}},
    [dict(orders[0],recipient_id=0)],
    "Destination ID")
expect_block(
    "RESERVED_GREATER_THAN_PHYSICAL_REJECTED",
    {101:{"physical":299,"reserved":300}},
    orders, "reserved cannot exceed physical")

print("FASE2_PURE_SURPLUS_ENTITLEMENT_GUARD_PASS")
print("SCOPE: SOURCE_ONLY NO ADDON IMPORT/UPGRADE NO STOCK DO OR TRANSFERS")
