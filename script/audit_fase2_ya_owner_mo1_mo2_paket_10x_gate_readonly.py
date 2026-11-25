"""READ-ONLY source bridge for OWNER'S EXACT two-wave mixed Paket fixture.

MO1 demand basket (NOT native mrp.production for a Paket):
  12205 Paket Nampan isi 20 D qty5, 10024 Martabak qty20,
  11591 Puding Buah Mini qty25, 11637 Kue Ku Merah Kecil qty10.
MO2 demand basket:
  12184 Paket Buka Bersama qty15, 11552 Bf Roll qty10,
  11637 Kue Ku Merah Kecil qty30, 11790 SOSIS AYAM qty40.

Expand real 1-Paket assembly BoMs and use published reference kitchen
routes. No changing Published Max or kitchen BoMs; no auto-inferred
PCK source for unrouted finished components. Preview exact native
MO BoM rounding, and raw material deficit at the existing CDC.
The established stock-opname 10x WILL be used ONLY in a later
single-transaction clone rollback QA, never in this read-only audit.
"""
from collections import Counter, defaultdict
from datetime import date
from math import ceil

CLONE = "erp-yussyakmal-mrp-test-RO_SO"
assert env.cr.dbname == CLONE, "STOP_WRONG_DATABASE"
env.cr.rollback()
env.cr.execute("SET TRANSACTION READ ONLY")
env.cr.execute("SHOW transaction_read_only")
assert env.cr.fetchone()[0] == "on", "STOP_READ_ONLY_NOT_ENFORCED"
Module = env["ir.module.module"].sudo().search([
    ("name", "=", "ya_sale_production_capacity")
], limit=1)
assert Module and Module.state == "installed" and (
    Module.installed_version == "19.0.1.1.3"
), "STOP_UNKNOWN_SALES_ADDON"
company = env["res.company"].sudo().browse(1).exists()
assert company
Product = env["product.product"].sudo().with_company(company)
Bom = env["mrp.bom"].sudo().with_company(company)
Plans = env["ya.production.planning"].sudo().with_company(company)
Wh = env["stock.warehouse"].sudo().with_company(company)
Quants = env["stock.quant"].sudo().with_company(company)
cdc = Wh.search([("code", "=", "CDC"), ("company_id", "=", company.id)])
pck = Wh.search([("code", "=", "PCK"), ("company_id", "=", company.id)])
assert len(cdc) == len(pck) == 1 and cdc.lot_stock_id and pck.lot_stock_id

waves = {
    "MO1": [("12205", 5), ("10024", 20),
            ("11591", 25), ("11637", 10)],
    "MO2": [("12184", 15), ("11552", 10),
            ("11637", 30), ("11790", 40)],
}
package_codes = {"12205", "12184"}
all_codes = sorted({code for rows in waves.values() for code, _ in rows})
products = Product.search([("default_code", "in", all_codes)])
by_code = defaultdict(list)
for product in products:
    by_code[product.default_code].append(product)
assert all(len(by_code[code]) == 1 for code in all_codes), (
    "STOP_MISSING_OR_AMBIGUOUS_REAL_REQUEST_SKU",
    [(code, len(by_code[code])) for code in all_codes]
)
assert all(
    (by_code[code][0].categ_id.complete_name ==
     "All / Produk Jadi / Paket") == (code in package_codes)
    for code in all_codes
), "STOP_SKU_CATEGORY_NOT_MATCH_OWNER_PAKET_VS_DIRECT"

print("DATABASE:", CLONE)
print("MODE: READ_ONLY_OWNER_MO1_MO2_EXACT_PAKET_AND_OPNAME10X_GATE")
print("YA_SALES_VERSION:", Module.installed_version)
print("MO_WAVE_INPUT_IS_DEMAND_BASKET_NOT_NATIVE_PACKAGE_MO")
print("OWNER_WAVE_ROWS:", waves)
print("OWNER_FINISHED_QTY:", sum(q for rows in waves.values()
                                  for _, q in rows))
print("DIRECT_OVERLAP_SKU11637:", 10, "+", 30, "=", 40)
print("PCK_ASSEMBLY_ONLY_PACKAGE_CODES:", sorted(package_codes))

