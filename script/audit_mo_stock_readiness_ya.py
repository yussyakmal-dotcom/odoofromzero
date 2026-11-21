"""YA Manufacturing Order stage 2: READ-ONLY stock/routing readiness.

No MO creation, stock transfers, reservation, or changes.
Targets BOM12499 on dedicated Manufacturing test database.
"""
from collections import defaultdict

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "Incorrect database"
bom = env["mrp.bom"].sudo().search([("code", "=", "BOM12499")], limit=2)
assert len(bom) == 1, "BoM BOM12499 missing or ambiguous"
print("DATABASE:", env.cr.dbname)
print("MODE: READ-ONLY MO STOCK READINESS")
print("BOM:", bom.code, "SKU:", bom.product_id.default_code, "BATCH:", bom.product_qty,
      "UOM:", bom.product_uom_id.name, "COMPONENT_LINES:", len(bom.bom_line_ids))

pt = bom.picking_type_id
assert pt and pt.code == "mrp_operation", "BoM manufacturing picking type missing"
print("PICKING TYPE:", pt.id, pt.display_name)
if pt.warehouse_id:
    print("WAREHOUSE:", pt.warehouse_id.display_name)
for field in [
    "default_location_src_id", "default_location_dest_id",
    "warehouse_id", "auto_print_mrp_reception_report", "reservation_method"
]:
    if field in pt._fields:
        val = pt[field]
        print("PICKING FIELD:", field, "=", val.display_name if hasattr(val, "display_name") else val)

location = env["stock.location"].sudo().with_context(active_test=False)
print("=== RELATED LOCATIONS ===")
related = location.search([
    "|", ("complete_name", "ilike", "TART"), ("complete_name", "ilike", "Production")
], order="complete_name")
for loc in related:
    print("LOCATION:", loc.id, repr(loc.complete_name),
          "USAGE:", loc.usage, "ACTIVE:", loc.active)

print("=== COMPONENT STOCK BY LOCATION ===")
quant_model = env["stock.quant"].sudo()
requirements = defaultdict(float)
for line in bom.bom_line_ids:
    # Product quantity is in the line's UoM; convert to base UoM for comparison.
    base_quantity = line.product_uom_id._compute_quantity(
        line.product_qty, line.product_id.uom_id, raise_if_failure=True
    )
    requirements[line.product_id.id] += base_quantity

product_model = env["product.product"].sudo()
products = {p.id: p for p in product_model.browse(list(requirements))}
loc_ids = [loc.id for loc in related if loc.usage == "internal"]
if not loc_ids:
    print("WARNING: No internal TART/Production locations identified")
quants = quant_model.search([
    ("product_id", "in", list(requirements)),
    ("location_id", "in", loc_ids or [-1]),
])
stock_by_key = defaultdict(float)
reserved_by_key = defaultdict(float)
for quant in quants:
    key = (quant.product_id.id, quant.location_id.complete_name)
    stock_by_key[key] += quant.quantity
    if "reserved_quantity" in quant._fields:
        reserved_by_key[key] += quant.reserved_quantity

def sku(product):
    return product.default_code or str(product.id)

for product_id in sorted(requirements, key=lambda i: sku(products[i])):
    product = products[product_id]
    qty = requirements[product_id]
    print("NEEDED:", sku(product), "QTY_BASE:", qty, "UOM:", product.uom_id.name)
    entries = sorted(
        ((name, stock_by_key[(product_id, name)], reserved_by_key[(product_id, name)])
         for (pid, name) in stock_by_key if pid == product_id),
        key=lambda entry: entry[0]
    )
    if not entries:
        print("  LOCATION STOCK: none in listed related locations")
    for name, available, reserved in entries:
        print("  LOCATION:", name, "ON_HAND:", available, "RESERVED:", reserved)

print("=== STOCK POLICY SIGNALS ===")
for module_name in ["stock", "mrp", "ya_integer_quantity"]:
    mod = env["ir.module.module"].sudo().search([("name", "=", module_name)], limit=1)
    print("MODULE:", module_name, mod.state if mod else "missing")
print("NOTE: This audit does NOT prove enforcement of no-negative-stock policy.")
print("NOTE: A physical stock reservation/done test is still required with rollback.")
print("MO_STOCK_READINESS_AUDIT_OK no data changed")
