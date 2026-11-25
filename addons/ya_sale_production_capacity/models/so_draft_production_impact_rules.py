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


def _reconcile_frozen_ro_snapshot(rows, original_ro_qty):
    """Keep original store RO distinct from frozen possibly inflated allocation.

    Rows are SAME SKU/date/slot only, from immutable batch allocation, never
    taken as new SO/Paket demand. Aggregate per source store (not just global
    net), so surplus at store A cannot be hidden by shortage at store B.
    """
    if rows is None:
        return {
            "snapshot_checked": False,
            "frozen_allocated_qty": None,
            "frozen_surplus_qty": None,
            "over_original_per_store_qty": None,
            "requires_frozen_snapshot_reconciliation": False,
        }
    if not isinstance(rows, (list, tuple)):
        raise SaleImpactError("Frozen RO snapshot must be rows or None")
    totals = {
        "requested": 0, "allocated": 0, "surplus": 0,
        "shortage": 0, "over_original_per_store": 0,
    }
    seen = set()
    anomalies = []
    for row in rows:
        if not isinstance(row, dict):
            raise SaleImpactError("Frozen RO snapshot line must be mapping")
        store_id = _whole(row.get("store_id"), "Frozen store ID", True)
        ro_id = _whole(row.get("ro_id"), "Frozen RO source ID", True)
        identity = (ro_id, store_id)
        if identity in seen:
            raise SaleImpactError("Duplicate frozen RO source/store row")
        seen.add(identity)
        requested = _whole(row.get("qty_requested"), "Original store RO")
        allocated = _whole(row.get("qty_allocated"), "Frozen allocation")
        surplus = _whole(row.get("qty_surplus"), "Frozen surplus")
        shortage = _whole(row.get("qty_shortage"), "Frozen shortage")
        if shortage > requested:
            raise SaleImpactError("Frozen shortage larger than original RO")
        if allocated != requested-shortage+surplus:
            raise SaleImpactError("Frozen store RO accounting identity invalid")
        totals["requested"] += requested
        totals["allocated"] += allocated
        totals["surplus"] += surplus
        totals["shortage"] += shortage
        over = max(0, allocated-requested)
        totals["over_original_per_store"] += over
        if surplus or shortage or over:
            anomalies.append({
                "ro_id": ro_id, "store_id": store_id,
                "original_ro_qty": requested,
                "frozen_allocated_qty": allocated,
                "frozen_surplus_qty": surplus,
                "frozen_shortage_qty": shortage,
                "allocated_above_original_ro_qty": over,
            })
    if totals["requested"] != original_ro_qty:
        raise SaleImpactError(
            "STOP_ORIGINAL_RO_MISMATCH: snapshot requested != raw RO"
        )
    return {
        "snapshot_checked": True,
        "original_order_qty": totals["requested"],
        "frozen_allocated_qty": totals["allocated"],
        "frozen_surplus_qty": totals["surplus"],
        "frozen_shortage_qty": totals["shortage"],
        "over_original_per_store_qty": totals["over_original_per_store"],
        "snapshot_rows_requiring_review": anomalies,
        "requires_frozen_snapshot_reconciliation": bool(
            totals["surplus"] or totals["shortage"] or
            totals["over_original_per_store"]
        ),
    }


def preview_draft_so_production_impact(*, new_so_qty,
                                       confirmed_so_qty,
                                       frozen_ro_package_qty,
                                       frozen_ro_store_qty,
                                       mo1_output,
                                       existing_mo2_output,
                                       bom_output,
                                       published_max,
                                       frozen_ro_store_snapshot_rows=None):
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
    frozen_ro_audit = _reconcile_frozen_ro_snapshot(
        frozen_ro_store_snapshot_rows, ro_store
    )
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
    assert delta_extra == delta_output-draft + (
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
    frozen_claim_after = (
        (prior+draft+ro_pkg+frozen_ro_audit["frozen_allocated_qty"])
        if frozen_ro_audit["snapshot_checked"] else None
    )
    frozen_claim_over_output = (
        max(0, frozen_claim_after-after["forecast_output"])
        if frozen_claim_after is not None else None
    )
    return {
        "new_draft_so_qty": draft,
        "prior_confirmed_so_qty": prior,
        "ro_paket_component_qty": ro_pkg,
        "ro_store_qty": ro_store,
        # Qty requested from original confirmed RO is the ONLY legitimate
        # store demand in the production forecast. Frozen qty_allocated
        # might include extra recipe surplus and is never substituted here.
        "ro_store_original_order_qty": ro_store,
        "ro_store_frozen_snapshot_diagnostics": frozen_ro_audit,
        "ro_store_frozen_allocated_qty_for_display_only":
            frozen_ro_audit["frozen_allocated_qty"],
        "ro_store_frozen_surplus_for_display_only":
            frozen_ro_audit["frozen_surplus_qty"],
        "potential_frozen_allocation_plus_so_claim_after":
            frozen_claim_after,
        "potential_double_claim_above_forecast_production":
            frozen_claim_over_output,
        "must_reconcile_frozen_snapshot_before_final_do": (
            frozen_ro_audit["requires_frozen_snapshot_reconciliation"] or
            (frozen_claim_over_output is not None
             and frozen_claim_over_output > 0)
        ),
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