package_boms = {}
package_parts = {}
for code in sorted(package_codes):
    pkg = by_code[code][0]
    matches = Bom.search([
        ("type", "=", "normal"), ("active", "=", True),
        ("product_tmpl_id", "=", pkg.product_tmpl_id.id),
        "|", ("product_id", "=", False), ("product_id", "=", pkg.id),
    ])
    assert len(matches) == 1, (
        "STOP_PAKET_REQUIRES_EXACTLY_ONE_ACTIVE_BOM", code, len(matches)
    )
    bom = matches[0]
    amount = bom.product_uom_id._compute_quantity(
        bom.product_qty, pkg.uom_id, round=False)
    assert abs(amount - 1.0) < 1e-7, (
        "STOP_PAKET_BOM_NOT_ONE_OUTPUT", code, amount
    )
    assert (bom.picking_type_id and
            bom.picking_type_id.warehouse_id == pck), (
        "STOP_PAKET_ASSEMBLY_NOT_AT_PCK", code
    )
    assert not bom.operation_ids, (
        "STOP_PAKET_BOM_WO_NOT_SUPPORTED", code
    )
    parts = defaultdict(float)
    for line in bom.bom_line_ids:
        comp = line.product_id
        assert comp.id != pkg.id
        assert comp.categ_id.complete_name != "All / Produk Jadi / Paket", (
            "STOP_NESTED_PAKET_COMPONENT", code, comp.default_code
        )
        qty = line.product_uom_id._compute_quantity(
            line.product_qty, comp.uom_id, round=False
        )
        assert qty > 0
        parts[comp.id] += qty
    assert parts
    package_boms[pkg.id] = bom
    package_parts[pkg.id] = dict(parts)
    print("REAL_PAKET_BOM:", {
        "sku": code, "name": pkg.display_name,
        "package_product_id": pkg.id,
        "assembly_bom_id": bom.id,
        "ratio_in_product_base_uom": [
            (Product.browse(pid).default_code, pid, qty)
            for pid, qty in sorted(parts.items())
        ],
    })
print("EXACT_TWO_REAL_PACKAGE_BOMS_VALIDATED_PASS")

routes_by_slot = defaultdict(lambda: defaultdict(list))
published = Plans.search([("state", "=", "published")])
for planning in published:
    for line in planning.line_ids:
        routes_by_slot[(planning.delivery_date, planning.slot)][
            line.product_id.id].append(line)
print("PUBLISHED_REFERENCE_DATE_SLOTS:", len(routes_by_slot))

# All directly sold items MUST be manufactured kitchen SKUs, whereas
# unplanned package components need explicit PCK/manual source review.
direct_ids = {
    by_code[code][0].id for rows in waves.values()
    for code, _ in rows if code not in package_codes
}
package_component_ids = set().union(*[
    set(parts) for parts in package_parts.values()
])
needed_ids = direct_ids | package_component_ids
def route_score(entry):
    (day, slot), rows = entry
    exact = sum(len(rows.get(pid, [])) == 1 for pid in needed_ids)
    dup = sum(len(rows.get(pid, [])) > 1 for pid in needed_ids)
    return (exact, -dup, day.toordinal(), slot)

assert routes_by_slot, "STOP_NO_PUBLISHED_PLANNING_REFERENCE"
reference, route_index = max(routes_by_slot.items(), key=route_score)
print("BEST_REFERENCE_PUBLISHED_SLOT:", str(reference[0]), reference[1],
      "REFERENCE_DATE_PAST:", reference[0] < date.today(),
      "COVERED_SKUS:", sum(len(route_index.get(p, [])) == 1
                          for p in needed_ids), "TOTAL:", len(needed_ids))
print("NOTE: reference Planning date is NEVER a production delivery date")

