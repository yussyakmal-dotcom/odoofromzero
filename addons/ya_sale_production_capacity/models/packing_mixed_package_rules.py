"""Pure SKU-conserving Packing priority ledger for mixed SO/RO Paket.

SOURCE/PURE ONLY. No Odoo env, ORM, reservations, MOs, stock moves or DO.
This is a strict whole-base-UoM first gate. Production UoM and fractional
PCK-only BoM components must be normalized by a later schema-checked ORM
adapter; never round fractional quantities silently.

Actual physical minus existing native reservations is the only available
stock. Confirmed SO direct + Paket BOM comes first. RO Paket requires ALL
components in sufficient quantities for its full requested count; if not,
raise an exception rather than allocate half a package. Ordinary RO is
last and may be partially served. Distribution among STORES is a separate
approved/prorata rule, never decided by this function.
"""
from collections import defaultdict


class MixedPackingError(ValueError):
    pass


def _whole(value, label, positive=False):
    if isinstance(value, bool) or not isinstance(value, int):
        raise MixedPackingError("%s must be a whole quantity in base UoM" % label)
    if value < 0 or (positive and value == 0):
        raise MixedPackingError("%s must be %s" % (
            label, "positive" if positive else "nonnegative"
        ))
    return value


def _positive_qty_map(values, label):
    if not isinstance(values, dict):
        raise MixedPackingError("%s must be a dictionary" % label)
    output = {}
    for raw_pid, raw_qty in values.items():
        pid = _whole(raw_pid, "%s product ID" % label, positive=True)
        qty = _whole(raw_qty, "%s SKU %s" % (label, pid))
        if qty:
            output[pid] = qty
    return output


def _sum_demands(base, extra):
    sums = defaultdict(int)
    for rows in (base, extra):
        for sku, qty in rows.items():
            sums[sku] += qty
    return dict(sums)


def _parts_from_packages(packages, package_boms, label):
    component_demands = defaultdict(int)
    by_package = {}
    for package, count in sorted(packages.items()):
        spec = package_boms.get(package)
        if not isinstance(spec, dict) or not spec:
            raise MixedPackingError(
                "%s Paket %s has no validated PCK assembly BoM" % (
                    label, package
                )
            )
        seen = False
        per_package = {}
        for bucket in ("kitchen", "pck"):
            component_rows = spec.get(bucket, {})
            if not isinstance(component_rows, dict):
                raise MixedPackingError("Paket %s bucket %s invalid" % (
                    package, bucket
                ))
            for raw_sku, raw_ratio in component_rows.items():
                sku = _whole(raw_sku, "Paket component SKU", positive=True)
                ratio = _whole(
                    raw_ratio, "Paket component base-UoM Qty", positive=True
                )
                if sku in per_package:
                    raise MixedPackingError(
                        "Paket %s component %s appears in two source buckets" %
                        (package, sku)
                    )
                per_package[sku] = (bucket, count * ratio)
                component_demands[sku] += count * ratio
                seen = True
        if not seen:
            raise MixedPackingError("Paket %s has no real components" % package)
        by_package[package] = dict(sorted(per_package.items()))
    return dict(component_demands), by_package


