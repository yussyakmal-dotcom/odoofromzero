"""READ-ONLY ranked feasibility search for REAL two-wave cross-kitchen Paket.

Unlike the earlier broad candidate finder, this gate checks ALL Paket masters
(not first 150), real Published Max >= two actual kitchen BoM outputs for EACH
kitchen component, and CDC free raw stock for two minimal native MO batches.
No invented SKU, BoM, stock, or capacity. A reference Published Planning from
a past date is used ONLY as a pattern; any native test must create future
planning/fixture in one unconditional rollback and retain genuine limits.

If no fully eligible candidate exists, print closest failures and summary.
This audit is diagnostic, not a claim of full SO/Paket/MO2 end-to-end PASS.
"""
from collections import Counter, defaultdict
from datetime import date
from math import ceil

DB = "erp-yussyakmal-mrp-test-RO_SO"
assert env.cr.dbname == DB, "STOP_WRONG_DATABASE"
env.cr.rollback()
env.cr.execute("SET TRANSACTION READ ONLY")
env.cr.execute("SHOW transaction_read_only")
assert env.cr.fetchone()[0] == "on", "STOP_READ_ONLY_UNAVAILABLE"

Module = env["ir.module.module"].sudo().search([
    ("name", "=", "ya_sale_production_capacity")
], limit=1)
assert Module and Module.state == "installed" and (
    Module.installed_version == "19.0.1.1.3"
), "STOP_WRONG_INSTALLED_SALES_ADDON_VERSION"

company = env["res.company"].sudo().browse(1).exists()
assert company, "STOP_COMPANY1_NOT_FOUND"
WH = env["stock.warehouse"].sudo().with_company(company)
cdc = WH.search([("code", "=", "CDC"), ("company_id", "=", 1)])
pck = WH.search([("code", "=", "PCK"), ("company_id", "=", 1)])
assert len(cdc) == len(pck) == 1 and cdc.lot_stock_id and pck.lot_stock_id
PCKTypes = env["stock.picking.type"].sudo().search([
    ("code", "=", "mrp_operation"),
    ("warehouse_id", "=", pck.id),
    ("company_id", "=", 1),
])
pck_route_ready = len(PCKTypes) == 1
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_ALL_REAL_PAKET_TWO_WAVE_FEASIBILITY_RANKING")
print("YA_SALES_VERSION:", Module.installed_version)
print("PCK_ASSEMBLY_NATIVE_OPERATION_READY:", pck_route_ready)

Cat = env["product.category"].sudo().search([
    ("complete_name", "=", "All / Produk Jadi / Paket")
])
assert len(Cat) == 1, "STOP_PACKAGE_CATEGORY_MISSING_OR_AMBIGUOUS"
products = env["product.product"].sudo().with_company(company).search([
    ("categ_id", "=", Cat.id)
], order="id")
print("PAKET_PRODUCT_COUNT_SCANNED_ALL:", len(products))

plannings = env["ya.production.planning"].sudo().with_company(company).search(
    [("state", "=", "published")])
routes_by_slot = defaultdict(lambda: defaultdict(list))
for planning in plannings:
    for line in planning.line_ids:
        routes_by_slot[(planning.delivery_date, planning.slot)][
            line.product_id.id].append(line)
print("PUBLISHED_SLOT_TEMPLATES:", len(routes_by_slot),
      "PUBLISHED_KITCHEN_PLANNINGS:", len(plannings))

# Exact owner-less, package-less and untracked quant only.
cdcs = env["stock.quant"].sudo().search([
    ("company_id", "=", 1),
    ("location_id", "=", cdc.lot_stock_id.id),
    ("lot_id", "=", False), ("package_id", "=", False),
    ("owner_id", "=", False),
])
cdc_free = defaultdict(float)
for q in cdcs:
    cdc_free[q.product_id.id] += q.quantity - q.reserved_quantity

Boms = env["mrp.bom"].sudo().with_company(company)
bom_cache = {}
component_route_cache = {}
counters = Counter()
ranked = []
today = date.today()