route_of = {}
unrouted = {}
ambiguous = []
for pid in sorted(needed_ids):
    lines = route_index.get(pid, [])
    product = Product.browse(pid)
    if len(lines) == 1:
        line = lines[0]
        try:
            bom = line._capacity_bom()
            wh = bom.picking_type_id.warehouse_id
            assert (bom.active and bom.type == "normal" and wh and
                    wh.company_id == company and wh.lot_stock_id and
                    bom.picking_type_id.default_location_dest_id ==
                    wh.lot_stock_id)
            expected = " ".join(
                ("Dapur " + (line.planning_id.workcenter_id.name or "")
                ).casefold().split())
            actual = " ".join((wh.name or "").casefold().split())
            assert expected == actual
            output = bom.product_uom_id._compute_quantity(
                bom.product_qty, product.uom_id, round=False)
            maximum = line.uom_id._compute_quantity(
                line.max_capacity, product.uom_id, round=False)
            assert output > 0 and maximum >= 0
            assert abs(output - round(output)) < 1e-7
            assert abs(maximum - round(maximum)) < 1e-7
            assert abs(maximum / output - round(maximum / output)) < 1e-7
            assert product.tracking == "none"
        except Exception as exc:
            ambiguous.append((product.default_code, "INVALID_KITCHEN_BOM_ROUTE",
                              type(exc).__name__))
            continue
        route_of[pid] = {
            "line": line, "bom": bom, "warehouse": wh,
            "bom_output": int(round(output)),
            "published_max": int(round(maximum)),
        }
    elif len(lines) == 0:
        unrouted[pid] = product
    else:
        ambiguous.append((product.default_code, "DUPLICATE_PUBLISHED_ROUTE",
                          len(lines)))

missing_direct = sorted(
    by_code[code][0].default_code for rows in waves.values()
    for code, _ in rows if code not in package_codes and
    by_code[code][0].id not in route_of
)
print("REFERENCE_ROUTE_UNRESOLVED:", ambiguous)
print("REFERENCE_DIRECT_SKU_WITHOUT_KITCHEN_ROUTE:", sorted(
    set(missing_direct)))
print("UNROUTED_PAKET_COMPONENTS_REQUIRE_SOURCE_REVIEW:", [
    (product.default_code, pid, product.categ_id.complete_name)
    for pid, product in sorted(unrouted.items())
    if pid in package_component_ids
])

# Demand: each wave is expanded independently. Same kitchen SKU appearing
# both as direct final product and Paket component is counted ONCE in the
# aggregated SKU requirement, retaining demand source provenance.
wave_kitchen = defaultdict(lambda: defaultdict(float))
wave_pck = defaultdict(lambda: defaultdict(float))
for wave, rows in waves.items():
    for code, qty in rows:
        product = by_code[code][0]
        if code in package_codes:
            for component, ratio in package_parts[product.id].items():
                demand = qty * ratio
                if component in route_of:
                    wave_kitchen[wave][component] += demand
                else:
                    wave_pck[wave][component] += demand
        else:
            wave_kitchen[wave][product.id] += qty

for wave in ("MO1", "MO2"):
    print("EXPANDED_WAVE_KITCHEN_DEMAND:", wave, [
        (Product.browse(pid).default_code, pid, qty)
        for pid, qty in sorted(wave_kitchen[wave].items())
    ])
    print("EXPANDED_WAVE_PCK_UNROUTED_DEMAND_REVIEW:", wave, [
        (Product.browse(pid).default_code, pid, qty)
        for pid, qty in sorted(wave_pck[wave].items())
    ])

