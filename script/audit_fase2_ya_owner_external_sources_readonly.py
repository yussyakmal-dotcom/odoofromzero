"""Odoo 19 clone-only READ-ONLY external source for exact owner mixed Paket fixture.

The exact owner basket's 11790 SOSIS AYAM is categorized Konsinyasi Masuk;
12337 is an unrouted finished pastry component of 12184; 11298/11384
are Paket packaging. This is a route and stock source diagnostic. NEVER
fabricate source stock or classify consignment as a native kitchen MO.

No writes, no inventory adjustment, no reservations or DO.
"""
from collections import defaultdict

DB = "erp-yussyakmal-mrp-test-RO_SO"
assert env.cr.dbname == DB, "STOP_WRONG_DATABASE"
env.cr.rollback()
env.cr.execute("SET TRANSACTION READ ONLY")
env.cr.execute("SHOW transaction_read_only")
assert env.cr.fetchone()[0] == "on", "STOP_READONLY_ISOLATION_NOT_SET"
mod = env["ir.module.module"].sudo().search([
    ("name", "=", "ya_sale_production_capacity"),
    ("state", "=", "installed"),
], limit=1)
assert mod and mod.installed_version == "19.0.1.1.3", (
    "STOP_UNEXPECTED_SALES_VERSION"
)

codes = {
    "11790": {"qty": 40, "role": "MO2_CONSIGNMENT_INCOMING"},
    "12337": {"qty": 75, "role": "MO2_PAKET_FINISHED_PASTRY_COMPONENT"},
    "11298": {"qty": 15, "role": "MO2_PAKET_PACKAGING"},
    "11384": {"qty": 5, "role": "MO1_PAKET_PACKAGING"},
}
Product = env["product.product"].sudo()
BOM = env["mrp.bom"].sudo()
Move = env["stock.move"].sudo()
Quant = env["stock.quant"].sudo()
WH = env["stock.warehouse"].sudo()
company = env["res.company"].sudo().browse(1).exists()
assert company, "STOP_NO_COMPANY1"
whs = WH.search([("company_id", "=", company.id)])
pck = whs.filtered(lambda w: w.code == "PCK")
assert len(pck) == 1 and pck.lot_stock_id
print("DATABASE:", DB)
print("MODE: READ_ONLY_OWNER_EXTERNAL_SOURCE_STOCK_AND_HISTORY")
print("EXACT_OWNER_EXTERNAL_SKUS:", codes)

found = Product.search([("default_code", "in", list(codes))])
by_code = defaultdict(list)
for p in found:
    by_code[p.default_code].append(p)
for code in codes:
    assert len(by_code[code]) == 1, (
        "STOP_MISSING_OR_DUPLICATE_SOURCE_SKU", code,
        len(by_code[code])
    )

