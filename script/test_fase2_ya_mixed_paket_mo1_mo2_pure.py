"""Pure regression: SAME Paket components from MO1 and incremental MO2.

No Odoo imports, no SQL, no stock/MO/DO changes.
Paket final SKU 900 requires A(101) from kitchen A, B(202) from
kitchen B, and C(303) stocked in PCK. 1 Paket = A1+B2+C1.
RO Paket and ordinary store RO existed at MO1 Pre Produksi.
YA SO1 first reuses MO1 including customer Paket + direct components;
YA SO2 adds customer Paket + direct demand, releasing true MO2 only
for incremental output. MO2 final can also cover remaining RO demand.
At PCK confirm full package component availability before assembly.
"""
import importlib.util
from pathlib import Path

ROOT = Path("addons/ya_sale_production_capacity/models")
SKUS = {"a": 101, "b": 202, "c": 303, "pkg": 900}
A, B, C, P = (SKUS[k] for k in ("a", "b", "c", "pkg"))


def load(name, relative):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, "MISSING_PURE_RULES: %s" % relative
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


capacity = load("ya_capacity_pure_multi", "confirm_capacity_math.py")
mo2 = load("ya_mo2_pure_multi", "mo2_priority_rules.py")
packing = load("ya_packing_package_pure_multi",
               "packing_mixed_package_rules.py")

bom = {P: {A: 1, B: 2, C: 1}}
sources = {A: "KITCHEN", B: "KITCHEN", C: "PCK"}
package_boms = {
    P: {"kitchen": {A: 1, B: 2}, "pck": {C: 1}}
}
so1_direct = {A: 4, B: 2}
so2_direct = {A: 1, B: 1}
so1_pkg = {P: 2}
so2_pkg = {P: 2}
ro_package = {P: 2}
ro_direct = {A: 3, B: 2}
# Initial joint RO need: A2(Paket)+A3(ordinary)=5 => MO1 A6,
# B4(Paket)+B2(ordinary)=6 => MO1 B6.
# Two distinct kitchen workcenters and published BoM output 2 each.
mo1_output = {A: 6, B: 6}
published = {A: 14, B: 18}
bom_output = {A: 2, B: 2}

expand = capacity.expand_so_package_requirements
req1 = expand(so1_direct, so1_pkg, bom, sources)
req2 = expand(so2_direct, so2_pkg, bom, sources)
assert req1 == {
    "kitchen_requirements": {A: 6, B: 6},
    "pck_stock_requirements": {C: 2},
}, req1
assert req2 == {
    "kitchen_requirements": {A: 3, B: 5},
    "pck_stock_requirements": {C: 2},
}, req2
assert P not in req1["kitchen_requirements"]
assert P not in req2["kitchen_requirements"]
print("SO1_PAKET_AND_DIRECT_REUSES_MO1_BOTH_KITCHENS_PASS")
print("SO2_PAKET_AND_DIRECT_REQUIRES_MO2_BOTH_KITCHENS_PASS")

so_total = {
    sku: req1["kitchen_requirements"][sku] +
         req2["kitchen_requirements"][sku]
    for sku in (A, B)
}
assert so_total == {A: 9, B: 11}
pure_so_increment = {}
for sku in (A, B):
    first = capacity.check_so_capacity(
        new_so_qty=req1["kitchen_requirements"][sku],
        existing_so_qty=0,
        published_max=published[sku],
        bom_output=bom_output[sku],
        mo1_output=mo1_output[sku],
    )
    assert first["incremental_mo2_output_needed"] == 0
    second = capacity.check_so_capacity(
        new_so_qty=req2["kitchen_requirements"][sku],
        existing_so_qty=req1["kitchen_requirements"][sku],
        published_max=published[sku],
        bom_output=bom_output[sku],
        mo1_output=mo1_output[sku],
    )
    pure_so_increment[sku] = second["incremental_mo2_output_needed"]
assert pure_so_increment == {A: 4, B: 6}, pure_so_increment
print("SO2_INCREMENTAL_CAPACITY_NOT_DOUBLE_COUNTED_PASS:",
      pure_so_increment)

# MO2 final at H-1 15:30 covers remaining RO Paket and ordinary RO
# WITHOUT violating SO priority, BoM multiples, or Published Max.
mo2_out = {}
for sku in (A, B):
    ro_pkg_component = ro_package[P] * bom[P][sku]
    result = mo2.calculate_mo2_release(
        total_confirmed_so=so_total[sku],
        mo1_output=mo1_output[sku],
        existing_mo2_output=0,
        published_max=published[sku],
        kitchen_bom_output=bom_output[sku],
        ro_package_components=ro_pkg_component,
        ro_direct_finished=ro_direct[sku],
        so_cutoff_closed=True,
        packing_physical_started=False,
    )
    assert result["release_allowed_now"]
    assert result["mo2_incremental_qty"] >= pure_so_increment[sku]
    assert result["mo2_incremental_qty"] % bom_output[sku] == 0
    mo2_out[sku] = result["mo2_incremental_qty"]
assert mo2_out == {A: 8, B: 12}, mo2_out
assert {
    sku: mo1_output[sku] + mo2_out[sku] for sku in (A, B)
} == published
print("MO1_PLUS_MO2_PACKAGE_AND_DIRECT_CAPACITY_CONSERVED_PASS:",
      "MO1:", mo1_output, "MO2:", mo2_out)

