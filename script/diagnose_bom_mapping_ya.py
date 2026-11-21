"""READ-ONLY diagnostic for YA BoM picking type and UoM name mismatches.

Run in Odoo shell on MRP test database. Uses private CSV files from env.
Prints the actual Odoo master records and all unresolved CSV unit names.
Never writes/commits any data.
"""
import csv
import os
from collections import Counter, defaultdict
from pathlib import Path

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "Wrong database"

def load(path, columns):
    file = Path(os.environ.get(path, ""))
    assert file.is_file(), f"Missing file path in {path}"
    with file.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        assert set(columns).issubset(reader.fieldnames or []), f"Bad headers in {file.name}"
        return list(reader)

headers = load("YA_BOM_HEADER_CSV", ["BOM_CODE", "Product_code", "Unit", "Operation Type"])
lines = load("YA_BOM_COMPONENT_CSV", ["ID_COMPONENT", "UOM_COMPONENT"])
print("DATABASE:", env.cr.dbname, "MODE: READ-ONLY")
print("=== ALL MRP PICKING TYPES ===")
model = env["stock.picking.type"].sudo().with_context(active_test=False)
types = model.search([("code", "=", "mrp_operation")], order="id")
for item in types:
    warehouse = item.warehouse_id if "warehouse_id" in item._fields else False
    print("ID:", item.id, "| NAME:", repr(item.name),
          "| DISPLAY:", repr(item.display_name),
          "| WAREHOUSE:", repr(warehouse.name if warehouse else None),
          "| ACTIVE:", item.active if "active" in item._fields else "?")
print("=== DISTINCT CSV OPERATION TYPES ===")
csv_ops = Counter(r["Operation Type"].strip() for r in headers)
for name, count in sorted(csv_ops.items()):
    print(repr(name), "| ROWS:", count)
print("=== UNMATCHED UOM LABELS ===")
uom = env["uom.uom"].sudo().with_context(active_test=False)
known = defaultdict(list)
for u in uom.search([]):
    known[str(u.name).strip().casefold()].append(u)
sku_set = {r["Product_code"].strip() for r in headers if r["Product_code"].strip()}
sku_set.update(r["ID_COMPONENT"].strip() for r in lines if r["ID_COMPONENT"].strip())
products = env["product.product"].sudo().with_context(active_test=False)
by_sku = {}
for start in range(0, len(sku_set), 300):
    for p in products.search([("default_code", "in", sorted(sku_set)[start:start+300])]):
        by_sku[p.default_code] = p
missing = Counter()
examples = defaultdict(list)
for label, rows, sku_field, label_field in [
    ("header", headers, "Product_code", "Unit"),
    ("component", lines, "ID_COMPONENT", "UOM_COMPONENT"),
]:
    for r in rows:
        txt = r[label_field].strip()
        if txt.casefold() not in known:
            missing[(label, txt)] += 1
            if len(examples[(label, txt)]) < 12:
                sku = r[sku_field].strip()
                p = by_sku.get(sku)
                examples[(label, txt)].append(
                    (sku, p.uom_id.name if p else "SKU NOT FOUND")
                )
for (kind, name), count in sorted(missing.items()):
    print("MISSING:", kind, repr(name), "| COUNT:", count,
          "| SKU_BASE_UOM_EXAMPLES:", examples[(kind, name)])
print("MISSING_TOTAL:", sum(missing.values()))
print("=== AVAILABLE UOM NAMES ===")
for u in uom.search([], order="name"):
    print("UOM:", u.id, repr(u.name))
print("BOM_MAPPING_DIAGNOSTIC_OK no changes made")
