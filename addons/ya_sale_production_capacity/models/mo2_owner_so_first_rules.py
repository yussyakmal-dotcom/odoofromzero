"""Fase2 OWNER SO-first / RO-shortage-allowed pure math (SOURCE ONLY).

NO Odoo imports, no ORM, no change to installed ya_sale_production_capacity
19.0.1.1.3, no native MO/DO. No forced MO2 merely to restore old store RO.
Inputs already normalized to whole PRODUCT BASE UoM for ONE SKU/date/slot.

Owner policy:
  1. Protect confirmed SO direct + SO Paket kitchen components FIRST.
  2. Produce MO2 ONLY for SO shortage beyond preexisting MO1/MO2,
     up to REAL Published Planning Max and whole real kitchen BoM batches.
  3. Remaining output can satisfy RO Paket components, then original
     ordinary store RO (both may receive partial or ZERO).
  4. NEVER auto-allocate recipe surplus to stores/other customers.
  5. IMMUTABLE MO1 store allocation is historic, not fresh RO demand.
This math is a projected capacity/allocation preview, NEVER proof of physical
FG at PCK or complete Paket assembly, and never a reservation.
"""


class OwnerSoFirstError(ValueError):
    pass


def _whole(value, label, positive=False):
    if isinstance(value, bool) or not isinstance(value, int):
        raise OwnerSoFirstError("%s must be whole SKU base-UoM" % label)
    if value < 0 or (positive and value == 0):
        raise OwnerSoFirstError("%s must be positive/nonnegative" % label)
    return value


def _roundup(qty, batch):
    return ((qty + batch - 1) // batch) * batch


def plan_so_first_only(*, confirmed_so_qty, existing_mo1_output,
                       existing_mo2_output, published_max,
                       kitchen_bom_output, original_ro_package_qty=0,
                       original_ro_store_qty=0,
                       frozen_store_allocated_for_display=None):
    """Forecast whole-batch *additional MO2 needed only to protect SO*.

    SO qty is aggregated SAME SKU/date/slot from native confirmed ledger,
    including customer Paket kitchen BoM components.
    Original RO qty MUST be original confirmed RO+Paket component needs,
    NOT frozen Pre Production 1 prorata allocations.
    Reject allocation identities incapable of proving that independently.
    """
    so = _whole(confirmed_so_qty, "Confirmed customer SO")
    mo1 = _whole(existing_mo1_output, "Existing MO1 output")
    mo2 = _whole(existing_mo2_output, "Existing MO2 output")
    mx = _whole(published_max, "Published Planning Max")
    batch = _whole(kitchen_bom_output, "Kitchen BoM batch", positive=True)
    pkg = _whole(original_ro_package_qty, "Original RO Paket demand")
    store = _whole(original_ro_store_qty, "Original store RO demand")
    frozen = (
        None if frozen_store_allocated_for_display is None else
        _whole(frozen_store_allocated_for_display,
               "Frozen store allocation for display")
    )
    if any(q % batch for q in (mo1, mo2, mx)):
        raise OwnerSoFirstError("MAX_MO1_MO2_MUST_USE_FULL_KITCHEN_BOM")
    preexisting = mo1 + mo2
    if preexisting > mx:
        raise OwnerSoFirstError("MO1_MO2_ALREADY_EXCEED_PUBLISHED_MAX")
    needed_so_output = _roundup(so, batch)
    if needed_so_output > mx:
        raise OwnerSoFirstError("SO_EXCEEDS_PUBLISHED_MAX_AFTER_BOM_ROUNDING")
    incremental = max(0, needed_so_output - preexisting)
    if incremental and mo2:
        raise OwnerSoFirstError("EXISTING_MO2_NO_SECOND_MO2_ALLOWED")
    if incremental % batch or preexisting + incremental > mx:
        raise OwnerSoFirstError("NATIVE_MO2_BATCH_CAPACITY_INVALID")

    forecast = preexisting + incremental
    so_filled = min(so, forecast)
    so_short = so-so_filled
    # SO complete is a HARD requirement for business promise; native
    # allocation can still fail if physical stock isn't present/free.
    assert so_short == 0
    remaining = forecast-so_filled
    pkg_filled = min(pkg, remaining)
    remaining -= pkg_filled
    store_filled = min(store, remaining)
    remaining -= store_filled

    legit = so + pkg + store
    # Production is driven ONLY by SO, not by a desire to eliminate
    # RO shortages or to preserve a frozen shop allocation.
    assert incremental == max(0, needed_so_output-preexisting)
    assert (so_filled + pkg_filled + store_filled + remaining == forecast)
    assert pkg_filled <= pkg and store_filled <= store
    return {
        "confirmed_so_qty": so,
        "original_ro_package_qty": pkg,
        "original_ro_store_qty": store,
        "frozen_store_allocation_for_display_only": frozen,
        "preexisting_mo1_qty": mo1,
        "preexisting_mo2_qty": mo2,
        "bom_output": batch,
        "published_max": mx,
        "kitchen_qty_required_by_so_rounded": needed_so_output,
        "mo2_increment_due_to_so_only": incremental,
        "forecast_total_output": forecast,
        "forecast_so_covered": so_filled,
        "forecast_so_shortage": so_short,
        "forecast_ro_package_covered": pkg_filled,
        "forecast_ro_package_shortage": pkg-pkg_filled,
        "forecast_ro_store_covered": store_filled,
        "forecast_ro_store_shortage": store-store_filled,
        "total_legitimate_demand": legit,
        "theoretical_extra_not_automatically_allocated": remaining,
        "old_frozen_allocated_above_original_ro": (
            max(0, frozen-store) if frozen is not None else None
        ),
        "old_frozen_store_plus_so_exceeds_forecast": (
            max(0, frozen+so+pkg-forecast)
            if frozen is not None else None
        ),
        "ro_partial_or_zero_allowed": True,
        "no_mo2_for_store_shortage_only": True,
        "no_auto_prorata_of_surplus": True,
        "requires_native_free_stock_and_paket_assembly_verification": True,
        "source_only_not_deployed": True,
    }