# This is the genuine stricter gate: each wave is a separate native MO per
# manufactured SKU (if its quantity >0), rounded to whole real kitchen BoM
# batches. Each SKU's two waves must fit ONE unchanged Published Max.
mo_plan = {}
blockers = []
raw_needs_by_kitchen = defaultdict(float)
rounding_totals = {
    "MO1": {"gross_demand": 0, "rounded_production": 0,
            "intermediate_surplus": 0},
    "MO2": {"gross_demand": 0, "covered_by_mo1_surplus": 0,
            "net_incremental_demand": 0, "rounded_production": 0,
            "additional_rounding_surplus": 0},
}
for pid in sorted(set(wave_kitchen["MO1"]) | set(wave_kitchen["MO2"])):
    product = Product.browse(pid)
    route = route_of.get(pid)
    if not route:
        blockers.append(("MISSING_UNIQUE_KITCHEN_ROUTE", product.default_code))
        continue
    need1 = wave_kitchen["MO1"].get(pid, 0)
    need2 = wave_kitchen["MO2"].get(pid, 0)
    if any(abs(v-round(v)) > 1e-7 for v in (need1, need2)):
        blockers.append(("FRACTIONAL_FINISHED_KITCHEN_DEMAND",
                         product.default_code, need1, need2))
        continue
    batch = route["bom_output"]
    qty1 = ceil(need1 / batch) * batch
    # Owner principle: an MO2 makes ONLY the missing increment. Any MO1
    # BoM-rounded surplus not needed by MO1 demand remains available to
    # cover the same SKU in MO2 before creating more batches. This is a
    # production-volume preview, not permission to steal physically
    # reserved SO/RO stock; the final PCK ledger still checks native free.
    provisional_mo1_surplus = qty1 - need1
    mo1_surplus_reused = min(provisional_mo1_surplus, need2)
    mo2_net_incremental_need = max(0, need2 - mo1_surplus_reused)
    qty2 = ceil(mo2_net_incremental_need / batch) * batch
    maximum = route["published_max"]
    if qty1 + qty2 > maximum:
        blockers.append(("TWO_MO_WAVES_EXCEED_PUBLISHED_MAX",
                         product.default_code, qty1, qty2, maximum))
    if qty1 and qty2 and qty1+qty2 <= maximum:
        print("SKU_IN_BOTH_MO_WAVES_CAPACITY_PASS:",
              product.default_code, qty1, qty2, maximum)
    # Count an early-rounding surplus only ONCE. As it is consumed by later
    # MO2 demand, it is no longer excess at the END of both waves.
    extra1_provisional = int(round(provisional_mo1_surplus))
    mo1_used = int(round(mo1_surplus_reused))
    net2 = int(round(mo2_net_incremental_need))
    extra2 = qty2 - net2
    final_extra = int(round(qty1 + qty2 - need1 - need2))
    assert final_extra == extra1_provisional - mo1_used + extra2
    assert final_extra >= 0
    rounding_totals["MO1"]["gross_demand"] += int(round(need1))
    rounding_totals["MO1"]["rounded_production"] += qty1
    rounding_totals["MO1"]["intermediate_surplus"] += extra1_provisional
    rounding_totals["MO2"]["gross_demand"] += int(round(need2))
    rounding_totals["MO2"]["covered_by_mo1_surplus"] += mo1_used
    rounding_totals["MO2"]["net_incremental_demand"] += net2
    rounding_totals["MO2"]["rounded_production"] += qty2
    rounding_totals["MO2"]["additional_rounding_surplus"] += extra2
    for wave, required, rounded, surplus, carried, net_demand in (
        ("MO1", int(round(need1)), qty1, extra1_provisional, 0,
         int(round(need1))),
        ("MO2", int(round(need2)), qty2, extra2, mo1_used, net2),
    ):
        print("RECIPE_ROUNDING_PER_WAVE_SKU:", {
            "wave": wave,
            "sku": product.default_code,
            "product_id": pid,
            "kitchen": route["warehouse"].code,
            "required_after_paket_expansion": required,
            "bom_output_per_batch": batch,
            "demand_covered_by_prior_mo1_surplus": carried,
            "net_incremental_demand_to_produce": net_demand,
            "batches_needed": rounded // batch,
            "rounded_production": rounded,
            "extra_from_this_wave_batch_rounding": surplus,
            "published_max": maximum,
            "combined_both_waves_within_max": qty1 + qty2 <= maximum,
        })
    print("RECIPE_ROUNDING_PER_SKU_TOTAL:", {
        "sku": product.default_code, "product_id": pid,
        "mo1_temporary_surplus": extra1_provisional,
        "mo1_surplus_reused_for_mo2": mo1_used,
        "mo2_new_batch_rounding_surplus": extra2,
        "true_final_extra_after_both_waves": final_extra,
    })
    if need2 and qty2 == 0:
        print("MO2_SKU_FULLY_COVERED_BY_MO1_SURPLUS_NO_MO2_NEEDED:",
              product.default_code)
    plan = {
        "sku": product.default_code, "product_id": pid,
        "kitchen": route["warehouse"].code,
        "mo1_demand": int(round(need1)), "mo2_demand": int(round(need2)),
        "bom_output": batch, "mo1_rounded": qty1,
        "mo2_net_incremental_demand": net2,
        "mo2_demand_covered_by_mo1_surplus": mo1_used,
        "mo2_rounded": qty2, "total_rounded": qty1+qty2,
        "mo1_intermediate_extra_from_rounding": extra1_provisional,
        "mo2_extra_from_rounding": extra2,
        "total_final_extra_after_mo1_reuse": final_extra,
        "published_max": maximum, "capacity_ok": qty1+qty2 <= maximum,
        "kitchen_bom": route["bom"].id,
    }
    mo_plan[pid] = plan
    print("ACTUAL_BOM_MO1_MO2_PLAN:", plan)
    for bl in route["bom"].bom_line_ids:
        raw = bl.product_id
        ratio = bl.product_uom_id._compute_quantity(
            bl.product_qty, raw.uom_id, round=False
        )
        if ratio <= 0 or raw.tracking != "none":
            blockers.append(("UNSUPPORTED_RAW_COMPONENT",
                             raw.default_code, product.default_code))
            continue
        raw_needs_by_kitchen[(route["warehouse"].id, raw.id)] += (
            ratio * (qty1+qty2)/batch
        )