def component_info(line):
    """Validate two BoM batches and CDC raw readiness for a kitchen SKU."""
    if line.id in component_route_cache:
        return component_route_cache[line.id]
    product = line.product_id
    result = {
        "id": product.id,
        "sku": product.default_code or str(product.id),
        "line_id": line.id,
        "output": None,
        "published_max": None,
        "warehouse": None,
        "ratio_in_paket": None,
        "two_wave_capacity": False,
        "cdc_two_batches_ready": False,
        "raw_needs_for_two_batches": {},
        "wo_free": False,
        "raw_shortage_skus": [],
        "issue": [],
    }
    try:
        bom = line._capacity_bom()
        pt = bom.picking_type_id
        wh = pt.warehouse_id if pt else False
        if not (bom.active and bom.type == "normal" and wh and
                pt.company_id == company and wh.company_id == company
                and pt.default_location_dest_id == wh.lot_stock_id):
            result["issue"].append("BOM_KITCHEN_ROUTE")
        else:
            expected = " ".join(("Dapur " +
                (line.planning_id.workcenter_id.name or "")).casefold().split())
            actual = " ".join((wh.name or "").casefold().split())
            if expected != actual:
                result["issue"].append("WORKCENTER_ROUTE")
        if wh:
            result["warehouse"] = wh.code
        output = bom.product_uom_id._compute_quantity(
            bom.product_qty, product.uom_id, round=False
        )
        maximum = line.uom_id._compute_quantity(
            line.max_capacity, product.uom_id, round=False
        )
        result["output"] = output
        result["published_max"] = maximum
        result["wo_free"] = ("operation_ids" in bom._fields and
                             not bom.operation_ids)
        if not result["wo_free"]:
            result["issue"].append("HAS_OR_UNKNOWN_WO")
        result["two_wave_capacity"] = bool(
            output > 0 and abs(output - round(output)) < 1e-7
            and maximum >= 2 * output
            and abs(maximum / output - round(maximum / output)) < 1e-7
            and product.tracking == "none"
        )
        if not result["two_wave_capacity"]:
            result["issue"].append("MAX_LESS_THAN_TWO_BOM_BATCHES")
        raw_by_sku = defaultdict(float)
        raw_ids = {}
        for line_bom in bom.bom_line_ids:
            raw = line_bom.product_id
            qty = line_bom.product_uom_id._compute_quantity(
                line_bom.product_qty, raw.uom_id, round=False
            )
            if qty <= 0 or raw.tracking != "none":
                result["issue"].append("INVALID_OR_TRACKED_RAW")
            raw_by_sku[raw.id] += qty * 2
            raw_ids[raw.id] = raw
        if not raw_by_sku:
            result["issue"].append("BOM_WITHOUT_RAW")
        result["raw_needs_for_two_batches"] = dict(raw_by_sku)
        for raw_id, needed in sorted(raw_by_sku.items()):
            if cdc_free[raw_id] + 1e-7 < needed:
                result["raw_shortage_skus"].append({
                    "id": raw_id,
                    "sku": raw_ids[raw_id].default_code,
                    "needed_min_two_batches": round(needed, 4),
                    "cdc_free": round(cdc_free[raw_id], 4),
                })
        result["cdc_two_batches_ready"] = bool(
            raw_by_sku and not result["raw_shortage_skus"] and
            "INVALID_OR_TRACKED_RAW" not in result["issue"]
        )
        if not result["cdc_two_batches_ready"]:
            result["issue"].append("CDC_RAW_SHORTAGE")
    except Exception as exc:
        result["issue"].append(
            "SCHEMA_OR_BOM_REQUIRES_REVIEW:%s" % type(exc).__name__
        )
    component_route_cache[line.id] = result
    return result


