"""Pure package-first demand arithmetic (no ORM / no stock mutations).

A package is ordered as a final SKU but never treated as an ordinary kitchen
product. Only explicitly routed MANUFACTURED_KITCHEN BoM components add demand
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
      MANUFACTURED_KITCHEN, PCK_STOCK_STANDARD_FLOW.
    Historical FINISHED_KITCHEN / CONSIGNMENT / PACKAGING aliases are accepted
    for compatibility with earlier source-only tests; no category inference.
    This function intentionally refuses nested packages, missing BoMs, unknown
    source kinds and noninteger BoM ratios. Source/multi-level UOM conversion,
    routing and package tie-break rules are outside this pure function.
    """
    kitchen_kinds = {"MANUFACTURED_KITCHEN", "FINISHED_KITCHEN"}
    standard_pck_kinds = {"PCK_STOCK_STANDARD_FLOW", "CONSIGNMENT", "PACKAGING"}
    valid = kitchen_kinds | standard_pck_kinds
    direct = {p: _qty(q, "direct_qty[%s]" % p)
              for p, q in direct_by_sku.items()}
    for p in direct:
        if source_kind_by_sku.get(p) not in kitchen_kinds:
            raise PackageDemandError(
                "Direct product %s must be routed MANUFACTURED_KITCHEN" % p)
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
            if kind in kitchen_kinds:
                kitchen_package[component] += required
            else:
                packing_non_kitchen[component] += required
        by_package[package] = component_detail
    gross_kitchen = dict(direct)
    # Direct RO SKUs are explicitly routed to kitchens, not inferred by category.
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


def plan_kitchen_capacity_with_package_priority(
        package_need, direct_by_store, bom_output, max_capacity):
    """Plan kitchen MO, giving Paket first priority and prorating ALL surplus.

    1. Gross demand = component qty protected for Paket + direct store RO.
    2. Round gross demand UP to whole kitchen BoM batch outputs.
    3. Respect Published Planning Max (whole BoM batches).
    4. Reserve full Paket requirement first, then direct RO demand to stores.
    5. If all direct RO is met, prorate remaining batch-rounding surplus to
       stores proportional to their ORIGINAL requested quantities, with
       largest-remainder/Hamilton tie-break by ascending store ID.

    One Paket assembly BoM still outputs exactly ONE final Paket; the
    bom_output here describes the KITCHEN component's manufacturing BoM.
    If Planning Max cannot cover the Paket bucket, fail closed, with no MO
    released. This is a pure calculation: no stock, MO, or document writes.

    Store identity: allocated = requested - shortage + surplus.
    Global quantity conservation:
       produced = protected_for_paket + sum(store allocated) + unallocated.
    Do not assign surplus to a store that did not order that SKU.
    """
    protected = _qty(package_need, "package_need")
    batch = _qty(bom_output, "bom_output", allow_zero=False)
    maximum = _qty(max_capacity, "max_capacity")
    stores = {}
    for store, requested in direct_by_store.items():
        if isinstance(store, bool) or not isinstance(store, int) or store <= 0:
            raise PackageDemandError("Store ID must be a positive integer")
        stores[store] = _qty(requested, "direct_store[%s]" % store)
    requested_direct = sum(stores.values())
    requested_total = protected + requested_direct

    if requested_total == 0:
        return {
            "status": "no_demand",
            "qty_production": 0,
            "package_component_qty_protected": 0,
            "package_component_shortage": 0,
            "direct_qty_requested": 0,
            "direct_qty_allocated": 0,
            "direct_qty_shortage": 0,
            "qty_surplus_distributed": 0,
            "qty_surplus": 0,  # unallocated surplus
            "store_allocations": {
                store: {"requested": quantity, "allocated": 0,
                        "shortage": 0, "surplus": 0}
                for store, quantity in stores.items()
            },
        }

    rounded_production = ((requested_total + batch - 1) // batch) * batch
    producible = min(rounded_production, (maximum // batch) * batch)
    if producible < protected or producible == 0:
        return {
            "status": "blocked_package_capacity" if producible < protected else "blocked",
            "qty_production": 0,
            "capacity_if_unblocked": producible,
            "package_component_qty_protected": 0,
            "package_component_shortage": protected,
            "direct_qty_requested": requested_direct,
            "direct_qty_allocated": 0,
            "direct_qty_shortage": requested_direct,
            "qty_surplus_distributed": 0,
            "qty_surplus": 0,
            "store_allocations": {
                store: {"requested": quantity, "allocated": 0,
                        "shortage": quantity, "surplus": 0}
                for store, quantity in stores.items()
            },
        }

    direct_budget = min(requested_direct, producible - protected)
    allocations = {}
    distributed = 0
    remainders = []
    for store, requested in stores.items():
        base, remainder = divmod(requested * direct_budget, requested_direct) if requested_direct else (0, 0)
        allocations[store] = {
            "requested": requested,
            "allocated": base,
            "shortage": requested - base,
            "surplus": 0,
        }
        distributed += base
        remainders.append((remainder, store))
    remainders.sort(key=lambda pair: (-pair[0], pair[1]))
    for _, store in remainders[:direct_budget - distributed]:
        allocations[store]["allocated"] += 1
        allocations[store]["shortage"] -= 1

    # Only after direct requests are covered: share the BoM rounding surplus.
    extra = producible - protected - direct_budget
    extra_allocated = 0
    if extra > 0 and requested_direct > 0 and direct_budget == requested_direct:
        extras = []
        initial = 0
        for store, requested in stores.items():
            per_store, remainder = divmod(requested * extra, requested_direct)
            allocations[store]["surplus"] += per_store
            allocations[store]["allocated"] += per_store
            initial += per_store
            extras.append((remainder, store))
        extras.sort(key=lambda pair: (-pair[0], pair[1]))
        for _, store in extras[:extra - initial]:
            allocations[store]["surplus"] += 1
            allocations[store]["allocated"] += 1
        extra_allocated = extra

    unallocated = extra - extra_allocated
    assert all(
        row["allocated"] == row["requested"] - row["shortage"] + row["surplus"]
        for row in allocations.values()
    )
    assert sum(row["surplus"] for row in allocations.values()) == extra_allocated
    assert sum(row["allocated"] for row in allocations.values()) + protected + unallocated == producible
    return {
        "status": "prorated_direct_only" if direct_budget < requested_direct else "ok",
        "qty_production": producible,
        "package_component_qty_protected": protected,
        "package_component_shortage": 0,
        "direct_qty_requested": requested_direct,
        "direct_qty_allocated": sum(row["allocated"] for row in allocations.values()),
        "direct_qty_shortage": requested_direct - direct_budget,
        "qty_surplus_distributed": extra_allocated,
        "qty_surplus": unallocated,
        "store_allocations": allocations,
    }
