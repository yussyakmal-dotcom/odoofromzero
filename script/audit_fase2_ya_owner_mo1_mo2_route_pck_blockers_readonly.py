"""Fase2 clone READ ONLY: resolve owner's MO1/MO2 Paket route/PCK blockers.

Requires NO inventory adjustment, no changes to Published Planning and
no changes to Package assembly. Inspect missing route for 11790 (Sosis
Ayam), global Published Planning alternatives for five overcapacity
SKUs, and actual PCK free stock for three unplanned Paket components.

The owner source recipe-rounding preview found 715 theoretical partial
surplus across 10 kitchen SKUs, but five products were over the selected
historical Published Max, direct SKU11790 had no route for reference
2026-11-24/S1, and package PCK source for 12337/11298/11384 remained
unverified. These guards are not bypassed by CDC stock opname 10x.
"""
from collections import defaultdict
from datetime import date

DB = "erp-yussyakmal-mrp-test-RO_SO"
assert env.cr.dbname == DB, "STOP_WRONG_DATABASE"
env.cr.rollback()
env.cr.execute("SET TRANSACTION READ ONLY")
env.cr.execute("SHOW transaction_read_only")
assert env.cr.fetchone()[0] == "on", "STOP_READ_ONLY_UNAVAILABLE"

company = env["res.company"].sudo().browse(1).exists()
assert company
Product = env["product.product"].sudo().with_company(company)
Plans = env["ya.production.planning.line"].sudo().with_company(company)
Bom = env["mrp.bom"].sudo().with_company(company)
WH = env["stock.warehouse"].sudo().with_company(company)
pck = WH.search([("code", "=", "PCK"), ("company_id", "=", 1)])
assert len(pck) == 1 and pck.lot_stock_id
Quant = env["stock.quant"].sudo().with_company(company)

print("DATABASE:", DB)
print("MODE: READ_ONLY_OWNER_MIXED_PAKET_ROUTE_PCK_CAPACITY_BLOCKERS")
print("REFERENCE_DATE_SLOT:", "2026-11-24", "S1")
print("IMPORTANT: past Published Max is reference, not a future-day approval")

# These are exact requirements after two separate kitchen MO-wave recipe
# multiples in owner's last READ ONLY audit (not raw customer-order qty).
# Never silently treat this table as future Published Planning approval.
needed_output = {
    "11620": 66,
    "11645": 144,
    "10024": 110,
    "11591": 100,
    "10041": 135,
}
all_codes = sorted(set(needed_output) | {
    "11790", "12337", "11298", "11384"
})
p_by_code = {}
for code in all_codes:
    found = Product.search([("default_code", "=", code)])
    assert len(found) == 1, (
        "STOP_MISSING_OR_DUPLICATE_SKU", code, len(found)
    )
    p_by_code[code] = found

# All Published references, sorted by delivery date/slot; state kept.
routes = defaultdict(list)
for line in Plans.search([
    ("planning_id.state", "=", "published"),
    ("product_id", "in", [p.id for p in p_by_code.values()]),
]):
    product = line.product_id
    try:
        native_bom = line._capacity_bom()
        output = native_bom.product_uom_id._compute_quantity(
            native_bom.product_qty, product.uom_id, round=False
        )
        maximum = line.uom_id._compute_quantity(
            line.max_capacity, product.uom_id, round=False
        )
        wh = native_bom.picking_type_id.warehouse_id
        route = {
            "planning_line_id": line.id,
            "planning_date": str(line.planning_id.delivery_date),
            "slot": line.planning_id.slot,
            "kitchen": wh.code if wh else "MISSING",
            "kitchen_bom_id": native_bom.id,
            "bom_output": output,
            "published_max": maximum,
            "reference_date_past":
                line.planning_id.delivery_date < date.today(),
        }
    except Exception as exc:
        route = {
            "planning_line_id": line.id,
            "invalid_source": type(exc).__name__,
        }
    routes[product.default_code].append(route)

target = p_by_code["11790"]
all_native = Bom.search([
    ("active", "=", True),
    ("type", "=", "normal"),
    ("product_tmpl_id", "=", target.product_tmpl_id.id),
    "|", ("product_id", "=", False), ("product_id", "=", target.id),
])
print("SKU11790_PRODUCT:", {
    "id": target.id, "name": target.display_name,
    "category": target.categ_id.complete_name,
    "uom": target.uom_id.name,
    "tracking": target.tracking,
    "all_published_routes": len(routes["11790"]),
})
for b in all_native:
    print("SKU11790_REAL_NATIVE_BOM:", {
        "bom_id": b.id,
        "kitchen": b.picking_type_id.warehouse_id.code
            if b.picking_type_id.warehouse_id else "MISSING",
        "bom_output": b.product_uom_id._compute_quantity(
            b.product_qty, target.uom_id, round=False
        ),
        "wo_operations": len(b.operation_ids)
            if "operation_ids" in b._fields else "UNKNOWN",
    })
for entry in routes["11790"]:
    print("SKU11790_PUBLISHED_ROUTE_ALTERNATIVE:", entry)
if not routes["11790"]:
    print("SKU11790_PUBLISHED_ROUTE_NOT_FOUND_IN_ANY_SLOT")

for code, required in sorted(needed_output.items()):
    rows = sorted(routes[code],
                  key=lambda x: (x.get("planning_date", ""),
                                 x.get("slot", "")))
    eligible = [
        x for x in rows if x.get("published_max") is not None
        and x["published_max"] + 1e-7 >= required
    ]
    print("SKU_CAPACITY_REFERENCE_OPTIONS:", {
        "sku": code,
        "minimum_rounded_output_required": required,
        "published_reference_count": len(rows),
        "published_reference_with_enough_max_count": len(eligible),
        "references": rows[:20],
    })
    if not eligible:
        print("SKU_NO_EXISTING_PUBLISHED_MAX_CAN_COVER_FIXTURE:",
              code, required)

for code in ("12337", "11298", "11384"):
    product = p_by_code[code]
    quants = Quant.search([
        ("company_id", "=", company.id),
        ("product_id", "=", product.id),
        ("location_id", "=", pck.lot_stock_id.id),
        ("lot_id", "=", False),
        ("package_id", "=", False),
        ("owner_id", "=", False),
    ])
    physical = sum(quants.mapped("quantity"))
    reserved = sum(quants.mapped("reserved_quantity"))
    need = {"12337": 75, "11298": 15, "11384": 5}[code]
    print("PCK_UNROUTED_PACKAGE_COMPONENT_STOCK:", {
        "sku": code, "id": product.id,
        "category": product.categ_id.complete_name,
        "quantity_needed_for_owner_packages": need,
        "physical": physical, "reserved": reserved,
        "native_free": physical-reserved,
        "pck_stock_sufficient_without_replenishment":
            physical-reserved+1e-7 >= need,
        "tracking": product.tracking,
        "storable": (
            product.is_storable if "is_storable" in product._fields
            else product.type == "product"
        ),
        "is_finished_pastry":
            product.categ_id.complete_name.startswith(
                "All / Produk Jadi"
            ),
    })

print("NEXT: Do not fabricate published kitchen Max or treat CDC opname")
print("      as correction for insufficient capacity or PCK stock.")
print("NEXT: Distinguish a future *hypothetical capacity simulator* from")
print("      a Native MO1/MO2 release requiring actual published capacity.")
print("READ_ONLY_OWNER_MIXED_PAKET_ROUTE_PCK_BLOCKERS_AUDIT_PASS")
print("NO_MO_STOCK_PCK_PLANNING_OR_DO_WRITE")
env.cr.rollback()