for product in products:
    pkboms = Boms.search([
        ("active", "=", True), ("type", "=", "normal"),
        ("product_tmpl_id", "=", product.product_tmpl_id.id),
        "|", ("product_id", "=", False), ("product_id", "=", product.id),
    ])
    if len(pkboms) != 1:
        counters["NOT_ONE_ACTIVE_PAKET_BOM"] += 1
        continue
    b = pkboms[0]
    try:
        output = b.product_uom_id._compute_quantity(
            b.product_qty, product.uom_id, round=False
        )
    except Exception:
        counters["INVALID_PAKET_UOM"] += 1
        continue
    if abs(output - 1) > 1e-7 or not b.bom_line_ids:
        counters["NOT_ONE_PAKET_OUTPUT_OR_EMPTY_BOM"] += 1
        continue
    if product.tracking != "none":
        counters["TRACKED_PAKET"] += 1
        continue
    if ("operation_ids" not in b._fields or b.operation_ids or
            b.picking_type_id.warehouse_id != pck):
        counters["PCK_BOM_ROUTE_OR_WORKORDER"] += 1
        continue
    for (delivery, slot), route_by_product in routes_by_slot.items():
        components = []
        unrouted = []
        issues = []
        kitchens = set()
        for bl in b.bom_line_ids:
            comp = bl.product_id
            try:
                qty = bl.product_uom_id._compute_quantity(
                    bl.product_qty, comp.uom_id, round=False
                )
            except Exception:
                issues.append("INVALID_PACKAGE_COMPONENT_UOM")
                continue
            if qty <= 0 or comp.categ_id == Cat:
                issues.append("NESTED_OR_ZERO_PACKAGE_COMPONENT")
                continue
            matches = route_by_product.get(comp.id, [])
            if len(matches) > 1:
                issues.append("DUPLICATE_PUBLISHED_ROUTE")
                continue
            if not matches:
                unrouted.append(comp.default_code or comp.id)
                continue
            if abs(qty - round(qty)) > 1e-7:
                issues.append("FRACTIONAL_KITCHEN_COMPONENT")
                continue
            component = dict(component_info(matches[0]))
            component["ratio_in_paket"] = int(round(qty))
            # Real test MUST be capable of at least ONE complete customer
            # Paket in MO1 AND ONE complete customer Paket in MO2. Ratio
            # may exceed a single kitchen BoM output. These quantities are
            # minimum, BEFORE any overlapping direct SO/RO demand is added.
            output = component["output"]
            maximum = component["published_max"]
            if (output and output > 0 and
                    abs(output - round(output)) < 1e-7 and maximum is not None):
                batches_per_paket_wave = ceil(qty / output)
                component["batches_per_package_wave"] = batches_per_paket_wave
                component["minimum_output_two_package_waves"] = (
                    2 * batches_per_paket_wave * output
                )
                component["two_package_waves_capacity"] = bool(
                    component["two_wave_capacity"] and
                    maximum + 1e-7 >=
                    component["minimum_output_two_package_waves"]
                )
                raw_mult = batches_per_paket_wave
                component["two_package_waves_cdc_raw_ready"] = bool(
                    component["cdc_two_batches_ready"] and
                    all(cdc_free[raw] + 1e-7 >= needed_two_batches * raw_mult
                        for raw, needed_two_batches in
                        component["raw_needs_for_two_batches"].items())
                )
            else:
                component["two_package_waves_capacity"] = False
                component["two_package_waves_cdc_raw_ready"] = False
            components.append(component)
            if component["warehouse"]:
                kitchens.add(component["warehouse"])
        if len(kitchens) < 2:
            continue
        counters["CROSS_KITCHEN_PUBLISHED_SLOT"] += 1
        if issues:
            counters["AMBIGUOUS_PAKET_COMPONENT"] += 1
            continue
        all_two_wave = bool(components and all(
            part["two_wave_capacity"] and
            not any(x in part["issue"] for x in (
                "BOM_KITCHEN_ROUTE", "WORKCENTER_ROUTE", "HAS_OR_UNKNOWN_WO"
            )) for part in components
        ))
        two_package_wave = bool(all_two_wave and all(
            c["two_package_waves_capacity"] for c in components
        ))
        cdc_two_batch_min = bool(components and all(
            c["cdc_two_batches_ready"] for c in components
        ))
        cdc_ok = bool(components and all(
            c["two_package_waves_cdc_raw_ready"] for c in components
        ))
        if all_two_wave:
            counters["ALL_KITCHEN_COMPONENTS_TWO_WAVES"] += 1
        if two_package_wave:
            counters["TWO_CUSTOMER_PAKET_WAVES_CAPACITY"] += 1
        if cdc_two_batch_min:
            counters["ALL_KITCHEN_COMPONENTS_CDC_TWO_BATCHES"] += 1
        if cdc_ok:
            counters["CDC_FOR_TWO_CUSTOMER_PAKET_WAVES"] += 1
        if two_package_wave and cdc_ok:
            counters["TWO_PAKET_WAVES_AND_CDC_READY"] += 1
        if unrouted:
            counters["HAS_UNROUTED_PCK_COMPONENT_TO_VALIDATE"] += 1
        if two_package_wave and cdc_ok and not unrouted and pck_route_ready:
            counters["FULL_MINIMUM_NATIVE_TWO_WAVE_CANDIDATE"] += 1
        blockers = [x for x in (
            "not_all_bom_two_waves" if not all_two_wave else None,
            "cannot_produce_one_paket_in_each_mo_wave"
                if not two_package_wave else None,
            "not_enough_cdc_raw_for_two_paket_waves" if not cdc_ok else None,
            "unrouted_pck_components_unverified" if unrouted else None,
            "no_unique_pck_manufacturing_type" if not pck_route_ready else None,
        ) if x]
        ranked.append({
            "paket_id": product.id,
            "paket_sku": product.default_code,
            "assembly_bom_id": b.id,
            "reference_date": str(delivery),
            "reference_slot": slot,
            "reference_is_past": delivery < today,
            "kitchens": sorted(kitchens),
            "components": components,
            "unrouted_pck_component_skus": unrouted,
            "all_two_wave_capacity": all_two_wave,
            "two_customer_paket_waves_capacity": two_package_wave,
            "all_cdc_two_batch_raw_ready": cdc_two_batch_min,
            "all_cdc_two_package_waves_raw_ready": cdc_ok,
            "full_minimum_candidate": not blockers,
            "blockers": blockers,
        })

