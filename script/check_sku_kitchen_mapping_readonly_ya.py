"""Narrow read-only SKU -> kitchen mapping check for Odoo 19 Community.
Odoo shell target: erp-yussyakmal-mrp-test ONLY.
No create/write/unlink/commit, no stock movements, no changes.
Inspect finished-product BoM -> Manufacturing Operation Type -> warehouse.
Only report counts, exceptions and a few samples.
"""
from collections import Counter, defaultdict

EXPECTED_DB = "erp-yussyakmal-mrp-test"
assert env.cr.dbname == EXPECTED_DB, "REFUSED WRONG DATABASE: %s" % env.cr.dbname

B = env["mrp.bom"].sudo().with_context(active_test=False)
P = env["product.product"].sudo().with_context(active_test=False)

print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_SKU_KITCHEN_MAPPING")
print("BOM_TOTAL:", B.search_count([]))

def field(model, name):
    f = model._fields.get(name)
    return ("absent" if not f else f.type + (":" + str(f.comodel_name) if getattr(f, "comodel_name", None) else ""))

for model, names in [
    (B, ("product_id", "product_tmpl_id", "picking_type_id", "company_id", "active", "type")),
    (env["stock.picking.type"], ("warehouse_id", "code", "default_location_src_id", "default_location_dest_id")),
    (P, ("default_code", "product_tmpl_id", "route_ids", "property_stock_production")),
]:
    print("MODEL_FIELDS:", model._name, {n: field(model, n) for n in names})

rows = B.search([("type", "=", "normal")], order="id")
per_sku = defaultdict(set)
by_kitchen = Counter()
missing = []
template_level = []
samples = []

for bom in rows:
    prod = bom.product_id
    if not prod:
        template_level.append((bom.id, bom.product_tmpl_id.display_name))
        continue
    sku = prod.default_code or ""
    pt = bom.picking_type_id
    wh = pt.warehouse_id if pt and "warehouse_id" in pt._fields else False
    if not sku or not pt or not wh or pt.code != "mrp_operation":
        missing.append((bom.id, sku or "-", pt.display_name if pt else "-", wh.name if wh else "-"))
        continue
    per_sku[sku].add((wh.id, wh.name))
    by_kitchen[wh.name] += 1
    if len(samples) < 8:
        samples.append((sku, bom.code or "-", pt.display_name, wh.name))

ambiguous = sorted((sku, sorted(whs)) for sku, whs in per_sku.items() if len(whs) > 1)
print("MFG_BOMS:", len(rows))
print("MAPPED_SKUS:", len(per_sku))
print("MISSING_OR_INVALID_MAPPING_COUNT:", len(missing))
print("MISSING_SAMPLES_MAX_10:", missing[:10])
print("TEMPLATE_LEVEL_BOMS_COUNT:", len(template_level))
print("TEMPLATE_LEVEL_SAMPLES_MAX_10:", template_level[:10])
print("MULTI_KITCHEN_SKUS_COUNT:", len(ambiguous))
print("MULTI_KITCHEN_SAMPLES_MAX_10:", ambiguous[:10])
print("KITCHEN_BOM_COUNTS:", sorted(by_kitchen.items()))
print("MAPPING_SAMPLES_MAX_8:", samples)
print("CAVEAT: BoM mapping proves SKU -> manufacturing operation warehouse only if complete and unique; it does not independently prove current business ownership.")
print("READ_ONLY_MAPPING_CHECK_OK")
