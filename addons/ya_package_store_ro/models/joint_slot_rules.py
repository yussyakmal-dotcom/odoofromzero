"""Pure, no-ORM joint RO consolidation for one Packing date/slot.

This bridges the two real request types:
  - ordinary ya.store.ro, with actual kitchen Published Planning;
  - cross-kitchen ya.package.store.ro, with exactly-one-output assembly BoM.

A completed output is a proposal only: kitchen MO, Paket assembly MO and
store DO are NOT created here. The system keeps Paket requirements, ordinary
store allocations and Packing->store internal-transfer fallback separate.

Call with planner=plan_kitchen_capacity_with_package_priority from ya_store_ro.
"""
from collections import defaultdict


class JointSlotError(ValueError):
    pass


def _whole(value, label, positive=False):
    if isinstance(value, bool) or not isinstance(value, int):
        raise JointSlotError("%s must be an integer" % label)
    if value < 0 or (positive and not value):
        raise JointSlotError("%s must be %s" %
                             (label, "positive" if positive else "nonnegative"))
    return value


def _key(value, label):
    return _whole(value, label, positive=True)


def plan_joint_slot(direct_rows, package_rows, kitchen_specs, planner):
    """Consolidate confirmed ordinary and Paket RO without changing either.

    direct_rows: [{product_id,store_id,qty,ro_id(optional)}].
    package_rows: [{product_id (Paket),store_id,qty,ro_id(optional),
      components:[{product_id, qty_per_package, source_kind:'KITCHEN'|'PCK'}]}]
    kitchen_specs: {component/product_id: {planning_id,kitchen_code,
      bom_id,bom_output,max_capacity}}. Specs must come from the SAME published
      delivery date and slot and be uniquely routed. Do not invent routes.
    planner: pure kitchen capacity calculator (no ORM).
    PCK component quantity may be fractional in its base UoM. Kitchen
      finished component quantity MUST be integer in its base UoM.
    """
    direct = defaultdict(lambda: defaultdict(int))
    protected = defaultdict(int)
    pending_pck = defaultdict(float)
    packages = defaultdict(int)
    component_trace = defaultdict(lambda: defaultdict(int))
    packing_trace = defaultdict(lambda: defaultdict(float))
    package_sources = defaultdict(set)
    direct_provenance = []
    package_provenance = []
    warnings = []

    for row in direct_rows:
        product = _key(row["product_id"], "direct product")
        store = _key(row["store_id"], "direct store")
        qty = _whole(row["qty"], "direct quantity")
        if product not in kitchen_specs:
            raise JointSlotError("Direct SKU %s lacks unique published kitchen route" % product)
        if qty:
            direct[product][store] += qty
            direct_provenance.append({
                "ro_id": row.get("ro_id"),
                "product_id": product,
                "store_id": store,
                "qty": qty,
            })

    for row in package_rows:
        package = _key(row["product_id"], "package product")
        store = _key(row["store_id"], "package store")
        qty = _whole(row["qty"], "package quantity")
        if not qty:
            continue
        components = row.get("components") or []
        if not components:
            raise JointSlotError("Paket %s requires a valid assembly BoM" % package)
        packages[(store, package)] += qty
        package_sources[package].add(row.get("ro_id") or 0)
        package_provenance.append({
            "ro_id": row.get("ro_id"),
            "bom_id": row.get("bom_id"),
            "product_id": package,
            "store_id": store,
            "qty": qty,
        })
        routed_kitchens = set()
        seen = set()
        for item in components:
            component = _key(item["product_id"], "Paket component")
            source = item["source_kind"]
            if component in seen:
                # Duplicate component BoM lines must be aggregated by the
                # ORM adapter first: avoid double counting or hidden UoM mix.
                raise JointSlotError(
                    "Duplicate unmerged component %s in Paket %s" %
                    (component, package))
            seen.add(component)
            per_package = item["qty_per_package"]
            if isinstance(per_package, bool) or not isinstance(
                    per_package, (int, float)) or per_package <= 0:
                raise JointSlotError("Invalid component ratio for %s" % component)
            needed = qty * per_package
            if source == "KITCHEN":
                if int(needed) != needed or int(per_package) != per_package:
                    raise JointSlotError(
                        "Fractional kitchen finished component %s in Paket %s" %
                        (component, package))
                if component not in kitchen_specs:
                    raise JointSlotError(
                        "Paket component %s lacks unique published kitchen route" %
                        component)
                needed = int(needed)
                protected[component] += needed
                component_trace[package][component] += needed
                routed_kitchens.add(kitchen_specs[component]["planning_id"])
            elif source == "PCK":
                pending_pck[component] += needed
                packing_trace[package][component] += needed
            else:
                raise JointSlotError("Unknown component source %s" % source)
        if len(routed_kitchens) < 2:
            warnings.append(
                "Paket %s uses fewer than 2 distinct planned kitchens; "
                "review category master (one-kitchen Paket belongs in ordinary RO)" %
                package)

    kitchen_results = []
    keys = sorted(set(direct) | set(protected))
    for product in keys:
        spec = kitchen_specs.get(product)
        if not spec:
            raise JointSlotError("Missing kitchen routing for %s" % product)
        planned = planner(
            protected[product], dict(direct[product]),
            spec["bom_output"], spec["max_capacity"],
        )
        qty = planned["qty_production"]
        allocated = sum(x["allocated"] for x in planned["store_allocations"].values())
        residual = planned["qty_surplus"]
        if planned["status"].startswith("blocked"):
            warnings.append(
                "Kitchen SKU %s: %s; review published capacity/BoM in SOP" %
                (product, planned["status"]))
        else:
            if qty != protected[product] + allocated + residual:
                raise JointSlotError("Unbalanced kitchen output %s" % product)
        kitchen_results.append({
            "product_id": product,
            "planning_id": spec["planning_id"],
            "kitchen_code": spec["kitchen_code"],
            "bom_id": spec["bom_id"],
            "bom_output": spec["bom_output"],
            "max_capacity": spec["max_capacity"],
            "package_component_qty": protected[product],
            "direct_store_requested": sum(direct[product].values()),
            "qty_production": qty,
            "store_allocations": planned["store_allocations"],
            "qty_pending_internal_transfer": residual,
            "status": planned["status"],
        })
    return {
        "package_store_delivery": [
            {"store_id": store, "product_id": package, "qty": qty}
            for (store, package), qty in sorted(packages.items())
        ],
        "ordinary_ro_source_lines": sorted(
            direct_provenance,
            key=lambda row: (row["product_id"], row["store_id"], row["ro_id"] or 0),
        ),
        "package_ro_source_lines": sorted(
            package_provenance,
            key=lambda row: (row["product_id"], row["store_id"], row["ro_id"] or 0),
        ),
        "package_component_trace": {
            package: dict(parts) for package, parts in sorted(component_trace.items())
        },
        "pck_component_trace": {
            package: dict(parts) for package, parts in sorted(packing_trace.items())
        },
        "package_ro_source_ids": {
            package: sorted(source_ids)
            for package, source_ids in sorted(package_sources.items())
        },
        "pck_stock_requirements": dict(sorted(pending_pck.items())),
        "kitchen_mo_plans": kitchen_results,
        "total_kitchen_mo_qty": sum(x["qty_production"] for x in kitchen_results),
        "total_pending_internal_transfer": sum(
            x["qty_pending_internal_transfer"] for x in kitchen_results),
        "warnings": warnings,
    }