ranked.sort(key=lambda r: (
    -int(r["full_minimum_candidate"]),
    -int(r["two_customer_paket_waves_capacity"]),
    -int(r["all_two_wave_capacity"]),
    -int(r["all_cdc_two_package_waves_raw_ready"]),
    len(r["unrouted_pck_component_skus"]),
    len(r["components"]),
    r["paket_id"],
    r["reference_date"],
))
print("CANDIDATE_COUNTS:", dict(sorted(counters.items())))
print("RANKED_CROSS_KITCHEN_CANDIDATES:", len(ranked))
for r in ranked[:12]:
    print("RANKED_NATIVE_TWO_WAVE_PAKET:", {
        "sku": r["paket_sku"], "id": r["paket_id"],
        "bom_id": r["assembly_bom_id"],
        "reference": r["reference_date"] + "/" + r["reference_slot"],
        "reference_is_past": r["reference_is_past"],
        "kitchens": r["kitchens"],
        "eligible_minimum": r["full_minimum_candidate"],
        "two_wave": r["all_two_wave_capacity"],
        "two_customer_paket_waves": r["two_customer_paket_waves_capacity"],
        "cdc_raw_two_bom_batches": r["all_cdc_two_batch_raw_ready"],
        "cdc_raw_for_two_paket_waves":
            r["all_cdc_two_package_waves_raw_ready"],
        "blockers": r["blockers"],
        "unrouted": r["unrouted_pck_component_skus"],
        "components": [
            {
                "sku": c["sku"], "id": c["id"],
                "kitchen": c["warehouse"],
                "BoM_output": c["output"],
                "Published_Max": c["published_max"],
                "Paket_ratio": c["ratio_in_paket"],
                "two_wave": c["two_wave_capacity"],
                "two_customer_paket_waves":
                    c["two_package_waves_capacity"],
                "minimum_output_two_paket_waves":
                    c.get("minimum_output_two_package_waves"),
                "cdc_raw_for_two_paket_waves":
                    c["two_package_waves_cdc_raw_ready"],
                "raw_shortage_count": len(c["raw_shortage_skus"]),
                "shortage_examples": c["raw_shortage_skus"][:4],
                "issues": c["issue"],
            }
            for c in r["components"]
        ],
    })

if counters["FULL_MINIMUM_NATIVE_TWO_WAVE_CANDIDATE"]:
    print("REAL_PAKET_TWO_WAVE_NATIVE_CDC_CANDIDATE_FOUND")
elif counters["TWO_CUSTOMER_PAKET_WAVES_CAPACITY"]:
    print("REAL_PAKET_TWO_PAKET_WAVES_CAPACITY_FOUND_BUT_RAW_OR_PCK_BLOCKED")
elif counters["ALL_KITCHEN_COMPONENTS_TWO_WAVES"]:
    print("REAL_PAKET_TWO_WAVE_CAPACITY_FOUND_BUT_PACKAGE_RATIO_BLOCKED")
else:
    print("REAL_PAKET_TWO_WAVE_CAPACITY_NOT_PROVEN_IN_PUBLISHED_REFERENCES")
print("NOTES: Ranking requires one COMPLETE customer Paket in MO1 and")
print("one COMPLETE customer Paket in MO2 across ALL kitchens; added SO direct")
print("and RO Paket/ordinary quantities require further capacity checks.")
print("NOTES: Two native BoM batches are MINIMUM only; real SO/RO demand")
print("must be recalculated for each SKU, per date/slot, with native raw demand.")
print("NOTES: Unrouted PCK components are UNVERIFIED, not automatically free.")
print("NOTES: No historical Planning date may be used for live production.")
print("NOTES: No stock was fabricated or capacity increased.")
print("READ_ONLY_REAL_PAKET_TWO_WAVE_RANKING_COMPLETE")
print("NO_PAKET_BOM_PLANNING_MO_STOCK_OR_DO_MUTATION")
env.cr.rollback()
