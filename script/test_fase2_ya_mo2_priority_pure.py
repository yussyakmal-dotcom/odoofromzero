"""Pure offline regression for MO2 final Qty and Packing priority buckets.

Run as Feri: python3 script/test_fase2_ya_mo2_priority_pure.py
Never connects to Odoo or modifies any database.
"""
import importlib.util
from pathlib import Path

p = Path.cwd() / "addons/ya_sale_production_capacity/models/mo2_priority_rules.py"
spec = importlib.util.spec_from_file_location("ya_mo2_rules", str(p))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def blocked(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except m.Mo2PriorityError:
        return
    raise AssertionError("EXPECTED_REJECTION_NOT_RAISED: %s" % fn.__name__)


def plan(so, mo1, mo2, max_qty, bom, closed=True, started=False,
         ro_pkg=0, ro=0):
    return m.calculate_mo2_release(
        so, mo1, mo2, max_qty, bom,
        ro_package_components=ro_pkg,
        ro_direct_finished=ro,
        so_cutoff_closed=closed,
        packing_physical_started=started,
    )


# Batch 24, MO1 already 48: SO 1-48 reuse MO1, no second MO.
assert plan(48, 48, 0, 96, 24)["mo2_incremental_qty"] == 0
# 49 SO units need 72 output: MO2 = 24 only, not whole SO.
x = plan(49, 48, 0, 96, 24)
assert x["mo2_incremental_qty"] == 24
assert x["release_allowed_now"]
assert x["uncommitted_capacity_after_mos"] == 24
# Sales before cutoff may be promised but MO2 cannot be RELEASED yet.
x = plan(49, 48, 0, 96, 24, closed=False)
assert x["mo2_incremental_qty"] == 24
assert not x["release_allowed_now"]
# MO2 also preserves RO demand when published kitchen capacity remains.
# MO1 48 was originally planned for RO, SO 48 arrives: target becomes 96,
# so MO2 48 keeps stores supplied instead of silently taking their allocation.
x = plan(48, 48, 0, 96, 24, ro=48)
assert x["mo2_incremental_qty"] == 48
assert x["total_output_target_with_ro"] == 96
# If SO + Paket RO + ordinary RO exceed Max, cap output at Published Max.
# Packing will protect SO, then RO Paket, then ordinary RO actual stock.
x = plan(49, 48, 0, 72, 24, ro_pkg=12, ro=20)
assert x["total_output_target_with_ro"] == 72
assert x["mo2_incremental_qty"] == 24
assert x["ro_package_kitchen_qty"] == 12

# Existing MO2 already covers SO: don't make another MO.
assert plan(49, 48, 24, 96, 24)["mo2_incremental_qty"] == 0
# Releasing a second MO2 for new demand is forbidden.
blocked(plan, 73, 48, 24, 96, 24)
# Cannot add manufacturing after Packing dispatch.
blocked(plan, 49, 48, 0, 96, 24, True, True)
# Confirmed SO cannot exceed max, even with protected RO reduction.
blocked(plan, 97, 48, 0, 96, 24)
# MO1+MO2 must fit max, batch conversion strict.
blocked(plan, 1, 96, 24, 96, 24)
blocked(plan, 1, 47, 0, 96, 24)
blocked(plan, 1, 48, 0, 95, 24)
blocked(plan, 1.5, 48, 0, 96, 24)

# SO protected first, then RO Paket components, then ordinary RO.
a = m.preview_packing_buckets(10, 3, 2, 2, 7)
assert (a["so_fulfilled"], a["ro_package_fulfilled"],
        a["ro_direct_fulfilled"], a["ro_direct_shortage"]) == (5, 2, 3, 4)
assert a["unallocated_finished"] == 0
assert a["requires_exception_review"]  # RO shortage still needs explicit review.
# Actual stock shortage must be explicit. Do NOT create stock.
a = m.preview_packing_buckets(4, 3, 2, 2, 7)
assert a["so_shortage"] == 1
assert a["ro_package_fulfilled"] == 0
assert a["ro_direct_fulfilled"] == 0
assert a["requires_exception_review"]
# Extra output stays unallocated pending native authorized transfer.
a = m.preview_packing_buckets(20, 3, 2, 2, 7)
assert a["unallocated_finished"] == 6
assert not a["requires_exception_review"]
# Only total buckets, not fabricated customer/store allocations.
blocked(m.preview_packing_buckets, -1, 1, 1, 1, 1)
blocked(m.preview_packing_buckets, 5, 1, 1, 0.5, 1)

print("FASE2_YA_MO2_PRIORITY_PURE_PASS")
print("MO2: MO1 reuse, SO + RO kitchen demand, Max cap, batch increment and duplicate guards")
print("PACKING_PREVIEW: actual-stock SO first, RO Paket, ordinary RO; shortage shown")
print("SCOPE: PURE_SOURCE_ONLY; no MO2 release, PCK transfers, SO/RO delivery or mutation")
