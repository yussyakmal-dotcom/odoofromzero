"""READ-ONLY audit: every YA BoM component line's UoM vs product master UoM.

Runs via odoo-bin shell on the dedicated MRP test database. No ORM writes.
Outputs all DIFFERENT or UNRESOLVED rows, plus summary. Captures actual
Odoo conversion factors, but conversion success alone does NOT mean the
unit definitions are semantically correct (e.g. Gram vs Pcs).
"""
from collections import Counter, defaultdict
from decimal import Decimal

DB = "erp-yussyakmal-mrp-test"
assert env.cr.dbname == DB, "Refusing non-MRP-test database"

Bom = env["mrp.bom"].sudo().with_context(active_test=False)
Line = env["mrp.bom.line"].sudo().with_context(active_test=False)
assert Bom.search_count([]) == 955, "Unexpected BoM count"
assert Line.search_count([]) == 8502, "Unexpected component line count"

print("DATABASE:", env.cr.dbname)
print("MODE: READ-ONLY COMPONENT UOM VS MASTER")
print("EXPECTED BOM:", 955, "EXPECTED COMPONENTS:", 8502)

# We classify more strictly than the ORM's _compute_quantity validation.
# Unit names are NOT used for conversion; native UoM method calculates
# the mathematical result, which is shown for every differing UoM.
def unit_family(value):
    n = str(value).strip().casefold().replace(".", "").replace(" ", "")
    if n in {"gram", "gr", "g", "kg", "kilogram", "mg", "miligram"}:
        return "MASS"
    if n in {"ml", "milliliter", "millilitre", "l", "liter", "litre", "cc"}:
        return "VOLUME"
    if n in {"pcs", "pc", "piece", "pieces", "butir", "buah", "botol", "paket", "lembar", "ikat", "toples"}:
        return "COUNT"
    if n in {"resep", "batch"}:
        return "RECIPE"
    return "OTHER"

tally = Counter()
diff_skus = defaultdict(set)
warnings = []
print("=== DIFFERENT / UNRESOLVED COMPONENT LINES ===")
for line in Line.search([], order="bom_id, sequence, id"):
    product = line.product_id
    uom = line.product_uom_id
    master = product.uom_id
    sku = product.default_code or f"ID:{product.id}"
    bom = line.bom_id.code or f"ID:{line.bom_id.id}"
    quantity = line.product_qty
    if not product or not uom or not master:
        kind = "MISSING_REFERENCE"
        converted = "N/A"
    elif uom.id == master.id:
        tally["EXACT"] += 1
        continue
    else:
        try:
            value = uom._compute_quantity(quantity, master, raise_if_failure=True)
            converted = str(value)
            if value <= 0:
                kind = "NONPOSITIVE_CONVERSION"
            elif unit_family(uom.name) != unit_family(master.name) and (
                "OTHER" not in (unit_family(uom.name), unit_family(master.name))
            ):
                kind = "CROSS_FAMILY_REVIEW"
            elif abs(value - quantity) < 1e-9:
                kind = "DIFFERENT_UOM_1_TO_1"
            else:
                kind = "DIFFERENT_UOM_CONVERSION"
        except Exception as exc:
            kind = "CONVERSION_FAILED"
            converted = f"{type(exc).__name__}: {exc}"
    tally[kind] += 1
    diff_skus[sku].add(kind)
    print(
        f"{kind} | BOM={bom} | SKU={sku} | {product.name} | "
        f"BOM_QTY={quantity} {uom.name if uom else '?'} (UOM_ID={uom.id if uom else '?'}) | "
        f"MASTER_UOM={master.name if master else '?'} (UOM_ID={master.id if master else '?'}) | "
        f"BASE_QTY={converted}"
    )

print("=== SUMMARY ===")
print("TOTAL_LINES:", sum(tally.values()))
print("EXACT_LINES:", tally["EXACT"])
print("DIFFERENT_LINES:", sum(v for k, v in tally.items() if k != "EXACT"))
print("DIFFERENT_SKUS:", len(diff_skus))
for key in sorted(tally):
    print("CLASS:", key, "COUNT:", tally[key])
print("=== DISTINCT SKU WITH DIFFERENCES ===")
for sku in sorted(diff_skus):
    print("SKU:", sku, "CLASSES:", ",".join(sorted(diff_skus[sku])))
print("=== FOCUS SKU 11055 ===")
p = env["product.product"].sudo().with_context(active_test=False).search(
    [("default_code", "=", "11055")]
)
print("SKU_11055_PRODUCT_COUNT:", len(p))
for item in p:
    print("SKU_11055_MASTER:", item.id, item.name, item.uom_id.name, item.uom_id.id)
    for line in Line.search([("product_id", "=", item.id)], order="bom_id, id"):
        print("SKU_11055_BOM:", line.bom_id.code, "QTY:", line.product_qty,
              "BOM_UOM:", line.product_uom_id.name, "BASE_UOM:", item.uom_id.name)
print("NOTE: Even if conversion succeeds, cross-family/1:1 mappings need business review.")
print("COMPONENT_UOM_MASTER_AUDIT_OK: no database changes")
