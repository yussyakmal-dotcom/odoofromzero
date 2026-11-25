"""Fase 2 source-only pure rules: MO2 and late Packing stock priority.

No Odoo env, ORM writes, MO creation, allocation to actual SO/RO recipients,
or manufacturing/stock move. Inputs are integer finished kitchen SKU units
in product BASE UoM after BoM and UoM validation. A delivery date/slot and
SKU-specific atomic lock are the ORM adapter's responsibility.

Priority agreed with owner: confirmed SO kitchen demand > Paket RO kitchen
components > ordinary store RO. Existing MO1 output serves SO FIRST and is
never counted twice. Last-mile recipient distribution remains a distinct
Packing step based on real completed production and real available stock.
"""

class Mo2PriorityError(ValueError):
    pass


def _whole(value, field, positive=False):
    if isinstance(value, bool) or not isinstance(value, int):
        raise Mo2PriorityError("%s must be integer in SKU base UoM" % field)
    if value < 0 or (positive and value == 0):
        raise Mo2PriorityError("%s must be %s" % (
            field, "positive" if positive else "nonnegative"))
    return value


def _round_up(quantity, batch):
    return ((quantity + batch - 1) // batch) * batch


def calculate_mo2_release(total_confirmed_so, mo1_output, existing_mo2_output,
                          published_max, kitchen_bom_output, *,
                          ro_package_components=0, ro_direct_finished=0,
                          so_cutoff_closed, packing_physical_started):
    """Compute incremental MO2, never reissue MO1.

    ro_package_components + ro_direct_finished MUST come from real
    confirmed RO demand (converted to base UoM), not from the already
    prorated/frozen store allocations in Packing. SO is protected first;
    any RO shortfall is handled at final Packing by real stock priority.
    so_cutoff_closed MUST mean the owner-approved final MO2 lock moment
    has been reached. It cannot be inferred from wall-clock here.
    existing_mo2_output MUST reflect all already-created MO2 for this SKU.
    This function allows a preview before final lock (ready=False); release
    requires ready=True and no physically started Packing.
    """
    so = _whole(total_confirmed_so, "Confirmed SO qty")
    ro_pkg = _whole(ro_package_components, "RO Paket kitchen component Qty")
    ro_direct = _whole(ro_direct_finished, "ordinary store RO Qty")
    mo1 = _whole(mo1_output, "MO1 qty")
    mo2 = _whole(existing_mo2_output, "Existing MO2 qty")
    maximum = _whole(published_max, "Published Max")
    batch = _whole(kitchen_bom_output, "BoM output", positive=True)
    if not isinstance(so_cutoff_closed, bool) or not isinstance(
            packing_physical_started, bool):
        raise Mo2PriorityError("Cutoff and Packing lock status must be explicit")
    if maximum % batch or mo1 % batch or mo2 % batch:
        raise Mo2PriorityError("Max/MO1/MO2 must be whole BoM batch outputs")
    if mo1 + mo2 > maximum:
        raise Mo2PriorityError("Existing MO1+MO2 exceeds Published Planning Max")
    target_so = _round_up(so, batch)
    if target_so > maximum:
        raise Mo2PriorityError("Confirmed SO demand exceeds Published Max")
    # MO2 should also preserve remaining RO demand whenever free kitchen
    # capacity exists, not intentionally abandon shops after confirming SO.
    # When gross demand exceeds Max, SO takes first priority and Packing
    # later distributes actual output to RO Paket then ordinary RO.
    gross = so + ro_pkg + ro_direct
    target_output = min(maximum, _round_up(gross, batch))
    additional = max(0, target_output - mo1 - mo2)
    if mo1 + mo2 + additional > maximum:
        raise Mo2PriorityError("MO2 would exceed Published Max")
    if additional and mo2:
        raise Mo2PriorityError(
            "One MO2 per SKU/slot already exists; no silent second MO2")
    if additional and packing_physical_started:
        raise Mo2PriorityError(
            "Packing physical transfer/DO has started; no late MO2")
    return {
        "confirmed_so_qty": so,
        "mo1_output": mo1,
        "existing_mo2_output": mo2,
        "published_max": maximum,
        "bom_output": batch,
        "rounded_so_protection": target_so,
        "ro_package_kitchen_qty": ro_pkg,
        "ro_direct_kitchen_qty": ro_direct,
        "gross_demand_before_roundup": gross,
        "total_output_target_with_ro": target_output,
        "mo2_incremental_qty": additional,
        "release_ready": so_cutoff_closed and not packing_physical_started,
        "release_allowed_now": bool(
            additional and so_cutoff_closed and not packing_physical_started
        ),
        "uncommitted_capacity_after_mos": maximum - mo1 - mo2 - additional,
    }


def preview_packing_buckets(actual_finished_available, so_direct_finished,
                            so_package_components, ro_package_components,
                            ro_direct_finished):
    """Aggregate *preview* of actual PCK SKU stock, never recipient dispatch.

    SO includes components of confirmed customer Paket (not assembled final
    Paket SKU). RO Paket protected next; ordinary RO third. Shortages stay
    explicit. No synthetic stock, no frozen RO snapshot overwrite.
    """
    stock = _whole(actual_finished_available, "available finished stock")
    so_direct = _whole(so_direct_finished, "direct SO")
    so_pkg = _whole(so_package_components, "SO Paket component")
    ro_pkg = _whole(ro_package_components, "RO Paket component")
    ro = _whole(ro_direct_finished, "ordinary RO")
    so_required = so_direct + so_pkg
    so_fulfilled = min(stock, so_required)
    stock -= so_fulfilled
    pkg_fulfilled = min(stock, ro_pkg)
    stock -= pkg_fulfilled
    ro_fulfilled = min(stock, ro)
    stock -= ro_fulfilled
    return {
        "so_required": so_required,
        "so_fulfilled": so_fulfilled,
        "so_shortage": so_required - so_fulfilled,
        "ro_package_required": ro_pkg,
        "ro_package_fulfilled": pkg_fulfilled,
        "ro_package_shortage": ro_pkg - pkg_fulfilled,
        "ro_direct_required": ro,
        "ro_direct_fulfilled": ro_fulfilled,
        "ro_direct_shortage": ro - ro_fulfilled,
        "unallocated_finished": stock,
        "requires_exception_review": (
            so_required > so_fulfilled or ro_pkg > pkg_fulfilled
        ),
    }
