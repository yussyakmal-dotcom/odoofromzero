"""READ ONLY clone: confirm REAL Paket 12114 can use MO1 + MO2 in 2 kitchens.

Selected real SKU/BoM, not fake SKU:
 Paket 12114 / product 712 / assembly BoM 1405, one Paket output;
 components SKU12014 (ROTI), 12019 and 11999 (PST), qty1 each;
 historical Published 2026-11-24 S1 is REFERENCE ONLY, not a
 currently eligible production date. A later rollback test must stage
 a future date/slot in its own transaction without changing these rows.

Audit native manufacturing BoM output multiples, CDC raw stock,
operations/WO constraints, true PCK Manufacturing type and actual PCK
component stock; NO create/write/MO/stock posting.
"""
from collections import defaultdict
from datetime import date

DB = "erp-yussyakmal-mrp-test-RO_SO"
assert env.cr.dbname == DB, "STOP_WRONG_DATABASE"
env.cr.rollback()
env.cr.execute("SET TRANSACTION READ ONLY")
env.cr.execute("SHOW transaction_read_only")
assert env.cr.fetchone()[0] == "on", "STOP_NOT_SQL_READ_ONLY"

Mod = env["ir.module.module"].sudo().search([
    ("name", "=", "ya_sale_production_capacity")], limit=1)
assert Mod and Mod.state == "installed" and (
    Mod.installed_version == "19.0.1.1.3"), (
    "STOP_YA_SALES_NOT_TESTED_VERSION"
)
company = env["res.company"].sudo().browse(1).exists()
assert company, "STOP_NO_TEST_COMPANY1"
Products = env["product.product"].sudo().with_company(company)
Boms = env["mrp.bom"].sudo().with_company(company)
Planning = env["ya.production.planning.line"].sudo().with_company(company)
Warehouses = env["stock.warehouse"].sudo().with_company(company)
Quants = env["stock.quant"].sudo().with_company(company)
PCK = Warehouses.search([("code", "=", "PCK"), ("company_id", "=", 1)])
CDC = Warehouses.search([("code", "=", "CDC"), ("company_id", "=", 1)])
assert len(PCK) == len(CDC) == 1 and PCK.lot_stock_id and CDC.lot_stock_id
assert PCK != CDC

print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_REAL_PAKET12114_NATIVE_TWO_WAVE_GATE")
print("VERSION:", Mod.installed_version)
print("REFERENCE_PLANNING_DATE:", "2026-11-24", "SLOT: S1")
print("REFERENCE_DATE_IS_PAST:", date(2026, 11, 24) < date.today())
print("PROPOSED_NEXT_TEST: FUTURE SYNTHETIC DATE_S1; ROLLBACK ONLY")

package = Products.browse(712).exists()
assert package and package.default_code == "12114", (
    "STOP_REFERENCE_PACKAGE_MASTER_CHANGED"
)
assert package.categ_id.complete_name == "All / Produk Jadi / Paket"
boms = Boms.search([
    ("active", "=", True), ("type", "=", "normal"),
    ("product_tmpl_id", "=", package.product_tmpl_id.id),
    "|", ("product_id", "=", False), ("product_id", "=", package.id),
])
assert len(boms) == 1 and boms.id == 1405, (
    "STOP_REFERENCE_PACKAGE_ASSEMBLY_BOM_CHANGED"
)
package_output = boms.product_uom_id._compute_quantity(
    boms.product_qty, package.uom_id, round=False)
assert abs(package_output - 1.0) < 1e-7, (
    "STOP_REFERENCE_PAKET_NOT_ONE_OUTPUT"
)
print("PACKAGE:", {
    "id": package.id, "sku": package.default_code,
    "name": package.display_name, "tracking": package.tracking,
    "product_type": package.type,
    "assembly_bom": boms.id, "bom_output": package_output,
    "bom_operations": len(boms.operation_ids)
        if "operation_ids" in boms._fields else "UNKNOWN",
    "bom_picking_type": boms.picking_type_id.id,
    "bom_picking_warehouse":
        boms.picking_type_id.warehouse_id.code,
})

component_expectation = {
    1029: ("12014", "ROTI", 1081),
    1252: ("12019", "PST", 886),
    1015: ("11999", "PST", 885),
}
actual_components = defaultdict(float)
for bl in boms.bom_line_ids:
    item = bl.product_id
    val = bl.product_uom_id._compute_quantity(
        bl.product_qty, item.uom_id, round=False)
    actual_components[item.id] += val
print("PACKAGE_BOM_COMPONENTS:", sorted(actual_components.items()))
assert set(actual_components) == set(component_expectation), (
    "STOP_PAKET12114_COMPONENT_SET_CHANGED"
)

types = env["stock.picking.type"].sudo().search([
    ("code", "=", "mrp_operation"),
    ("warehouse_id", "=", PCK.id),
    ("company_id", "=", 1),
])
print("PCK_MANUFACTURING_OPERATION_TYPES:", [
    (t.id, t.name, t.default_location_src_id.id,
     t.default_location_dest_id.id) for t in types
])
print("PCK_NATIVE_MANUFACTURING_TYPE_UNIQUE:", len(types) == 1)

def exact_stock(pid, loc):
    q = Quants.search([
        ("company_id", "=", 1), ("product_id", "=", pid),
        ("location_id", "=", loc.id), ("lot_id", "=", False),
        ("package_id", "=", False), ("owner_id", "=", False),
    ])
    physical, reserved = (
        sum(q.mapped("quantity")), sum(q.mapped("reserved_quantity"))
    )
    return (physical, reserved, physical - reserved)

