"""Pure regression of THREE separate YA consolidations.

NO Odoo, no DB, no installed addon upgrade. User fixed:
1 Pre Produksi 1 RO original 190; frozen store allocation195; MO1 200.
2 Pre Produksi 2 confirmed customer SO5/20/200, SO-only incremental MO2.
3 FINAL Packing native free stock200, SO FIRST; store may receive 0.
"""
import importlib.util
from pathlib import Path

root = Path(__file__).resolve().parents[1] / "addons/ya_sale_production_capacity/models"
path = root / "three_stage_consolidation_rules.py"
spec = importlib.util.spec_from_file_location("pure_three_stage", path)
assert spec and spec.loader and path.exists(), path
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

stage1 = m.stage1_mo1_snapshot(
    original_store_ro=190,
    original_ro_package_components=0,
    frozen_store_allocation=195,
    mo1_planned_output=200)
assert stage1["original_store_ro"] == 190
assert stage1["frozen_store_allocation_display_only"] == 195
assert stage1["historic_store_extra_in_frozen_allocated"] == 5
print("STAGE1_PREPROD1_ORIGINAL_RO190_VS_FROZEN195_PRESERVED_PASS")

for so, store, store_short, unallocated in [
    (5, 190, 0, 5),
    (20, 180, 10, 0),
    (200, 0, 190, 0),
]:
    stage2 = m.stage2_consolidate_so(
        stage1=stage1,
        total_confirmed_so=so,
        already_released_mo2=0,
        bom_output=200,
        published_max=400)
    assert stage2["additional_mo2_for_so_only"] == 0
    assert stage2["forecast_total_output"] == 200
    stage3 = m.stage3_final_packing(
        stage1=stage1, stage2=stage2,
        pck_native_free_stock=200)
    assert stage3["final_so_allocated"] == so
    assert stage3["final_ro_store_allocated"] == store
    assert stage3["final_ro_store_shortage_accepted"] == store_short
    assert stage3["unallocated_pck_surplus"] == unallocated
    assert stage3["no_automatic_extra_store_allocation"]
    assert stage3["no_new_mo2_during_final_packing"]
print("STAGE2_SO_ONLY_MO2_ZERO_IF_MO1_ENOUGH_PASS")
print("STAGE3_PCK_FINAL_SO_FIRST_RO_PARTIAL_OR_ZERO_PASS")

# Even when RO needs 300 and MO1 is 200, stage2 must not generate extra
# manufacturing if SO needs only 5. Native Packing accepts RO shortage105.
stage1_large = m.stage1_mo1_snapshot(
    original_store_ro=300,
    original_ro_package_components=0,
    frozen_store_allocation=300,
    mo1_planned_output=200)
stage2_large = m.stage2_consolidate_so(
    stage1=stage1_large, total_confirmed_so=5,
    already_released_mo2=0,bom_output=200,published_max=400)
stage3_large = m.stage3_final_packing(
    stage1=stage1_large,stage2=stage2_large,
    pck_native_free_stock=200)
assert stage2_large["additional_mo2_for_so_only"] == 0
assert stage3_large["final_ro_store_allocated"] == 195
assert stage3_large["final_ro_store_shortage_accepted"] == 105
print("RO_SHORTAGE_NEVER_FORCES_ADDITIONAL_MO2_PASS")

# New sales qty205 does require *one* genuine incremental recipe200.
stage2_inc = m.stage2_consolidate_so(
    stage1=stage1, total_confirmed_so=205,
    already_released_mo2=0,
    bom_output=200,published_max=400)
assert stage2_inc["additional_mo2_for_so_only"] == 200
assert stage2_inc["forecast_total_output"] == 400
# However final allocation uses REAL PCK stock, not planned output 400.
try:
    m.stage3_final_packing(
        stage1=stage1,stage2=stage2_inc,
        pck_native_free_stock=200)
except m.ThreeStageError as exc:
    assert "BLOCK_CONFIRMED_SO_NATIVE_FG_SHORTAGE" in str(exc)
else:
    raise AssertionError("PHANTOM_MO2_OUTPUT_USED_AS_REAL_PACKING_STOCK")
print("NATIVE_PCK_STOCK_NOT_INFERRED_FROM_PLANNED_MO2_PASS")

# Native PCK FG ready400; SO205 and store190 -> real extra5 (not sent).
final_ready = m.stage3_final_packing(
    stage1=stage1,stage2=stage2_inc,
    pck_native_free_stock=400)
assert final_ready["final_so_allocated"] == 205
assert final_ready["final_ro_store_allocated"] == 190
assert final_ready["unallocated_pck_surplus"] == 5
print("STAGE3_ACTUAL_FREE_STOCK_ONLY_EXTRA_UNALLOCATED_PASS")

# Paket priority: confirmed customer component SO150 first, then
# store Paket components90, then direct RO190; RO store allocation zero.
s1_pkg = m.stage1_mo1_snapshot(
    original_store_ro=190,
    original_ro_package_components=90,
    frozen_store_allocation=195,
    mo1_planned_output=200)
s2_pkg = m.stage2_consolidate_so(
    stage1=s1_pkg,total_confirmed_so=150,
    already_released_mo2=0,bom_output=200,published_max=400)
s3_pkg = m.stage3_final_packing(
    stage1=s1_pkg,stage2=s2_pkg,pck_native_free_stock=200)
assert s3_pkg["final_so_allocated"] == 150
assert s3_pkg["final_ro_package_allocated"] == 50
assert s3_pkg["final_ro_package_shortage_accepted"] == 40
assert s3_pkg["final_ro_store_allocated"] == 0
assert s3_pkg["final_ro_store_shortage_accepted"] == 190
print("FINAL_SO_BEFORE_RO_PAKET_BEFORE_RO_DIRECT_PASS")
print("NOTE_PAKET_REQUIRES_SEPARATE_COMPLETE_BOM_ASSEMBLY")

# Previous confirmed customer quantities already fulfilled are NOT
# available to allocate a second time; inputs to native adapter must
# separately account for stock reservation and previous recipient ledger.
s2 = m.stage2_consolidate_so(
    stage1=stage1,total_confirmed_so=20,
    already_released_mo2=0,bom_output=200,published_max=400)
out = m.stage3_final_packing(
    stage1=stage1,stage2=s2,
    pck_native_free_stock=180,
    already_fulfilled_so=20)
assert out["confirmed_so_open_qty"] == 0
assert out["final_so_allocated"] == 0
assert out["final_ro_store_allocated"] == 180
assert out["final_ro_store_shortage_accepted"] == 10
print("ALREADY_FULFILLED_SO_NOT_ALLOCATED_TWICE_PASS")

print("FASE2_OWNER_THREE_CONSOLIDATIONS_PURE_PASS")
print("SCOPE: PURE ONLY; NO INSTALLED ADDON CHANGE, STOCK/MO/DO")
