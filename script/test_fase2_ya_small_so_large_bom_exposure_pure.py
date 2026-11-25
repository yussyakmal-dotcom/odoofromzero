"""Source-only regression: small SO orders against 100/200-unit BoM.

No Odoo import/database/stock and no release or confirmation side effects.
Source-only risk preview (operator approval thresholds not yet approved).
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "addons"
RISK_FILE = ROOT / "ya_sale_production_capacity/models/mo2_small_so_batch_risk_rules.py"
CAP_FILE = ROOT / "ya_sale_production_capacity/models/confirm_capacity_math.py"
REL_FILE = ROOT / "ya_sale_production_capacity/models/mo2_priority_rules.py"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader and path.exists(), path
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


risk = load("mo2_risk", RISK_FILE)
capacity = load("so_capacity", CAP_FILE)
release = load("mo2_release", REL_FILE)


def assess(*, new, previous=0, mo1=0, mo2=0,
           max_qty=200, batch=200, ro_pkg=0, ro_store=0):
    return risk.assess_incremental_so_batch_exposure(
        new_so_qty=new, prior_confirmed_so_qty=previous,
        mo1_output=mo1, existing_mo2_output=mo2,
        published_max=max_qty, bom_output=batch,
        ro_paket_component_qty=ro_pkg, ro_store_qty=ro_store)


# One tiny SO will require a whole kitchen recipe batch, if neither MO1
# nor any other valid SO/RO demand covers it.
a = assess(new=5)
assert a["total_mo2_increment_if_finalized_now"] == 200
assert a["theoretical_surplus_after_rounding"] == 195
assert a["surplus_to_demand_ratio"] == 39
assert a["disproportionate_mo2_risk_review_suggested"]
assert a["newly_exposed_bom_capacity_due_to_this_so"] == 200
print("FIRST_SO5_BOM200_EXPOSURE195_RISK_SIGNAL_PASS")

b = assess(new=8, max_qty=100, batch=100)
assert b["total_mo2_increment_if_finalized_now"] == 100
assert b["theoretical_surplus_after_rounding"] == 92
assert b["disproportionate_mo2_risk_review_suggested"]
print("FIRST_SO8_BOM100_EXPOSURE92_RISK_SIGNAL_PASS")

# More SOs of SAME SKU/date/slot share the 200-unit batch promise:
# NOT a separate additional MO per customer.
c = assess(new=5, previous=5)
assert c["newly_exposed_bom_capacity_due_to_this_so"] == 0
assert c["total_mo2_increment_if_finalized_now"] == 200
assert c["theoretical_surplus_after_rounding"] == 190
print("TWO_SMALL_SO_SHARE_ONE_BOM_BATCH_PASS")

d = assess(new=5, previous=145)
assert d["total_legitimate_demand"] == 150
assert d["total_mo2_increment_if_finalized_now"] == 200
assert d["theoretical_surplus_after_rounding"] == 50
assert not d["disproportionate_mo2_risk_review_suggested"]
print("THIRTY_SO5_AGGREGATE_BEFORE_RELEASE_PASS")

e = assess(new=5, previous=195)
assert e["total_mo2_increment_if_finalized_now"] == 200
assert e["theoretical_surplus_after_rounding"] == 0
print("FORTY_SO5_FILL_ONE_BATCH_NO_SURPLUS_PASS")

# Frozen MO1 production (even if it was originally triggered by RO) is
# included ONCE, and does not create MO2 solely because one SO arrives.
f = assess(new=5, mo1=200)
assert f["newly_exposed_bom_capacity_due_to_this_so"] == 0
assert f["total_mo2_increment_if_finalized_now"] == 0
assert f["no_stock_or_packing_allocation_inferred"]
print("SMALL_SO_USE_EXISTING_MO1_CAPACITY_NOT_NEW_MO2_PASS")

# Real RO/Paket component demand can legitimately absorb a batch. This
# is NOT an instruction to ship their unauthorized recipe surplus.
g = assess(new=5, ro_pkg=95, ro_store=100)
assert g["total_legitimate_demand"] == 200
assert g["total_mo2_increment_if_finalized_now"] == 200
assert g["theoretical_surplus_after_rounding"] == 0
print("VALID_RO_AND_PAKET_DEMAND_REDUCES_BATCH_SURPLUS_PASS")

# Ensure actual pure baseline SO Confirm and final MO2 arithmetic agree
# with the proposed early-warning quantities on a relevant fixture.
confirmed = capacity.check_so_capacity(
    new_so_qty=5, existing_so_qty=0,
    published_max=200, bom_output=200, mo1_output=0)
released = release.calculate_mo2_release(
    total_confirmed_so=5,
    mo1_output=0, existing_mo2_output=0,
    published_max=200, kitchen_bom_output=200,
    ro_package_components=0, ro_direct_finished=0,
    so_cutoff_closed=True, packing_physical_started=False)
assert confirmed["incremental_mo2_output_needed"] == 200
assert released["mo2_incremental_qty"] == a[
    "total_mo2_increment_if_finalized_now"]
print("EXISTING_CONFIRM_AND_MO2_MATH_MATCH_EARLY_RISK_PASS")

# Capacity has HARD limits, independent of whether a warning is dismissed.
for options in (
    {"new":201},
    {"new":5,"max_qty":100,"batch":200},
    {"new":5,"mo1":1},
    {"new":5,"mo2":100,"batch":200},
):
    try:
        assess(**options)
    except risk.BatchExposureError:
        pass
    else:
        raise AssertionError("INVALID CAPACITY/MO EXEMPTION ACCEPTED")
print("PUBLISHED_MAX_AND_NATIVE_RECIPE_INVARIANTS_PASS")

print("FASE2_SMALL_SO_LARGE_BOM_RISK_PURE_PASS")
print("SCOPE: SOURCE ONLY. NO NEW OPERATOR BLOCK, NO SO CONFIRM,"
      " MO RELEASE, STOCK OR RO SNAPSHOT CHANGE")