for code, expected in codes.items():
    p = by_code[code][0]
    company_stock = Quant.search([
        ("company_id", "=", company.id),
        ("product_id", "=", p.id),
        ("location_id.usage", "=", "internal"),
    ])
    physical = sum(company_stock.mapped("quantity"))
    reserved = sum(company_stock.mapped("reserved_quantity"))
    pck_stock = company_stock.filtered(
        lambda q: q.location_id == pck.lot_stock_id
    )
    pck_physical = sum(pck_stock.mapped("quantity"))
    pck_reserved = sum(pck_stock.mapped("reserved_quantity"))
    bom_matches = BOM.search([
        ("active", "=", True),
        ("type", "=", "normal"),
        ("product_tmpl_id", "=", p.product_tmpl_id.id),
        "|", ("product_id", "=", False),
             ("product_id", "=", p.id),
    ])
    all_published = env["ya.production.planning.line"].sudo().search([
        ("product_id", "=", p.id),
        ("planning_id.state", "=", "published"),
    ])
    print("EXTERNAL_PRODUCT:", {
        "sku": code, "product_id": p.id,
        "name": p.display_name,
        "role": expected["role"],
        "demand": expected["qty"],
        "category": p.categ_id.complete_name,
        "tracking": p.tracking,
        "storable": (
            p.is_storable if "is_storable" in p._fields
            else p.type == "product"
        ),
        "uom": p.uom_id.name,
        "PCK_exact_physical": pck_physical,
        "PCK_exact_reserved": pck_reserved,
        "PCK_exact_free": pck_physical - pck_reserved,
        "company_internal_physical_all_locations": physical,
        "company_internal_reserved_all_locations": reserved,
        "active_normal_bom_count": len(bom_matches),
        "published_kitchen_routes_count": len(all_published),
    })
    for q in company_stock.sorted(
        key=lambda x: x.quantity-x.reserved_quantity, reverse=True
    )[:20]:
        if abs(q.quantity) < 1e-7 and abs(q.reserved_quantity) < 1e-7:
            continue
        print("SOURCE_QUANT_LOCATION:", {
            "sku": code,
            "location_id": q.location_id.id,
            "location_path": q.location_id.complete_name,
            "usage": q.location_id.usage,
            "physical": q.quantity,
            "reserved": q.reserved_quantity,
            "free": q.quantity-q.reserved_quantity,
            "lot_id": q.lot_id.id,
            "owner_id": q.owner_id.id,
            "package_id": q.package_id.id,
        })
    for b in bom_matches[:8]:
        pt = b.picking_type_id
        print("SOURCE_ACTIVE_BOM:", {
            "sku": code, "bom_id": b.id,
            "output": b.product_uom_id._compute_quantity(
                b.product_qty, p.uom_id, round=False
            ),
            "manufacturing_warehouse": (
                pt.warehouse_id.code if pt and pt.warehouse_id else None
            ),
            "operation_count": len(b.operation_ids)
                if "operation_ids" in b._fields else None,
        })
    for line in all_published[:12]:
        print("SOURCE_PUBLISHED_PLANNING_REFERENCE:", {
            "sku": code,
            "line_id": line.id,
            "date": str(line.planning_id.delivery_date),
            "slot": line.planning_id.slot,
            "max_capacity": line.max_capacity,
        })
    moves = Move.search([
        ("company_id", "=", company.id),
        ("product_id", "=", p.id),
        ("state", "=", "done"),
    ], order="date desc, id desc", limit=8)
    print("SOURCE_NATIVE_STOCK_MOVES_DONE_COUNT_SAMPLE:", code, len(moves))
    for mv in moves:
        print("SOURCE_NATIVE_MOVE_HISTORY:", {
            "sku": code, "move_id": mv.id,
            "date": str(mv.date),
            "reference": mv.reference if "reference" in mv._fields
                         else mv.origin if "origin" in mv._fields
                         else "",
            "source": mv.location_id.complete_name,
            "source_usage": mv.location_id.usage,
            "destination": mv.location_dest_id.complete_name,
            "destination_usage": mv.location_dest_id.usage,
            "quantity_done_uom": mv.quantity,
            "picking_id": mv.picking_id.id,
        })
    if code == "11790":
        assert p.categ_id.complete_name == "All / Konsinyasi Masuk", (
            "STOP_11790_NOT_CONSIGNMENT_ANYMORE"
        )
        if all_published:
            print("CONSIGNMENT_11790_HAS_PUBLISHED_ROUTE_REVIEW_REQUIRED")
        else:
            print("CONSIGNMENT_11790_DO_NOT_CREATE_NATIVE_KITCHEN_MO")
    if pck_physical - pck_reserved < expected["qty"]:
        print("PCK_COMPONENT_OR_EXTERNAL_STOCK_SHORTFALL:", code,
              expected["qty"]-(pck_physical-pck_reserved))
print("IMPORTANT: External goods and packaging require real provenance;")
print("native Inventory Adjustment 10x in CDC is ONLY a rollback test seed")
print("for kitchen RAW material shortages, not a replacement for receipts.")
print("READ_ONLY_OWNER_EXTERNAL_STOCK_SOURCE_AUDIT_COMPLETE")
print("NO_CONSIGNMENT_RECEIPT_PACKAGING_PCK_STOCK_OR_MO_MUTATION")
env.cr.rollback()
