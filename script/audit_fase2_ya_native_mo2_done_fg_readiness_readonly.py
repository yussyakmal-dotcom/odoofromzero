"""Read-only preflight for NATIVE (not simulated) MO2 Done -> PCK QA.

RO_SO clone only. Find required Odoo 19 manufacturing methods, warehouse
stock and inventory constraints for a controlled rollback-only test of:
  native CDC picking Done -> actual MO2 Done -> native FG picking Draft.
No creates, inventory adjustments, writes, workflow calls or commits here.
Never claim this preflight proves MO2 Done or FG picking validation.
"""
from collections import defaultdict

DB = "erp-yussyakmal-mrp-test-RO_SO"
assert env.cr.dbname == DB, "STOP_WRONG_DATABASE"

Module = env["ir.module.module"].sudo().search([
    ("name", "=", "ya_sale_production_capacity"),
], limit=1)
assert Module and Module.state == "installed" and (
    Module.installed_version == "19.0.1.1.3"
), "STOP_FG_NATIVE_ADDON_NOT_INSTALLED_1_1_3"

MO = env["mrp.production"]
Move = env["stock.move"]
Picking = env["stock.picking"]
Planning = env["ya.production.planning.line"].sudo()
Quant = env["stock.quant"].sudo()
Warehouse = env["stock.warehouse"].sudo()
Release = env["ya.sale.mo2.release.line"].sudo()

print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_NATIVE_MO2_DONE_FG_ROLLBACK_READINESS")
print("INSTALLED_YA_SO_VERSION:", Module.installed_version)

method_names = (
    "action_confirm", "button_mark_done", "button_plan",
    "action_assign", "action_cancel",
)
print("MRP_NATIVE_METHODS:", {
    name: callable(getattr(MO, name, None))
    for name in method_names
})
print("MRP_FIELDS:", {
    key: (MO._fields[key].type if key in MO._fields else "MISSING")
    for key in (
        "state", "product_qty", "qty_producing", "product_uom_id",
        "move_raw_ids", "move_finished_ids", "lot_producing_id",
        "workorder_ids", "is_planned",
    )
})
print("MOVE_FIELDS:", {
    key: (Move._fields[key].type if key in Move._fields else "MISSING")
    for key in (
        "state", "quantity", "product_uom_qty", "product_uom",
        "move_line_ids", "location_id", "location_dest_id",
        "is_picked", "picked",
    )
})
print("PICKING_METHODS:", {
    name: callable(getattr(Picking, name, None))
    for name in ("action_confirm", "button_validate", "action_assign")
})

sample = Planning.browse(3162).exists()
assert sample and sample.planning_id.state == "published", (
    "STOP_REFERENCE_PUBLISHED_LINE_3162_CHANGED"
)
assert sample.product_id.id == 1584, "STOP_REFERENCE_SKU_CHANGED"
bom = sample._capacity_bom()
assert bom.id == 1154 and bom.type == "normal", (
    "STOP_REFERENCE_BOM_CHANGED"
)
company = bom.picking_type_id.company_id
kitchen = bom.picking_type_id.warehouse_id
CDC = Warehouse.search([
    ("code", "=", "CDC"), ("company_id", "=", company.id),
])
PCK = Warehouse.search([
    ("code", "=", "PCK"), ("company_id", "=", company.id),
])
assert len(CDC) == len(PCK) == 1 and kitchen and (
    kitchen.company_id == company
) and len({CDC.id, PCK.id, kitchen.id}) == 3, (
    "STOP_REFERENCE_WAREHOUSES_INVALID"
)
assert all(x.lot_stock_id and x.lot_stock_id.usage == "internal"
           for x in (CDC, PCK, kitchen)), "STOP_STOCK_LOCATION_INVALID"
print("TEMPLATE:", {
    "plan_line": sample.id,
    "product_id": sample.product_id.id,
    "product_code": sample.product_id.default_code,
    "product_uom": sample.product_id.uom_id.name,
    "product_tracking": sample.product_id.tracking,
    "bom_id": bom.id,
    "bom_output": bom.product_qty,
    "published_max": sample.max_capacity,
    "kitchen": kitchen.code,
    "company_id": company.id,
    "cdc": CDC.code,
    "packing": PCK.code,
    "warehouse_native_internal_transfer": bool(
        kitchen.int_type_id and kitchen.int_type_id.code == "internal"
    ),
})
assert sample.product_id.tracking == "none", (
    "STOP_TRACKED_REFERENCE_PRODUCT"
)

def exact_stock(location, product):
    quants = Quant.search([
        ("product_id", "=", product.id),
        ("location_id", "=", location.id),
        ("company_id", "=", company.id),
        ("lot_id", "=", False), ("package_id", "=", False),
        ("owner_id", "=", False),
    ])
    return (
        sum(quants.mapped("quantity")),
        sum(quants.mapped("reserved_quantity")),
    )

bom_materials = defaultdict(float)
products = {}
for line in bom.bom_line_ids:
    product = line.product_id
    if not product:
        continue
    qty = line.product_uom_id._compute_quantity(
        line.product_qty, product.uom_id, round=False
    )
    if qty <= 0:
        continue
    bom_materials[product.id] += qty
    products[product.id] = product
assert bom_materials, "STOP_BOM_HAS_NO_RAW_MATERIALS"
for pid, qty in sorted(bom_materials.items()):
    p = products[pid]
    cdc_onhand, cdc_reserved = exact_stock(CDC.lot_stock_id, p)
    kitchen_onhand, kitchen_reserved = exact_stock(kitchen.lot_stock_id, p)
    print("RAW_BOM_MATERIAL:", {
        "product_id": pid, "code": p.default_code,
        "bom_line_qty_base": qty, "base_uom": p.uom_id.name,
        "tracking": p.tracking,
        "cdc_physical": cdc_onhand, "cdc_reserved": cdc_reserved,
        "cdc_free": cdc_onhand - cdc_reserved,
        "kitchen_physical": kitchen_onhand,
        "kitchen_reserved": kitchen_reserved,
        "kitchen_free": kitchen_onhand - kitchen_reserved,
    })
fg_stock, fg_reserved = exact_stock(kitchen.lot_stock_id, sample.product_id)
print("FG_REFERENCE_KITCHEN_NOW:", {
    "physical": fg_stock,
    "reserved": fg_reserved,
    "free": fg_stock - fg_reserved,
})
print("PERSISTED_MO2_LINES:", Release.search_count([]))

assert callable(getattr(MO, "button_mark_done", None)), (
    "STOP_NATIVE_MO_DONE_METHOD_UNAVAILABLE; inspect Odoo 19 API first"
)
assert callable(getattr(Picking, "button_validate", None)), (
    "STOP_NATIVE_PICKING_VALIDATION_UNAVAILABLE"
)
assert all(key in Move._fields for key in (
    "quantity", "product_uom_qty", "product_uom", "state"
)), "STOP_NATIVE_MOVE_QUANTITY_SCHEMA_MISSING"

print("QA_DESIGN_RULE: no fake DONE state, no fake finished moves.")
print("QA_DESIGN_RULE: ONLY native Odoo MO/button_mark_done, inside rollback.")
print("QA_DESIGN_RULE: real CDC picking must be fulfilled or test STOP.")
print("QA_DESIGN_RULE: native FG draft must read DONE MO2 output and exact kitchen free stock.")
print("QA_DESIGN_RULE: test transaction rollback must include stock and valuation changes.")
print("READ_ONLY_NATIVE_MO2_DONE_FG_READINESS_PASS")
print("NO_MO_CDC_STOCK_OR_PICKING_MUTATION")
