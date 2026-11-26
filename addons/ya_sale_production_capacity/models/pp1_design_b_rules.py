"""Design B: pure PP1 and pre-release cumulative SO projection.

One kitchen SKU/date/slot in whole product base UoM. Caller must validate
source identities, routing, BoM, ledger, cutoff and date-slot mutex.
RO inputs are original confirmed demands, not frozen allocations.
SO inputs include direct and expanded Paket kitchen components exactly once.
No Odoo imports, stock, native allocation, MO creation or database writes.
"""


class PP1DesignError(ValueError):
    pass


def _whole(value, label, positive=False):
    if type(value) is not int or value < 0 or (positive and value == 0):
        raise PP1DesignError("%s must be a valid whole base-UoM quantity" % label)
    return value


def plan_pp1(*, confirmed_so_qty, original_ro_package_qty,
             original_ro_store_qty, bom_output, published_max):
    """Forecast MO1 from known RO + SO, with aggregate SO-first protection."""
    so = _whole(confirmed_so_qty, "SO")
    pkg = _whole(original_ro_package_qty, "RO Paket")
    store = _whole(original_ro_store_qty, "RO ordinary")
    bom = _whole(bom_output, "BoM", positive=True)
    maximum = _whole(published_max, "Published Max")
    if maximum % bom:
        raise PP1DesignError("Published Max must be a complete BoM multiple")
    if so > maximum:
        raise PP1DesignError("SO exceeds Published Max")
    gross = so + pkg + store
    rounded = ((gross + bom - 1) // bom) * bom
    mo1 = min(rounded, maximum)
    remaining = mo1 - so
    pkg_covered = min(pkg, remaining)
    remaining -= pkg_covered
    store_covered = min(store, remaining)
    remaining -= store_covered
    assert mo1 % bom == 0 and mo1 <= maximum
    assert so + pkg_covered + store_covered + remaining == mo1
    return {
        "confirmed_so_qty": so,
        "original_ro_package_qty": pkg,
        "original_ro_store_qty": store,
        "gross_known_demand": gross,
        "unrestricted_rounded_qty": rounded,
        "forecast_mo1_qty": mo1,
        "forecast_so_covered": so,
        "forecast_ro_package_covered": pkg_covered,
        "forecast_ro_package_shortage": pkg - pkg_covered,
        "forecast_ro_store_covered": store_covered,
        "forecast_ro_store_shortage": store - store_covered,
        "forecast_unallocated_surplus": remaining,
        "forecast_not_physical_stock": True,
        "recipient_and_complete_paket_allocation_pending": True,
    }


def preview_before_pp1_release(*, draft_so_qty, confirmed_so_qty,
                               original_ro_package_qty, original_ro_store_qty,
                               bom_output, published_max, ro_closed):
    """Sales Admin marginal scenario before Produksi OK PP1.

    ro_closed must come from a verified cutoff state, not absence of RO rows.
    A draft is never treated as a real confirmed order or native MO.
    RO shortage may INCREASE or DECREASE when a new SO triggers a whole batch.
    """
    draft = _whole(draft_so_qty, "Draft SO", positive=True)
    prior = _whole(confirmed_so_qty, "Confirmed SO")
    if type(ro_closed) is not bool:
        raise PP1DesignError("Explicit RO cutoff state required")
    common = dict(original_ro_package_qty=original_ro_package_qty,
                  original_ro_store_qty=original_ro_store_qty,
                  bom_output=bom_output, published_max=published_max)
    before = plan_pp1(confirmed_so_qty=prior, **common)
    after = plan_pp1(confirmed_so_qty=prior+draft, **common)
    delta = after["forecast_mo1_qty"] - before["forecast_mo1_qty"]
    surplus_delta = (after["forecast_unallocated_surplus"]
                     - before["forecast_unallocated_surplus"])
    pkg_delta = (after["forecast_ro_package_shortage"]
                 - before["forecast_ro_package_shortage"])
    store_delta = (after["forecast_ro_store_shortage"]
                   - before["forecast_ro_store_shortage"])
    assert delta >= 0
    assert surplus_delta == delta - draft + pkg_delta + store_delta
    return {
        "before": before, "after": after,
        "draft_so_qty": draft,
        "confirmed_so_qty_before": prior,
        "hypothetical_so_qty_after": prior+draft,
        "marginal_mo1_qty": delta,
        "marginal_surplus_change": surplus_delta,
        "new_surplus": max(0, surplus_delta),
        "absorbed_surplus": max(0, -surplus_delta),
        "ro_package_shortage_change": pkg_delta,
        "ro_store_shortage_change": store_delta,
        "ro_closed": ro_closed,
        "ro_demand_incomplete_warning": not ro_closed,
        "confirm_requires_locked_revalidation": True,
        "preview_only": True,
    }