def plan_mixed_so_ro_package_packing(
    *, physical_reserved_by_sku, so_direct, so_package_qty,
    ro_package_qty, ro_direct, package_boms,
):
    """Full-component all-or-nothing SO and RO Paket safety preview.

    physical_reserved_by_sku: {SKU: {physical:int, reserved:int}}, all
    SKU amounts in BASE UoM including components supplied directly at PCK.
    Missing stock entries count as zero; existing reservations NEVER available.
    so_direct/ro_direct: finished kitchen SKU -> required Qty.
    so_package_qty/ro_package_qty: final Paket SKU -> package count.
    package_boms: {Paket SKU: {"kitchen":{SKU:qty/unit},
                                "pck":{SKU:qty/unit}}}

    SO direct and SO Paket share the same protected tier. If insufficient to
    meet both COMPLETELY, STOP for owner exception; do NOT invent tie-break.
    RO Paket is the next indivisible tier; if full requested quantity cannot
    be fulfilled, STOP for explicit shortage decision. RO ordinary is last;
    aggregate partial service is a preview, NOT per-store DO allocations.
    """
    so_d = _positive_qty_map(so_direct, "SO direct")
    so_p = _positive_qty_map(so_package_qty, "SO Paket")
    ro_p = _positive_qty_map(ro_package_qty, "RO Paket")
    ro_d = _positive_qty_map(ro_direct, "RO ordinary")
    if not isinstance(package_boms, dict):
        raise MixedPackingError("Package BoMs must be a mapping")
    for pkg in set(so_p) | set(ro_p):
        _whole(pkg, "Paket SKU", positive=True)

    so_components, so_package_trace = _parts_from_packages(
        so_p, package_boms, "SO"
    )
    ro_components, ro_package_trace = _parts_from_packages(
        ro_p, package_boms, "RO"
    )
    so_total = _sum_demands(so_d, so_components)

    if not isinstance(physical_reserved_by_sku, dict):
        raise MixedPackingError("Native stock snapshot must be a dictionary")
    free = {}
    for pid, details in physical_reserved_by_sku.items():
        product = _whole(pid, "Stock product ID", positive=True)
        if not isinstance(details, dict):
            raise MixedPackingError("Native physical/reserved stock missing")
        physical = _whole(details.get("physical"), "physical")
        reserved = _whole(details.get("reserved"), "native reserved")
        if reserved > physical:
            raise MixedPackingError(
                "SKU %s has reserved stock larger than physical" % product
            )
        free[product] = physical - reserved

    needed_skus = set(so_total) | set(ro_components) | set(ro_d)
    remaining = {sku: free.get(sku, 0) for sku in needed_skus}
    so_missing = {
        sku: demand - remaining[sku]
        for sku, demand in so_total.items() if remaining[sku] < demand
    }
    if so_missing:
        raise MixedPackingError(
            "SO_UNFULFILLED_STOCK: %s; no partial SO Paket or SO tie-break" %
            sorted(so_missing.items())
        )
    for sku, demand in so_total.items():
        remaining[sku] -= demand

    ro_package_missing = {
        sku: demand - remaining[sku]
        for sku, demand in ro_components.items() if remaining[sku] < demand
    }
    if ro_package_missing:
        raise MixedPackingError(
            "RO_PAKET_COMPONENT_SHORTAGE: %s; do not assemble partial Paket" %
            sorted(ro_package_missing.items())
        )
    for sku, demand in ro_components.items():
        remaining[sku] -= demand

    ordinary_allocated = {
        sku: min(demand, remaining.get(sku, 0))
        for sku, demand in ro_d.items()
    }
    for sku, granted in ordinary_allocated.items():
        remaining[sku] -= granted
    ordinary_shortage = {
        sku: demand - ordinary_allocated[sku]
        for sku, demand in ro_d.items() if demand > ordinary_allocated[sku]
    }

    for sku in needed_skus:
        assert (
            so_total.get(sku, 0) + ro_components.get(sku, 0)
            + ordinary_allocated.get(sku, 0) + remaining[sku]
            == free.get(sku, 0)
        ), "Stock conservation failure %s" % sku
        assert remaining[sku] >= 0
    return {
        "so_direct": dict(sorted(so_d.items())),
        "so_package_qty": dict(sorted(so_p.items())),
        "so_package_components": dict(sorted(so_components.items())),
        "so_package_trace": so_package_trace,
        "so_protected_total": dict(sorted(so_total.items())),
        "ro_package_qty": dict(sorted(ro_p.items())),
        "ro_package_components": dict(sorted(ro_components.items())),
        "ro_package_trace": ro_package_trace,
        "ordinary_ro_required": dict(sorted(ro_d.items())),
        "ordinary_ro_allocated": dict(sorted(ordinary_allocated.items())),
        "ordinary_ro_shortage": dict(sorted(ordinary_shortage.items())),
        "unallocated_after_priority": dict(sorted(remaining.items())),
        "free_stock_before": {
            sku: free.get(sku, 0) for sku in sorted(needed_skus)
        },
        "needs_ordinary_ro_shortage_review": bool(ordinary_shortage),
        "ready_for_native_pck_assembly": True,
        "only_pure_preview_no_ledger_stock_or_do": True,
    }
