"""Pure SOURCE-ONLY pre-Confirm Sales impact preview for YA Pre Produksi 2.

Read under SAME date-slot-SKU consistent snapshot/lock in future ORM
adapter; DO NOT rely on the current frozen RO allocation surplus or claim
MO1 produced units are physically free at PCK. No Odoo import/DB access,
no writes, no module import/upgrade, no role/cutoff bypass.

Important difference:
- incremental production caused by the DRAFT SO = forecast AFTER vs BEFORE;
- marginal surplus caused/absorbed by draft = excess AFTER - BEFORE;
- pre-existing excess may be absorbed by the SO (negative difference);
- even if MO1 output covers all demand, pre-existing frozen RO allocation
  may be displaced by giving SO priority; report this explicitly.
Actual PCK DO needs further physical stock/lot/reservation and full Paket
component assembly checks. This preview is only a projection.
"""


class SaleImpactError(ValueError):
    pass


def _whole(x, label, positive=False):
    if isinstance(x, bool) or not isinstance(x, int):
        raise SaleImpactError("%s requires whole base UoM" % label)
    if x < 0 or (positive and x == 0):
        raise SaleImpactError("%s must be %s" % (
            label, "positive" if positive else "nonnegative"
        ))
    return x


def _round(qty, batch):
    return ((qty + batch - 1) // batch) * batch


def preview_draft_so_production_impact(*, new_so_qty,
                                       confirmed_so_qty,
                                       frozen_ro_package_qty,
                                       frozen_ro_store_qty,
                                       mo1_output,
                                       existing_mo2_output,
                                       bom_output,
                                       published_max):
    """Per base-UoM SKU; inputs are from authoritative raw Confirmed sources.

    Requires confirmed SO ledger (EXCLUDE current draft), real frozen RO
    source demand only (NOT old prorated qty_allocated), real released MO1,
    existing native MO2 if any, same SKU/date/slot Published Max & BoM.
    Assert all qty in PRODUCT BASE UoM before calling. No DO/stock authority.
    """
    draft = _whole(new_so_qty, "Draft SO new Qty", positive=True)
    prior = _whole(confirmed_so_qty, "Confirmed SO Qty")
    ro_pkg = _whole(frozen_ro_package_qty, "RO Paket component Qty")
    ro_store = _whole(frozen_ro_store_qty, "RO Store Qty")
    mo1 = _whole(mo1_output, "MO1 output")
    mo2 = _whole(existing_mo2_output, "Native MO2 output")
    batch = _whole(bom_output, "Kitchen BoM output", positive=True)
    maximum = _whole(published_max, "Published Planning Max")
    if maximum % batch or mo1 % batch or mo2 % batch:
        raise SaleImpactError("BoM, MO1/MO2 and Max batch multiple mismatch")
    if mo1 + mo2 > maximum:
        raise SaleImpactError("Existing MO1+MO2 exceeds Published Max")
    if _round(prior, batch) > maximum:
        raise SaleImpactError("Previous SO promises exceed Published Max")
    if _round(prior + draft, batch) > maximum:
        raise SaleImpactError(
            "BLOCK_SO_CONFIRM: newly Confirmed SO batch needs exceed Max"
        )

    current_native = mo1 + mo2

    def forecast(sales_qty):
        gross = sales_qty + ro_pkg + ro_store
        rounded = _round(gross, batch)
        # SO capacity is absolutely protected within Published Max;
        # RO may be short and requires an explicit Packing decision.
        target = min(maximum, rounded)
        output = max(current_native, target)
        extra = max(0, output-gross)
        missing = max(0, gross-output)
        available_for_ro = max(0, output-sales_qty)
        pkg_served = min(ro_pkg, available_for_ro)
        store_served = min(ro_store, available_for_ro-pkg_served)
        return {
            "legitimate_demand": gross,
            "rounded_unrestricted_gross": rounded,
            "forecast_output": output,
            "projected_mo2_increment_from_native": output-current_native,
            "projected_extra_unallocated": extra,
            "total_shortage": missing,
            "ro_paket_shortage": ro_pkg-pkg_served,
            "ro_store_shortage": ro_store-store_served,
        }

    before = forecast(prior)
    after = forecast(prior+draft)
    delta_output = after["forecast_output"]-before["forecast_output"]
    delta_extra = (
        after["projected_extra_unallocated"]
        - before["projected_extra_unallocated"]
    )
    assert delta_output >= 0
    assert delta_extra == delta_output-draft - (
        after["total_shortage"] - before["total_shortage"])
    assert after["forecast_output"] <= maximum
    # A new SO cannot increase a SO-agnostic product's capacity beyond Max;
    # if it reduces the RO share, make that effect visible before Confirm.
    displaced = (
        after["ro_paket_shortage"]-before["ro_paket_shortage"],
        after["ro_store_shortage"]-before["ro_store_shortage"]
    )
    if any(delta < 0 for delta in displaced):
        raise SaleImpactError("RO shortage projection decreased unexpectedly")
    return {
        "new_draft_so_qty": draft,
        "prior_confirmed_so_qty": prior,
        "ro_paket_component_qty": ro_pkg,
        "ro_store_qty": ro_store,
        "mo1_output": mo1,
        "existing_mo2_output": mo2,
        "bom_output": batch,
        "published_max": maximum,
        "before_draft": before,
        "after_draft": after,
        "additional_mo2_due_to_this_draft_vs_baseline": delta_output,
        "change_in_theoretical_surplus_due_to_this_draft": delta_extra,
        "new_theoretical_surplus_created_by_draft": max(0, delta_extra),
        "existing_theoretical_surplus_absorbed_by_draft": max(0, -delta_extra),
        "expected_total_surplus_after_draft": after[
            "projected_extra_unallocated"
        ],
        "increased_ro_paket_shortage": displaced[0],
        "increased_ro_store_shortage": displaced[1],
        "needs_priority_displacement_review": any(displaced),
        "needs_high_surplus_review_suggestion": (
            delta_extra > 0 and after["projected_extra_unallocated"] >
            after["legitimate_demand"]
        ),
        "confirm_does_not_release_mo2": True,
        "pending_native_stock_and_paket_assembly_gates": True,
        "source_only_not_deployed": True,
    }
