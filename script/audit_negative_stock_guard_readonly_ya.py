"""YA Odoo19 TEST READ ONLY: negative stock protection readiness.

Run via odoo-bin shell on erp-yussyakmal-mrp-test only.
NO stock validation, adjustment, MO completion, creation, write, or commit.
Checks installed modules, OCA quant guard registry, exemptions, legacy
negative quants, and real warehouse locations. This is NOT an install script.
"""
assert env.cr.dbname == "erp-yussyakmal-mrp-test", "REFUSED: WRONG DATABASE"
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_NEGATIVE_STOCK_GUARD_AUDIT")

Module = env["ir.module.module"].sudo()
Quant = env["stock.quant"].sudo()
Product = env["product.product"].sudo()
Category = env["product.category"].sudo()
Location = env["stock.location"].sudo()
Warehouse = env["stock.warehouse"].sudo()

target = Module.search([("name", "=", "stock_no_negative")], limit=2)
assert len(target) <= 1, "Ambiguous stock_no_negative module registry records"
print("OCA_STOCK_NO_NEGATIVE_REGISTRY:", (
    target.state if target else "NOT_IN_MODULE_REGISTRY"))
print("OCA_STOCK_NO_NEGATIVE_INSTALLED_VERSION:", (
    target.installed_version if target else "NOT_INSTALLED"))
print("OCA_STOCK_NO_NEGATIVE_LATEST_VERSION:", (
    target.latest_version if target else "NOT_IN_REGISTRY"))

other = Module.search([
    "|", "|",
    ("name", "ilike", "no_negative"),
    ("name", "ilike", "prevent_negative"),
    ("name", "ilike", "restrict_negative"),
], order="name")
print("NEGATIVE_STOCK_CANDIDATE_MODULES:", [
    (m.name, m.state, m.installed_version) for m in other
])

def field_present(model, name):
    return name in model._fields

print("NEGATIVE_STOCK_REGISTRY_FLAGS:",
      "product", field_present(Product, "allow_negative_stock"),
      "category", field_present(Category, "allow_negative_stock"),
      "location", field_present(Location, "allow_negative_stock"),
      "quant_validator", callable(getattr(Quant, "check_negative_qty", None)))

# OCA stock_no_negative 19: product/category/location-level exemptions.
# Never set these; just identify any existing exemptions on actual records.
for code in ("CDC", "PST", "ROTI", "PCK"):
    records = Warehouse.search([("code", "=", code)], limit=2)
    assert len(records) <= 1, "Warehouse code not unique: "+code
    if records:
        wh = records[0]
        loc = wh.lot_stock_id
        print("WAREHOUSE_NEGATIVE_POLICY:", code,
              "warehouse_id:", wh.id,
              "stock_location:", loc.complete_name,
              "location_usage:", loc.usage,
              "allow_negative_stock:", (
                  loc.allow_negative_stock
                  if field_present(Location, "allow_negative_stock")
                  else "FIELD_ABSENT"))

for code in ("11999", "12014", "12019", "12114"):
    products = Product.search([("default_code", "=", code)], limit=2)
    assert len(products) <= 1, "Product code not unique: "+code
    if products:
        p = products[0]
        print("SKU_NEGATIVE_POLICY:", code,
              "product_type:", p.type,
              "is_storable:", p.is_storable,
              "allow_on_product:", (
                  p.allow_negative_stock
                  if field_present(Product, "allow_negative_stock")
                  else "FIELD_ABSENT"),
              "allow_on_category:", (
                  p.categ_id.allow_negative_stock
                  if field_present(Category, "allow_negative_stock")
                  else "FIELD_ABSENT"))

negative_domain = [
    ("quantity", "<", -0.000001),
    ("location_id.usage", "in", ["internal", "transit"]),
    ("product_id.is_storable", "=", True),
]
negative_count = Quant.search_count(negative_domain)
print("EXISTING_NEGATIVE_INTERNAL_TRANSIT_QUANT_COUNT:", negative_count)
for q in Quant.search(negative_domain, limit=15, order="id"):
    print("EXISTING_NEGATIVE_QUANT_EXAMPLE:",
          "SKU:", q.product_id.default_code,
          "LOCATION:", q.location_id.complete_name,
          "QTY:", q.quantity,
          "RESERVED:", q.reserved_quantity)
if negative_count:
    print("CAUTION: Existing negative quants require investigation before "
          "introducing or enforcing a negative stock constraint.")

installed = bool(target and target.state == "installed")
guard_method = callable(getattr(Quant, "check_negative_qty", None))
flags = all([
    field_present(Product, "allow_negative_stock"),
    field_present(Category, "allow_negative_stock"),
    field_present(Location, "allow_negative_stock"),
])
if installed and guard_method and flags:
    print("GUARD_READINESS: OCA_MODULE_INSTALLED_REGISTRY_PRESENT")
    print("NOTE: Flags or exclusions can still permit negative stocks; "
          "inspect above values before any enforcement claim.")
elif installed:
    print("GUARD_READINESS: OCA_MODULE_INSTALLED_BUT_REGISTRY_INCONSISTENT")
else:
    print("GUARD_READINESS: OCA_MODULE_NOT_INSTALLED_OR_NOT_DISCOVERED")
    print("NOTE: This audit cannot exclude unrelated custom overrides "
          "or database automations; it checks the named OCA guard.")
print("READ_ONLY_NEGATIVE_STOCK_GUARD_AUDIT_OK")
