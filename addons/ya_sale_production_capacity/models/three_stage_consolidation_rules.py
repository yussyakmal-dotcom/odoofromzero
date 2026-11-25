"""SOURCE-ONLY three separated YA Bakery consolidation stages.

Exactly three business checkpoints, as owner clarified:
  1. Pre Produksi 1 freezes confirmed RO + MO1 + historical RO allocations.
  2. Pre Produksi 2 consolidates confirmed customer SO and calculates MO2
     ONLY for SO gaps after existing MO1/MO2 (with whole kitchen BoM).
  3. Final Packing consolidation uses ACTUAL PCK native free stock and
     assigns SO first, RO Paket then ordinary RO; RO partial/zero allowed.

All inputs one SKU/date/slot, whole product base UoM. This is pure math
only, without Odoo/ORM; real workflow must verify source identity, physical
done stock moves, reservations, customer Paket assembly completeness,
company/warehouse and no prior DO. Never overwrite frozen RO allocation.
"""


class ThreeStageError(ValueError):
    pass


def _qty(value, label):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ThreeStageError("%s requires nonnegative integer" % label)
    return value


def stage1_mo1_snapshot(*, original_store_ro, original_ro_package_components,
                         frozen_store_allocation, mo1_planned_output):
    """Read/retain already frozen Pre Production 1 baseline; no mutation."""
    ro = _qty(original_store_ro, "original store RO")
    package_ro = _qty(original_ro_package_components, "original Paket RO")
    frozen = _qty(frozen_store_allocation, "frozen store allocation")
    mo1 = _qty(mo1_planned_output, "MO1 planned output")
    return {
        "original_store_ro": ro,
        "original_ro_package_components": package_ro,
        "frozen_store_allocation_display_only": frozen,
        "mo1_output_frozen": mo1,
        "historic_store_extra_in_frozen_allocated": max(0, frozen-ro),
        "immutable_original_allocation": True,
    }


def stage2_consolidate_so(*, stage1, total_confirmed_so,
                           already_released_mo2,
                           bom_output, published_max):
    """Calculate new MO2 production strictly from SO shortage, not RO."""
    if not isinstance(stage1, dict) or not stage1.get(
            "immutable_original_allocation"):
        raise ThreeStageError("No verified Pre Production 1 baseline")
    so = _qty(total_confirmed_so, "confirmed SO after Paket BoM expansion")
    mo1 = _qty(stage1["mo1_output_frozen"], "frozen MO1 output")
    mo2 = _qty(already_released_mo2, "native MO2 output")
    bom = _qty(bom_output, "real kitchen BoM output")
    maximum = _qty(published_max, "real Published Max")
    if not bom:
        raise ThreeStageError("Kitchen BoM output must be positive")
    if any(x % bom for x in (mo1, mo2, maximum)):
        raise ThreeStageError("MO1/MO2/Max not complete recipe batches")
    if mo1+mo2 > maximum:
        raise ThreeStageError("Existing production exceeds Published Max")
    so_rounded = ((so+bom-1)//bom)*bom
    if so_rounded > maximum:
        raise ThreeStageError("SO needs more than Published Max")
    additional = max(0, so_rounded-mo1-mo2)
    if additional and mo2:
        raise ThreeStageError("One native MO2 per SKU/slot already exists")
    if mo1+mo2+additional > maximum:
        raise ThreeStageError("MO2 would exceed Published Max")
    # Historical frozen RO allocation quantity is informational only.
    return {
        "confirmed_so_qty": so,
        "kitchen_bom_output": bom,
        "published_max": maximum,
        "existing_mo1_output": mo1,
        "existing_mo2_output": mo2,
        "additional_mo2_for_so_only": additional,
        "forecast_total_output": mo1+mo2+additional,
        "original_store_ro_display_only": stage1["original_store_ro"],
        "frozen_store_allocation_display_only": stage1[
            "frozen_store_allocation_display_only"],
        "no_store_restoration_mo2": True,
        "stage1_snapshot_unchanged": True,
        "not_yet_actual_fg_stock": True,
    }


def stage3_final_packing(*, stage1, stage2, pck_native_free_stock,
                          already_fulfilled_so=0,
                          already_fulfilled_ro_package=0,
                          already_fulfilled_ro_store=0):
    """Aggregate final allocation using EXACT PCK native FREE stock only.

    Quantities already fulfilled are deducted from CONFIRMED demand; caller
    must prove these from native moves/reservations and source ledger. Never
    subtract the same native reservation or DO twice. No auto SO partial:
    an unmet confirmed SO is an explicit blocker, while RO can be 0.
    This provides AGGREGATE quantities only. Per-store distribution policy
    and COMPLETE package BoM availability require separate native checks.
    """
    if not isinstance(stage1, dict) or not isinstance(stage2, dict):
        raise ThreeStageError("Missing source consolidation results")
    available = _qty(pck_native_free_stock, "verified PCK native free stock")
    already_so = _qty(already_fulfilled_so, "previously fulfilled SO")
    already_pkg = _qty(already_fulfilled_ro_package, "previously fulfilled Paket RO")
    already_ro = _qty(already_fulfilled_ro_store, "previously fulfilled store RO")
    so = _qty(stage2["confirmed_so_qty"], "confirmed SO total")
    pkg = _qty(stage1["original_ro_package_components"], "original RO Paket")
    ro = _qty(stage1["original_store_ro"], "original RO Store")
    if already_so > so or already_pkg > pkg or already_ro > ro:
        raise ThreeStageError("Previously fulfilled exceeds valid demand")
    due_so = so-already_so
    due_pkg = pkg-already_pkg
    due_ro = ro-already_ro
    if due_so > available:
        raise ThreeStageError("BLOCK_CONFIRMED_SO_NATIVE_FG_SHORTAGE")
    rest = available-due_so
    alloc_pkg = min(due_pkg, rest)
    rest -= alloc_pkg
    alloc_ro = min(due_ro, rest)
    rest -= alloc_ro
    if due_so + alloc_pkg + alloc_ro + rest != available:
        raise ThreeStageError("Stock conservation violated")
    return {
        "confirmed_so_open_qty": due_so,
        "final_so_allocated": due_so,
        "final_ro_package_allocated": alloc_pkg,
        "final_ro_package_shortage_accepted": due_pkg-alloc_pkg,
        "final_ro_store_allocated": alloc_ro,
        "final_ro_store_shortage_accepted": due_ro-alloc_ro,
        "pck_actual_free_stock": available,
        "unallocated_pck_surplus": rest,
        "frozen_store_allocation_display_only": stage1[
            "frozen_store_allocation_display_only"],
        "original_store_order_qty": ro,
        "no_automatic_extra_store_allocation": True,
        "no_standalone_transfer_for_surplus": True,
        "no_new_mo2_during_final_packing": True,
        "preview_only_no_native_do": True,
    }