# Totals are a COUNT of surplus units across different SKUs, not an
# interchangeable pool of inventory. Exact per-SKU FINAL surplus above is
# authoritative (especially overlapping SKU11637). MO1 provisional extra
# and MO2 extra must NOT be added without deducting MO1 quantity reused.
all_resolved = all(
    pid in mo_plan
    for pid in set(wave_kitchen["MO1"]) | set(wave_kitchen["MO2"])
)
for wave in ("MO1", "MO2"):
    print("RECIPE_ROUNDING_SUMMARY_PER_WAVE:", wave,
          rounding_totals[wave])
true_final_units = (
    rounding_totals["MO1"]["intermediate_surplus"]
    - rounding_totals["MO2"]["covered_by_mo1_surplus"]
    + rounding_totals["MO2"]["additional_rounding_surplus"]
)
grand_produced = (
    rounding_totals["MO1"]["rounded_production"]
    + rounding_totals["MO2"]["rounded_production"]
)
grand_demand = (
    rounding_totals["MO1"]["gross_demand"]
    + rounding_totals["MO2"]["gross_demand"]
)
assert true_final_units == grand_produced - grand_demand
print("RECIPE_ROUNDING_SUMMARY_BOTH_WAVES:", {
    "total_demand_after_paket_expansion": grand_demand,
    "total_actual_production_after_bom_rounding": grand_produced,
    "mo1_provisional_surplus": rounding_totals["MO1"]["intermediate_surplus"],
    "mo1_surplus_reused_for_mo2":
        rounding_totals["MO2"]["covered_by_mo1_surplus"],
    "mo2_additional_rounding_surplus":
        rounding_totals["MO2"]["additional_rounding_surplus"],
    "TRUE_FINAL_EXTRA_UNITS": true_final_units,
})
print("RECIPE_ROUNDING_ALL_SKUS_RESOLVED:", all_resolved)
if not all_resolved:
    print("RECIPE_ROUNDING_TOTAL_PARTIAL_ONLY: missing unique validated"
          " Published kitchen route or fractional demand for some SKUs")
print("RECIPE_ROUNDING_NOTE: MO1 excess of SAME SKU is reused to"
      " cover incremental MO2 demand before creating MO2 batches")
print("RECIPE_ROUNDING_NOTE: Qty excess cannot replace another SKU;"
      " Paket final SKU output1 is assembled in PCK separately")
print("RECIPE_ROUNDING_NOTE: a positive extra with combined MO1+MO2"
      " above Published Max is an INVALID production plan, not approved surplus")

