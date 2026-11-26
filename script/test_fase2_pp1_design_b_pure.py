"""Source-only tests. Run as Feri; no Odoo, database or upgrade."""
import importlib.util
from pathlib import Path

path = Path(__file__).resolve().parents[1] / "addons/ya_sale_production_capacity/models/pp1_design_b_rules.py"
spec = importlib.util.spec_from_file_location("pp1_design_b", path)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def plan(so, pkg, store, maximum=400, bom=200):
    return m.plan_pp1(confirmed_so_qty=so, original_ro_package_qty=pkg,
                      original_ro_store_qty=store, bom_output=bom,
                      published_max=maximum)

def preview(draft, prior, pkg=0, store=0, maximum=400, closed=False):
    return m.preview_before_pp1_release(draft_so_qty=draft,
        confirmed_so_qty=prior, original_ro_package_qty=pkg,
        original_ro_store_qty=store, bom_output=200,
        published_max=maximum, ro_closed=closed)

assert plan(0,0,0)["forecast_mo1_qty"] == 0
assert plan(0,0,190)["forecast_mo1_qty"] == 200
assert plan(0,0,190)["forecast_unallocated_surplus"] == 10
assert plan(20,0,190)["forecast_mo1_qty"] == 400
assert plan(20,0,190)["forecast_unallocated_surplus"] == 190
print("PP1_EARLY_SO_INCLUDED_IN_MO1_PASS")

p = plan(150,90,190,200)
assert p["forecast_so_covered"] == 150
assert p["forecast_ro_package_covered"] == 50
assert p["forecast_ro_package_shortage"] == 40
assert p["forecast_ro_store_covered"] == 0
assert p["forecast_ro_store_shortage"] == 190
assert p["forecast_mo1_qty"] == 200
print("PP1_SO_FIRST_PAKET_THEN_ORDINARY_RO_PASS")

p = preview(5,0)
assert p["marginal_mo1_qty"] == 200
assert p["new_surplus"] == 195
assert p["ro_demand_incomplete_warning"]
p = preview(15,5,closed=True)
assert p["marginal_mo1_qty"] == 0
assert p["absorbed_surplus"] == 15
assert not p["ro_demand_incomplete_warning"]
assert preview(190,20)["marginal_mo1_qty"] == 200
assert preview(10,210)["marginal_mo1_qty"] == 0
print("PP1_CUMULATIVE_SO_MARGINAL_BATCH_AND_RO_CUTOFF_PASS")

p = preview(20,0,store=190,maximum=200)
assert p["marginal_mo1_qty"] == 0
assert p["ro_store_shortage_change"] == 10
assert p["absorbed_surplus"] == 10
assert p["before"]["original_ro_store_qty"] == p["after"]["original_ro_store_qty"] == 190
print("PP1_CAPACITY_DISPLACEMENT_ORIGINAL_RO_UNCHANGED_PASS")

for fn, expected in [
    (lambda: plan(201,0,0,200), "SO exceeds"),
    (lambda: plan(0,0,1,250), "complete BoM"),
    (lambda: plan(0,0,1,400,0), "whole base-UoM"),
    (lambda: plan(True,0,0), "whole base-UoM"),
    (lambda: plan(0,-1,0), "whole base-UoM"),
    (lambda: preview(0,0), "whole base-UoM"),
    (lambda: preview(1,0,closed=None), "Explicit RO cutoff"),
    (lambda: preview(1,400), "SO exceeds"),
]:
    try:
        fn()
    except m.PP1DesignError as exc:
        assert expected in str(exc), str(exc)
    else:
        raise AssertionError("Invalid input accepted: " + expected)
print("PP1_HARD_MAX_BOM_AND_INPUT_GUARDS_PASS")

for maximum in (0,200,400):
    for so in range(0,maximum+1,10):
        for pkg in (0,5,190,400):
            for ro in (0,5,190,400):
                p = plan(so,pkg,ro,maximum)
                assert p["forecast_mo1_qty"] % 200 == 0
                assert p["forecast_mo1_qty"] <= maximum
                assert p["forecast_so_covered"] == so
                assert p["forecast_ro_package_covered"] <= pkg
                assert p["forecast_ro_store_covered"] <= ro
                assert (so + p["forecast_ro_package_covered"] +
                        p["forecast_ro_store_covered"] +
                        p["forecast_unallocated_surplus"]) == p["forecast_mo1_qty"]
print("PP1_AGGREGATE_CONSERVATION_MATRIX_PASS")
print("FASE2_PP1_DESIGN_B_PURE_PASS")
print("SOURCE_ONLY_NO_ODOO_DB_MO_STOCK_OR_DO")
