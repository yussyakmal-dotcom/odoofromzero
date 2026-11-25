"""Pure Sales Admin Quotation PRE-CONFIRM preview: marginal MO2 and surplus.

Source only. No Odoo, no DB, no native MO release, no stock movements.
Comparisons must be made under same date/slot/sku authoritative snapshot
and refreshed after lock at actual Confirm time in future ORM integration.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "addons/ya_sale_production_capacity/models"

def load(name, filename):
    path = ROOT / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader and path.exists()
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

mod = load("draft_so_delta_pure", "so_draft_production_impact_rules.py")
expand = load("existing_sale_package_expansion", "confirm_capacity_math.py")


def preview(new, prior=0, pkg=0, ro=0, mo1=0, mo2=0, batch=200,
            maximum=200):
    return mod.preview_draft_so_production_impact(
        new_so_qty=new,
        confirmed_so_qty=prior,
        frozen_ro_package_qty=pkg,
        frozen_ro_store_qty=ro,
        mo1_output=mo1, existing_mo2_output=mo2,
        bom_output=batch,
        published_max=maximum,
    )


# SO1: 5 pcs can trigger a whole batch 200, visible BEFORE Confirm.
a = preview(5)
assert a["additional_mo2_due_to_this_draft_vs_baseline"] == 200
assert a["new_theoretical_surplus_created_by_draft"] == 195
assert a["expected_total_surplus_after_draft"] == 195
assert a["needs_high_surplus_review_suggestion"]
print("DRAFT_SO5_BOM200_BEFORE_CONFIRM_SHOWS_PLUS195_PASS")

b = preview(8, batch=100, maximum=100)
assert b["additional_mo2_due_to_this_draft_vs_baseline"] == 100
assert b["expected_total_surplus_after_draft"] == 92
print("DRAFT_SO8_BOM100_BEFORE_CONFIRM_SHOWS_PLUS92_PASS")

# Multiple SO for same SKU share batch; count only marginal delta, not
# each SO as a separate 200-pc recipe.
c = preview(5, prior=5)
assert c["before_draft"]["forecast_output"] == 200
assert c["after_draft"]["forecast_output"] == 200
assert c["additional_mo2_due_to_this_draft_vs_baseline"] == 0
assert c["existing_theoretical_surplus_absorbed_by_draft"] == 5
assert c["expected_total_surplus_after_draft"] == 190
print("SECOND_SMALL_SO_SHARES_PRIOR_SKU_BATCH_NO_DOUBLE_PRODUCTION_PASS")

d = preview(5, prior=195)
assert d["after_draft"]["legitimate_demand"] == 200
assert d["expected_total_surplus_after_draft"] == 0
assert d["additional_mo2_due_to_this_draft_vs_baseline"] == 0
assert d["existing_theoretical_surplus_absorbed_by_draft"] == 5
print("SO5_COMPLETES_PREVIOUS_SO195_TO_FULL_BATCH_PASS")

# RO Paket and store demand are legitimate demand; this SO can help use
# their rounding extra. Do not infer that frozen historical store allocation
# has become physically available to customers.
e = preview(5, pkg=95, ro=100)
assert e["before_draft"]["forecast_output"] == 200
assert e["before_draft"]["projected_extra_unallocated"] == 5
assert e["after_draft"]["projected_extra_unallocated"] == 0
assert e["additional_mo2_due_to_this_draft_vs_baseline"] == 0
print("SO5_ABSORBS_LEGITIMATE_RO_PAKET_MO1_ROUNDING_PASS")

# MO1 already 200 with RO store entitlement 200; SO5 increases shortage
# to RO store by 5. Forecast extra remains 0 and SO has NO new MO2 output.
# This warning is important even if the original immutable pre-production
# allocations still show RO=200 and the SO was confirmed later.
f = preview(5, ro=200, mo1=200)
assert f["additional_mo2_due_to_this_draft_vs_baseline"] == 0
assert f["new_theoretical_surplus_created_by_draft"] == 0
assert f["increased_ro_store_shortage"] == 5
assert f["needs_priority_displacement_review"]
print("SO_DISPLACES_FROZEN_RO_CAPACITY_SHOWN_BEFORE_CONFIRM_PASS")

g = preview(5, pkg=200, maximum=200)
assert g["increased_ro_paket_shortage"] == 5
assert g["needs_priority_displacement_review"]
print("SO_DISPLACES_PAKET_COMPONENT_REQUIRES_ASSEMBLY_REVIEW_PASS")

# A multi-line Quotation containing Paket and direct SKU components must
# merge them FIRST into kitchen demand, then preview every SKU once.
bundle = expand.expand_so_package_requirements(
    direct_kitchen={11:5},
    package_qty={900:2},
    bom_components={900:{11:2,22:3,33:1}},
    component_source={11:"KITCHEN",22:"KITCHEN",33:"PCK"},
)
assert bundle["kitchen_requirements"] == {11:9,22:6}
assert bundle["pck_stock_requirements"] == {33:2}
r11 = preview(bundle["kitchen_requirements"][11],batch=100,maximum=100)
r22 = preview(bundle["kitchen_requirements"][22],batch=200,maximum=200)
assert r11["new_theoretical_surplus_created_by_draft"] == 91
assert r22["new_theoretical_surplus_created_by_draft"] == 194
assert sum(x["new_theoretical_surplus_created_by_draft"]
           for x in (r11,r22)) == 285
print("DRAFT_SO_PAKET_COMPONENT_AND_DIRECT_DEDUP_PER_KITCHEN_SKU_PASS")

# Capacity rules remain hard stops; warning/approval alone cannot waive Max.
for invalid in (
    {"new":201},
    {"new":5,"prior":200},
    {"new":5,"maximum":100},
    {"new":5,"mo1":1},
    {"new":5,"mo2":100},
):
    try:
        preview(**invalid)
    except mod.SaleImpactError:
        pass
    else:
        raise AssertionError("INVALID_NATIVE_CAPACITY_WAS_ACCEPTED: %s" % invalid)
print("HARD_PUBLISHED_MAX_AND_BOM_GATES_UNCHANGED_PASS")
print("FASE2_SALES_ADMIN_PRECONFIRM_IMPACT_PURE_PASS")
print("SCOPE_SOURCE_ONLY_NO_OD00_UI_CONFIRM_MO2_OR_STOCK_MUTATION")