# Stock Opname 10x preview for *all* waves, aggregated shared raw deficits.
# Keep existing quantity+reservation completely untouched in this audit.
raw_gross = defaultdict(float)
invalid_for_seed = []
raw_details = []
for (wh_id, pid), required in sorted(raw_needs_by_kitchen.items()):
    kitchen = Wh.browse(wh_id)
    quants = Quants.search([
        ("company_id", "=", company.id),
        ("location_id", "child_of", kitchen.lot_stock_id.id),
        ("location_id.usage", "=", "internal"),
        ("product_id", "=", pid),
    ])
    physical = sum(quants.mapped("quantity"))
    reserved = sum(quants.mapped("reserved_quantity"))
    if physical < -1e-7 or reserved > 1e-7:
        invalid_for_seed.append(("KITCHEN_NEGATIVE_OR_RESERVED",
                                 kitchen.code, pid, physical, reserved))
    gross_shortage = max(0.0, required - physical)
    raw_gross[pid] += gross_shortage
    raw_details.append((kitchen.code, pid, required, physical, reserved))
print("RAW_REQUIRED_BY_KITCHEN_BOTH_WAVES:", raw_details)

opname_preview = []
for pid, total_short in sorted(raw_gross.items()):
    raw = Product.browse(pid)
    quant = Quants.search([
        ("company_id", "=", company.id),
        ("location_id", "child_of", cdc.lot_stock_id.id),
        ("location_id.usage", "=", "internal"),
        ("product_id", "=", pid),
    ])
    physical = sum(quant.mapped("quantity"))
    reserved = sum(quant.mapped("reserved_quantity"))
    if physical < -1e-7 or reserved > 1e-7 or raw.tracking != "none":
        invalid_for_seed.append(("CDC_NEGATIVE_RESERVED_OR_TRACKED",
                                 raw.default_code, physical, reserved))
    if ("is_storable" in raw._fields and not raw.is_storable):
        invalid_for_seed.append(("RAW_NOT_STORABLE", raw.default_code))
    deficit = max(0.0, total_short - physical)
    # Extend the original 10x-shortfall formula with an explicit minimum
    # fulfillment floor: 10x the shortfall may by itself be less than total
    # demand when CDC already has stock just below requirement.
    target = max(physical, total_short, 10 * deficit)
    preview = {
        "raw_sku": raw.default_code, "id": pid, "uom": raw.uom_id.name,
        "gross_kitchen_shortfall": round(total_short, 4),
        "cdc_physical": round(physical, 4),
        "cdc_reserved": round(reserved, 4),
        "outstanding": round(deficit, 4),
        "cdc_target_10x_with_minimum_demand_floor": round(target, 4),
        "to_add_in_later_rollback_test": round(target-physical, 4),
    }
    opname_preview.append(preview)
print("OPNAME_10X_RAW_SKU_COUNT:", len(opname_preview))
for row in opname_preview:
    print("OPNAME_10X_FUTURE_ROLLBACK_PREVIEW:", row)
print("OPNAME_10X_INVALID_SOURCE_GUARDS:", invalid_for_seed)

if missing_direct or ambiguous:
    blockers.append(("REFERENCE_PUBLISHED_ROUTES_INCOMPLETE",
                     missing_direct, ambiguous))
if any(pid in package_component_ids for pid in unrouted):
    blockers.append(("UNROUTED_PAKET_COMPONENT_SOURCE_NOT_VERIFIED", [
        Product.browse(pid).default_code
        for pid in sorted(package_component_ids & set(unrouted))
    ]))
if invalid_for_seed:
    blockers.append(("OPNAME_10X_GUARD_REQUIRES_REVIEW",
                     len(invalid_for_seed)))

print("OWNER_FIXTURE_NATIVE_READINESS_BLOCKERS:", blockers)
print("OWNER_FIXTURE_REFERENCE_PLANNING_GUARD_PASS:",
      not missing_direct and not ambiguous)
print("OWNER_FIXTURE_ALL_NATIVE_CAPACITY_WITHIN_PUBLISHED_MAX:",
      not any(x[0] == "TWO_MO_WAVES_EXCEED_PUBLISHED_MAX"
              for x in blockers))
print("OWNER_FIXTURE_FULL_NATIVE_READY:", not blockers)
print("NOTE: NO real inventory adjustment made; 10x requires")
print("      a new Fase2 CLONE-ONLY SINGLE ROLLBACK test.")
print("READ_ONLY_OWNER_MIXED_PAKET_MO1_MO2_10X_GATE_COMPLETE")
print("NO_PLANNING_BOM_MO_QUANT_SALES_OR_DO_WRITE")
env.cr.rollback()