# Simulate a PCK inventory quant with 100 ALREADY RESERVED from historical
# transactions for EACH component A/B. Only new MO1+MO2 PCK stock is free.
# Source origin is logical provenance: untracked stock itself is fungible.
stock = {
    A: {"physical": 114, "reserved": 100}, # free14
    B: {"physical": 118, "reserved": 100}, # free18
    C: {"physical": 6, "reserved": 0},
}
merged_so_direct = {A: 5, B: 3}
result = packing.plan_mixed_so_ro_package_packing(
    physical_reserved_by_sku=stock,
    so_direct=merged_so_direct,
    so_package_qty={P: 4},
    ro_package_qty=ro_package,
    ro_direct=ro_direct,
    package_boms=package_boms,
)
assert result["so_package_components"] == {A: 4, B: 8, C: 4}
assert result["so_protected_total"] == {A: 9, B: 11, C: 4}
assert result["ro_package_components"] == {A: 2, B: 4, C: 2}
assert result["ordinary_ro_allocated"] == {A: 3, B: 2}
assert result["ordinary_ro_shortage"] == {}
assert result["unallocated_after_priority"] == {A: 0, B: 1, C: 0}
assert result["free_stock_before"] == {A: 14, B: 18, C: 6}
assert result["ready_for_native_pck_assembly"]
assert result["only_pure_preview_no_ledger_stock_or_do"]
print("PCK_SO_DIRECT_AND_SO_PAKET_FIRST_PASS")
print("PCK_RO_PAKET_THEN_ORDINARY_RO_PASS")
print("PCK_HISTORIC_RESERVED_100_EACH_NOT_FREE_PASS")
print("PCK_ALL_COMPONENTS_AVAILABLE_WHOLE_PAKET_PASS")

def rejects(label, snapshot, expected):
    try:
        packing.plan_mixed_so_ro_package_packing(
            physical_reserved_by_sku=snapshot,
            so_direct=merged_so_direct,
            so_package_qty={P: 4},
            ro_package_qty=ro_package,
            ro_direct=ro_direct,
            package_boms=package_boms,
        )
    except packing.MixedPackingError as exc:
        assert expected in str(exc), (
            "%s WRONG_ERROR %s" % (label, exc)
        )
        print(label + "_PASS:", str(exc))
    else:
        raise AssertionError(label + "_WRONGLY_ALLOWED")

# A missing SO component must stop, never silently decide which customer's
# package/direct line loses supply.
rejects("SO_COMPONENT_SHORTAGE_FAIL_CLOSED",
        {**stock, B: {"physical": 110, "reserved": 100}},
        "SO_UNFULFILLED_STOCK")

# SO components can be fully available, yet RO package B is 1 short.
# Cannot "assemble" one and a half RO Paket.
rejects("RO_PAKET_COMPONENT_SHORTAGE_FAIL_CLOSED",
        {**stock, B: {"physical": 114, "reserved": 100}},
        "RO_PAKET_COMPONENT_SHORTAGE")

# Partial ordinary RO is permitted; remains explicitly visible as shortage.
partial = packing.plan_mixed_so_ro_package_packing(
    physical_reserved_by_sku={
        **stock, B: {"physical": 116, "reserved": 100},
    },
    so_direct=merged_so_direct,
    so_package_qty={P: 4},
    ro_package_qty=ro_package,
    ro_direct=ro_direct,
    package_boms=package_boms,
)
assert partial["ordinary_ro_allocated"] == {A: 3, B: 1}
assert partial["ordinary_ro_shortage"] == {B: 1}
assert partial["needs_ordinary_ro_shortage_review"]
print("RO_ORDINARY_PARTIAL_SHORTAGE_VISIBLE_PASS")

for broken_boms in (
    {P: {"kitchen": {A: 1, B: 2}, "pck": {A: 1}}},
    {P: {"kitchen": {A: 1.5, B: 2}}},
    {P: {"kitchen": {A: 1, B: 2}, "pck": {C: 0}}},
):
    try:
        packing.plan_mixed_so_ro_package_packing(
            physical_reserved_by_sku=stock, so_direct=merged_so_direct,
            so_package_qty={P: 4}, ro_package_qty=ro_package,
            ro_direct=ro_direct, package_boms=broken_boms,
        )
        raise AssertionError("UNSAFE_OR_AMBIGUOUS_PAKET_BOM_ALLOWED")
    except packing.MixedPackingError:
        pass
print("AMBIGUOUS_OR_FRACTIONAL_BOM_FAIL_CLOSED_PASS")

for sku in (A, B):
    try:
        no_more = mo2.calculate_mo2_release(
            total_confirmed_so=so_total[sku],
            mo1_output=mo1_output[sku],
            existing_mo2_output=mo2_out[sku],
            published_max=published[sku],
            kitchen_bom_output=bom_output[sku],
            ro_package_components=ro_package[P] * bom[P][sku],
            ro_direct_finished=ro_direct[sku],
            so_cutoff_closed=True,
            packing_physical_started=True,
        )
    except mo2.Mo2PriorityError:
        raise
    # No remaining need and no new MO2 is required. A duplicate must not
    # create a second native MO; immutable release model enforces this.
    assert no_more["mo2_incremental_qty"] == 0
    assert not no_more["release_allowed_now"]
assert sum(ro_package.values()) == 2
print("PACKAGE_FINAL_SKU_IS_PCK_ASSEMBLY_ONLY_PASS")
print("FASE2_YA_MIXED_PAKET_MO1_MO2_PURE_PASS")
print("SCOPE: SOURCE_PURE_ONLY; NO NATIVE PACKAGE MO, FG, PCK DO OR STOCK WRITE")
