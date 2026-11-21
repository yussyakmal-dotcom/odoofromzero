"""Read-only diagnostic of BoM component UoM and no-negative-stock signals.

Run in Odoo shell on erp-yussyakmal-mrp-test. No create/write/commit.
Specifically checks SKU 11055 in BOM12499 and other components.
"""
from collections import defaultdict

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "Refusing other DB"
B = env["mrp.bom"].sudo()
boms = B.search([("code", "=", "BOM12499")], limit=2)
assert len(boms) == 1, "Expected one BOM12499"
bom = boms[0]
print("DATABASE:", env.cr.dbname, "| MODE: READ-ONLY UOM AND STOCK POLICY")
print("BOM:", bom.code, "BATCH:", bom.product_qty, bom.product_uom_id.name)
print("=== COMPONENT UOM AND CONVERSIONS ===")
for line in bom.bom_line_ids.sorted(key=lambda rec: (rec.sequence, rec.id)):
    p = line.product_id
    src = line.product_uom_id
    base = p.uom_id
    try:
        converted = src._compute_quantity(line.product_qty, base, raise_if_failure=True)
        status = "MATCH" if src.id == base.id else "DIFF"
    except Exception as exc:
        converted = "ERROR: " + str(exc)
        status = "ERROR"
    print(
        "SKU:", p.default_code,
        "| PRODUCT:", p.display_name,
        "| BOM_QTY:", line.product_qty,
        "| BOM_UOM:", src.name, f"(id={src.id})",
        "| PRODUCT_UOM:", base.name, f"(id={base.id})",
        "| CONVERTED_QTY:", converted,
        "| STATUS:", status,
    )
print("=== FOCUS SKU 11055 ===")
target = env["product.product"].sudo().search([("default_code", "=", "11055")])
print("PRODUCT_RECORD_COUNT:", len(target))
for p in target:
    print("SKU:", p.default_code, "NAME:", p.display_name,
          "UOM:", p.uom_id.name, "UOM_ID:", p.uom_id.id,
          "PRODUCT_TYPE:", p.type if "type" in p._fields else "NOT AVAILABLE")
print("=== AVAILABLE UOMS WITH GRAM OR PCS IN NAME ===")
for u in env["uom.uom"].sudo().with_context(active_test=False).search([]):
    if any(token in u.name.casefold() for token in ("gram", "pcs", "piece")):
        print("UOM:", u.id, repr(u.name),
              "FIELDS:", {key: u[key] for key in ("factor", "relative_factor") if key in u._fields})
print("=== NEGATIVE STOCK MODULE SIGNALS ===")
mods = env["ir.module.module"].sudo().search([
    "|", ("name", "ilike", "negative"), ("name", "ilike", "stock")
])
for m in mods:
    if "negative" in m.name.lower() or m.name in ("stock", "stock_account"):
        print("MODULE:", m.name, "STATE:", m.state)
print("NOTE: Presence/absence of modules is NOT proof negative stock is forbidden.")
print("UOM_STOCK_POLICY_DIAGNOSTIC_OK no changes made")
