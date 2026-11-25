"""Pure Stage 2 capacity rules for YA Sales confirmations.

SOURCE-ONLY: no ORM, no SQL, no reservation, no confirmation.
All manufactured quantities MUST already be in product BASE UoM.
This helper deliberately does not allocate to stores or change RO/MO.
"""


class CapacityDecisionError(ValueError):
    pass


def _whole(value, label, positive=False):
    if isinstance(value, bool) or not isinstance(value, int):
        raise CapacityDecisionError("%s must be a whole base-UoM quantity" % label)
    if value < 0 or (positive and not value):
        raise CapacityDecisionError("%s must be %s" % (
            label, "positive" if positive else "nonnegative"))
    return value


def round_up_batch(quantity, bom_output):
    qty = _whole(quantity, "quantity")
    batch = _whole(bom_output, "BoM output", positive=True)
    return ((qty + batch - 1) // batch) * batch


def check_so_capacity(new_so_qty, existing_so_qty, published_max,
                      bom_output, mo1_output=0, mo2_output=0,
                      slot_open=True):
    """One kitchen SKU for one (delivery date, slot); atomic lock is CALLER's duty.

    RO demand is intentionally NOT a protected reservation. Existing MO1,
    even if triggered by RO, may satisfy confirmed SO; never count it as
    additional SO demand. MO2 is an incremental output requirement, not a
    new order for the entire Sales Qty. No MO creation or SO side effects.
    """
    new = _whole(new_so_qty, "new SO Qty", positive=True)
    existing = _whole(existing_so_qty, "already-confirmed SO Qty")
    maximum = _whole(published_max, "Published Planning Max")
    batch = _whole(bom_output, "BoM output", positive=True)
    mo1 = _whole(mo1_output, "MO1 output")
    mo2 = _whole(mo2_output, "MO2 output")
    if not isinstance(slot_open, bool):
        raise CapacityDecisionError("Slot Open/Locked status must be explicit")
    if not slot_open:
        raise CapacityDecisionError("Production/Delivery schedule is Locked")
    if maximum % batch:
        raise CapacityDecisionError("Published Planning Max is not a BoM batch multiple")
    if mo1 % batch or mo2 % batch:
        raise CapacityDecisionError("MO1/MO2 output is not a BoM batch multiple")
    if mo1 + mo2 > maximum:
        raise CapacityDecisionError("Existing MO1+MO2 exceeds Published Planning Max")
    total_so = existing + new
    planned_floor = round_up_batch(total_so, batch)
    if planned_floor > maximum:
        raise CapacityDecisionError(
            "Confirmed SO demand after batch rounding exceeds Published Planning Max")
    currently_planned = mo1 + mo2
    incremental = max(0, planned_floor - currently_planned)
    assert incremental % batch == 0
    assert currently_planned + incremental <= maximum
    return {
        "new_so_qty": new,
        "existing_confirmed_so_qty": existing,
        "confirmed_so_qty_after": total_so,
        "mo1_output": mo1,
        "mo2_output": mo2,
        "published_max": maximum,
        "bom_output": batch,
        "so_required_batch_output": planned_floor,
        "incremental_mo2_output_needed": incremental,
        "remaining_so_qty_capacity": maximum - total_so,
    }


def expand_so_package_requirements(direct_kitchen, package_qty,
                                   bom_components, component_source):
    """Separate kitchen components of Paket from PCK-procured components.

    direct_kitchen: product_id -> integer finished qty in base UoM.
    package_qty: final Paket product_id -> integer qty (one output/Paket).
    bom_components: Paket ID -> {component ID: integer kitchen/float PCK qty}.
    component_source: component ID -> 'KITCHEN' or 'PCK'.
    Nested Paket/ambiguous routes MUST be rejected by ORM adapter.
    """
    kitchen = {}
    pck = {}
    for key, qty in direct_kitchen.items():
        _whole(key, "direct product ID", positive=True)
        kitchen[key] = _whole(qty, "direct kitchen demand")
    for package, qty in package_qty.items():
        _whole(package, "Paket product ID", positive=True)
        count = _whole(qty, "Paket Qty")
        if not count:
            continue
        components = bom_components.get(package)
        if not components:
            raise CapacityDecisionError("Paket %s has no validated assembly BoM" % package)
        for sku, ratio in components.items():
            _whole(sku, "component product ID", positive=True)
            kind = component_source.get(sku)
            if kind == "KITCHEN":
                n = _whole(ratio, "kitchen component ratio", positive=True)
                kitchen[sku] = kitchen.get(sku, 0) + count * n
            elif kind == "PCK":
                if (isinstance(ratio, bool) or not isinstance(ratio, (int, float))
                        or ratio <= 0):
                    raise CapacityDecisionError("PCK component ratio must be positive")
                pck[sku] = pck.get(sku, 0) + count * ratio
            else:
                raise CapacityDecisionError(
                    "Unknown/unrouted Paket component %s; do not assume a kitchen" % sku)
    return {"kitchen_requirements": kitchen,
            "pck_stock_requirements": pck}
