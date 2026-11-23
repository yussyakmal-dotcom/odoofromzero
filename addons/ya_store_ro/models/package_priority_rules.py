"""Pure package-first demand arithmetic (no ORM / no stock mutations).

A package is ordered as a final SKU but never treated as an ordinary kitchen
product. Only explicitly classified FINISHED_KITCHEN BoM components add demand
to kitchen production. Purchased consignment and packaging components stay
in a separate PCK stock-requirement bucket. Actual assembly/RO allocation
is a later Odoo integration step; this module does NOT reserve stock.

Input line qty is *already converted to the component base UoM*. Strict
integers prevent accidental fractional manufacturing orders.
"""
from collections import defaultdict


class PackageDemandError(ValueError):
    """Reject ambiguous, fractional or incomplete package demand."""


def _qty(value, label, *, allow_zero=True):
    if isinstance(value, bool) or not isinstance(value, int):
        raise PackageDemandError("%s must be an integer in base UoM" % label)
    if value < 0 or (not allow_zero and value == 0):
        raise PackageDemandError("%s must be positive%s" % (
            label, " or zero" if allow_zero else ""))
    return value


def compute_package_first_demand(direct_by_sku, packages_by_sku,
                                 bom_by_package, source_kind_by_sku):
    """Return independently traceable production and Packing-demand buckets.

    direct_by_sku: {component_sku_id: direct RO demand}, integer quantities.
    packages_by_sku: {package_sku_id: RO demand}, integer quantities.
    bom_by_package: {package_sku_id: {component_sku_id: integer qty/unit}}.
    source_kind_by_sku maps every used component to exactly one of:
      FINISHED_KITCHEN, CONSIGNMENT, PACKAGING.
    This function intentionally refuses nested packages, missing BoMs, unknown
    source kinds and noninteger BoM ratios. Source/multi-level UOM conversion,
    routing and package tie-break rules are outside this pure function.
    """
    valid = {"FINISHED_KITCHEN", "CONSIGNMENT", "PACKAGING"}
    direct = {p: _qty(q, "direct_qty[%s]" % p)
              for p, q in direct_by_sku.items()}
    packages = {p: _qty(q, "package_qty[%s]" % p)
                for p, q in packages_by_sku.items()}
    kitchen_package = defaultdict(int)
    packing_non_kitchen = defaultdict(int)
    by_package = {}
    for package, qty in sorted(packages.items(), key=lambda pair: str(pair[0])):
        if not qty:
            continue
        if package not in bom_by_package or not bom_by_package[package]:
            raise PackageDemandError("Package %s has no unambiguous BoM" % package)
        component_detail = {}
        for component, ratio in sorted(bom_by_package[package].items(),
                                       key=lambda pair: str(pair[0])):
            n = _qty(ratio, "BoM[%s][%s]" % (package, component),
                     allow_zero=False)
            kind = source_kind_by_sku.get(component)
            if kind not in valid:
                raise PackageDemandError(
                    "Component %s: unknown or nested source kind %s" %
                    (component, kind))
            required = qty * n
            component_detail[component] = required
            if kind == "FINISHED_KITCHEN":
                kitchen_package[component] += required
            else:
                packing_non_kitchen[component] += required
        by_package[package] = component_detail
    gross_kitchen = dict(direct)
    # direct_by_sku is expected to include only kitchen products; the caller
    # must validate this before invoking pure computation.
    for component, qty in kitchen_package.items():
        gross_kitchen[component] = gross_kitchen.get(component, 0) + qty
    return {
        "direct_store_finished": direct,
        "package_store_finished": packages,
        "package_kitchen_protected": dict(kitchen_package),
        "package_packing_stock_requirements": dict(packing_non_kitchen),
        "gross_kitchen_demand": gross_kitchen,
        "package_component_breakdown": by_package,
    }


def allocate_kitchen_capacity_package_first(package_need, direct_by_store,
                                            available):
    """Protect package bucket before allocating remaining supply to stores.

    Pure *one-component* preview. The function intentionally refuses to
    silently prorate competing stores; caller must apply existing Hamilton
    prorata to the remaining supply using confirmed RO store demand. It does
    NOT imply a complete package can be assembled from one component alone.
    """
    protected = _qty(package_need, "package_need")
    available = _qty(available, "available")
    for store_id, qty in direct_by_store.items():
        _qty(qty, "store_qty[%s]" % store_id)
    reserved = min(protected, available)
    remaining = available - reserved
    direct_requested = sum(direct_by_store.values())
    return {
        "protected_required": protected,
        "protected_from_supply": reserved,
        "protected_shortage": protected - reserved,
        "available_after_package": remaining,
        "direct_requested": direct_requested,
        "direct_possible": min(remaining, direct_requested),
        "direct_shortage": max(0, direct_requested - remaining),
    }
