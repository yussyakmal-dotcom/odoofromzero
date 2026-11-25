"""Pure source-only early warning for small YA SO vs large kitchen BoM.

Not imported by addon, no ORM, no stock, NO SO confirmation or MO release.
Does NOT reassign historical MO1 store inventory or claim its stock is free.
Evaluate under SAME date/slot lock from confirmed SO capacity ledger before
any final MO2 release. For large excess, signal explicit risk decision; do not
change existing Published Max, native BoM output or promise customer delivery
from hypothetical excess.

The default 'surplus > total legitimate demand' is only a PREVIEW review
signal, not an owner-approved operator block threshold. Subsequent ORM gate
and approval rights remain pending an explicit owner decision.
"""


class BatchExposureError(ValueError):
    pass


def whole(value, label, allow_zero=True):
    if isinstance(value, bool) or not isinstance(value, int):
        raise BatchExposureError("%s must be integer base-UoM quantity" % label)
    if value < 0 or (not allow_zero and not value):
        raise BatchExposureError("%s cannot be negative/zero" % label)
    return value


def ceil_batch(qty, batch):
    return ((qty + batch - 1) // batch) * batch


def assess_incremental_so_batch_exposure(*, new_so_qty, prior_confirmed_so_qty,
                                          mo1_output, existing_mo2_output,
                                          published_max, bom_output,
                                          ro_paket_component_qty=0,
                                          ro_store_qty=0):
    """Estimate full incremental MO2 and rounding excess per ONE kitchen SKU.

    'new_so_qty' is one customer's proposed SO, aggregated after Paket BoM
    component expansion. 'prior_confirmed_so_qty' is total previously
    confirmed SO for SAME date/slot/SKU, not one order.
    All numbers must be exact whole product base UoM.
    The already frozen MO1 is counted ONCE and never modified. Pending RO
    needs belong to existing confirmed sources, and are *not* inferred from
    old frozen allocations that might include unauthorized recipe surplus.
    """
    new = whole(new_so_qty, "new SO", False)
    prior = whole(prior_confirmed_so_qty, "prior confirmed SO")
    mo1 = whole(mo1_output, "existing MO1")
    mo2 = whole(existing_mo2_output, "existing MO2")
    maximum = whole(published_max, "Published Planning Max")
    batch = whole(bom_output, "kitchen BoM output", False)
    ro_pkg = whole(ro_paket_component_qty, "RO Paket component")
    ro_store = whole(ro_store_qty, "ordinary RO")
    if maximum % batch:
        raise BatchExposureError("Published Max must be multiple of recipe")
    if mo1 % batch or mo2 % batch:
        raise BatchExposureError("Native MO output must be full recipe batches")
    if mo1 + mo2 > maximum:
        raise BatchExposureError("Existing MO exceeds Published Max")
    prior_floor = ceil_batch(prior, batch)
    confirmed_total = prior + new
    now_floor = ceil_batch(confirmed_total, batch)
    if now_floor > maximum:
        raise BatchExposureError(
            "SO cannot be promised within Published Planning Max")
    # Marginal new SO *promise*: earlier confirmed SO may already have
    # exposed one whole batch which this new SO merely shares.
    before_promise = max(mo1 + mo2, prior_floor)
    after_promise = max(mo1 + mo2, now_floor)
    newly_exposed_batch = max(0, after_promise - before_promise)

    gross = confirmed_total + ro_pkg + ro_store
    target = min(maximum, ceil_batch(gross, batch))
    additional_mo2 = max(0, target - mo1 - mo2)
    total_output = mo1 + mo2 + additional_mo2
    uncovered = max(0, gross - total_output)
    theoretical_surplus = max(0, total_output - gross)
    # Existing MO1 may already be allotted to ordinary RO from Fase1 frozen
    # snapshot. This mathematical preview does NOT guarantee available FG.
    ratio = (
        theoretical_surplus / gross if gross else None
    )
    disproportionate = (
        additional_mo2 > 0 and theoretical_surplus > gross
    )
    return {
        "new_so_qty": new,
        "prior_confirmed_so_qty": prior,
        "combined_confirmed_so_qty": confirmed_total,
        "existing_mo1_qty": mo1,
        "existing_mo2_qty": mo2,
        "ro_paket_component_qty": ro_pkg,
        "ro_store_qty": ro_store,
        "total_legitimate_demand": gross,
        "kitchen_bom_output": batch,
        "published_max": maximum,
        "newly_exposed_bom_capacity_due_to_this_so": newly_exposed_batch,
        "total_mo2_increment_if_finalized_now": additional_mo2,
        "total_output_including_existing_mo1_mo2": total_output,
        "uncovered_demand_after_published_max": uncovered,
        "theoretical_surplus_after_rounding": theoretical_surplus,
        "surplus_to_demand_ratio": ratio,
        "disproportionate_mo2_risk_review_suggested": disproportionate,
        "no_auto_release_approval_configured": True,
        "no_stock_or_packing_allocation_inferred": True,
    }