eligible = True
for pid, (sku, kitchen_code, line_id) in component_expectation.items():
    product = Products.browse(pid).exists()
    assert product and product.default_code == sku, (
        "STOP_REFERENCE_COMPONENT_CHANGED_%s" % pid
    )
    ratio = actual_components[pid]
    lines = Planning.search([
        ("id", "=", line_id),
        ("product_id", "=", pid),
        ("planning_id.delivery_date", "=", date(2026, 11, 24)),
        ("planning_id.slot", "=", "S1"),
        ("planning_id.state", "=", "published"),
    ])
    assert len(lines) == 1, (
        "STOP_PUBLISHED_REFERENCE_PLANNING_CHANGED_%s" % sku
    )
    line = lines[0]
    bom = line._capacity_bom()
    wh = bom.picking_type_id.warehouse_id
    assert wh and wh.code == kitchen_code and wh.company_id == company
    expected_name = " ".join(
        ("Dapur " + (line.planning_id.workcenter_id.name or "")).casefold().split()
    )
    actual_name = " ".join((wh.name or "").casefold().split())
    assert expected_name == actual_name, (
        "STOP_WORKCENTER_WAREHOUSE_ROUTE_MISMATCH_%s" % sku
    )
    assert bom.type == "normal" and bom.active
    output = bom.product_uom_id._compute_quantity(
        bom.product_qty, product.uom_id, round=False)
    maximum = line.uom_id._compute_quantity(
        line.max_capacity, product.uom_id, round=False)
    # Two independent manufacturing waves need at least one whole BOM batch
    # in EACH wave. Product output is not necessarily 1 despite Paket ratio1.
    two_wave = (
        output > 0 and abs(output - round(output)) < 1e-7
        and maximum >= 2 * output
        and abs(maximum / output - round(maximum / output)) < 1e-7
        and ratio > 0 and abs(ratio - round(ratio)) < 1e-7
        and product.tracking == "none"
    )
    if not two_wave:
        eligible = False
    raw_needs = defaultdict(float)
    raw_products = {}
    for bl in bom.bom_line_ids:
        raw = bl.product_id
        raw_qty = bl.product_uom_id._compute_quantity(
            bl.product_qty, raw.uom_id, round=False
        )
        if raw_qty <= 0:
            eligible = False
            continue
        raw_needs[raw.id] += raw_qty * 2
        raw_products[raw.id] = raw
    raw_summaries = []
    cdc_stock_sufficient = True
    for raw_id, qty_two_batches in sorted(raw_needs.items()):
        raw = raw_products[raw_id]
        cdc_onhand, cdc_reserved, cdc_free = exact_stock(
            raw_id, CDC.lot_stock_id
        )
        in_cdc = cdc_free + 1e-7 >= qty_two_batches
        cdc_stock_sufficient &= in_cdc and raw.tracking == "none"
        raw_summaries.append({
            "sku": raw.default_code, "id": raw_id,
            "required_two_bom_batches_base": qty_two_batches,
            "base_uom": raw.uom_id.name,
            "tracking": raw.tracking,
            "cdc_physical": cdc_onhand,
            "cdc_reserved": cdc_reserved,
            "cdc_free": cdc_free,
            "cdc_sufficient": in_cdc,
        })
    # Snapshot is read-only: in the native rollback fixture we may consume
    # MORE than two batches after SO+RO final demand; recheck exact required
    # qty there and STOP if CDC lacks inventory.
    print("KITCHEN_COMPONENT_GATE:", {
        "product_id": pid, "sku": sku, "kitchen": kitchen_code,
        "planning_line_id": line.id, "planning_max": maximum,
        "native_kitchen_bom": bom.id, "bom_output_base": output,
        "package_ratio_base": ratio, "two_mo_waves_possible": two_wave,
        "kitchen_fg_stock": exact_stock(pid, wh.lot_stock_id),
        "pck_fg_stock": exact_stock(pid, PCK.lot_stock_id),
        "bom_operations": len(bom.operation_ids)
            if "operation_ids" in bom._fields else "UNKNOWN",
        "raw_materials_two_batches": raw_summaries,
        "cdc_two_batches_sufficient": cdc_stock_sufficient,
    })
    if not cdc_stock_sufficient:
        eligible = False

print("PCK_PACKAGE_FINISHED_STOCK:", exact_stock(
    package.id, PCK.lot_stock_id))
ready = bool(
    eligible and len(types) == 1 and package.tracking == "none"
    and "operation_ids" in boms._fields and not boms.operation_ids
)
print("REAL_PAKET_12114_TWO_WAVE_PREFLIGHT_ELIGIBLE:", ready)
if ready:
    print("REAL_PAKET_12114_TWO_WAVE_PREFLIGHT_PASS")
else:
    print("REAL_PAKET_12114_TWO_WAVE_BLOCKED_REVIEW_DETAILS")
print("AUDIT_NOTE: 2 BOM batches per kitchen is a MINIMUM, not final RO+SO demand")
print("AUDIT_NOTE: real Package BoM 1405 and Published Planning reference are unchanged")
print("READ_ONLY_PAKET12114_NATIVE_MO1_MO2_GATE_COMPLETE")
print("NO_PLANNING_PACKAGE_MO_STOCK_OR_DELIVERY_WRITE")
env.cr.rollback()
