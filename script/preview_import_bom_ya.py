"""Preview-only YA BoM import mapping; never writes Odoo data.

Private inputs:
  YA_BOM_HEADER_CSV, YA_BOM_COMPONENT_CSV
Run in Odoo shell on erp-yussyakmal-mrp-test.
CSV is NOT stored in this public repository.
"""
import csv
import os
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "Refusing non-MRP-test database"
assert os.environ.get("YA_APPLY") != "1", "PREVIEW ONLY; no APPLY support in this script"

def read_csv(name, expected):
    raw = os.environ.get(name, "")
    assert raw, f"{name} not supplied"
    path = Path(raw)
    assert path.is_file(), f"File unreadable: {path}"
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        assert set(expected) <= set(reader.fieldnames or []), (name, reader.fieldnames)
        return [{k: (v or "").strip() for k, v in row.items()} for row in reader]

headers = read_csv("YA_BOM_HEADER_CSV",
    ["BOM_CODE", "Product_code", "BoM Type", "Operation Type", "Quantity", "Unit"])
components = read_csv("YA_BOM_COMPONENT_CSV",
    ["Product/Internal Reference", "ID_COMPONENT", "QTY_COMPONENT", "UOM_COMPONENT"])
print("DATABASE:", env.cr.dbname)
print("MODE: PREVIEW ONLY (READ-ONLY)")
print("SOURCE HEADERS:", len(headers), "SOURCE COMPONENT LINES:", len(components))

problems = defaultdict(list)
def err(key, message):
    problems[key].append(str(message))

def integer_gt_zero(value, desc):
    try:
        number = Decimal(value)
        if not number.is_finite() or number <= 0 or number != number.to_integral_value():
            raise ValueError("not a positive integer")
        return int(number)
    except (InvalidOperation, ValueError):
        err("INVALID_QUANTITY", f"{desc}: {value!r}")
        return None

bom_codes = Counter(row["BOM_CODE"] for row in headers)
result_skus = Counter(row["Product_code"] for row in headers)
groups = Counter(row["Product/Internal Reference"] for row in components)
for label, counts in [("BOM_CODE", bom_codes), ("PRODUCT_SKU", result_skus)]:
    for key, amount in counts.items():
        if not key or amount != 1:
            err("DUPLICATE_OR_EMPTY_" + label, f"{key!r}: {amount}")
for sku, qty in groups.items():
    if sku not in result_skus:
        err("ORPHAN_COMPONENT_GROUP", f"{sku}: {qty} components")
for sku in result_skus:
    if not groups.get(sku):
        err("HEADER_WITHOUT_COMPONENT", sku)

for row in headers:
    integer_gt_zero(row["Quantity"], "Header " + row["BOM_CODE"])
    if row["BoM Type"] != "Manufacture this product":
        err("UNEXPECTED_BOM_TYPE", row["BOM_CODE"])
for number, line in enumerate(components, 2):
    integer_gt_zero(line["QTY_COMPONENT"], f"Component row {number}")
    if not line["ID_COMPONENT"]:
        err("EMPTY_COMPONENT_SKU", number)

product_codes = sorted(
    {h["Product_code"] for h in headers} |
    {c["ID_COMPONENT"] for c in components}
)
products = env["product.product"].sudo().with_context(active_test=False)
found = defaultdict(list)
for start in range(0, len(product_codes), 300):
    for product in products.search(
        [("default_code", "in", product_codes[start:start+300])]
    ):
        found[product.default_code].append(product)
for code in product_codes:
    if len(found[code]) != 1:
        err("SKU_NOT_UNIQUE_IN_ODOO", f"{code}: {len(found[code])}")

uom_model = env["uom.uom"].sudo().with_context(active_test=False)
units = defaultdict(list)
for unit in uom_model.search([]):
    units[unit.name.strip().casefold()].append(unit)

def resolve_unit(code, unit_label, context):
    possible = units.get(unit_label.casefold(), [])
    if len(possible) != 1:
        err("UOM_MISSING_OR_AMBIGUOUS", f"{context}: {unit_label!r}, count={len(possible)}")
        return
    p = found.get(code, [])
    if len(p) != 1:
        return
    try:
        result = possible[0]._compute_quantity(1, p[0].uom_id, raise_if_failure=True)
        if result <= 0:
            raise ValueError("non-positive conversion")
    except Exception as exc:
        err("UOM_NOT_CONVERTIBLE", f"{context} {code}: {unit_label} -> {p[0].uom_id.name}: {exc}")

for h in headers:
    resolve_unit(h["Product_code"], h["Unit"], "HEADER " + h["BOM_CODE"])
for number, line in enumerate(components, 2):
    resolve_unit(line["ID_COMPONENT"], line["UOM_COMPONENT"], f"COMPONENT row {number}")

# CSV: "Dapur Tart: Tart"; Odoo: "Dapur Tart: Manufacturing".
# Match the WAREHOUSE prefix, only among manufacturing types, with no fuzzy guesses.
picking_type_model = env["stock.picking.type"].sudo().with_context(active_test=False)
picking_types_by_warehouse = defaultdict(list)
for pt in picking_type_model.search([("code", "=", "mrp_operation")]):
    wh = pt.warehouse_id if "warehouse_id" in pt._fields else False
    if wh:
        picking_types_by_warehouse[wh.name.strip().casefold()].append(pt)

resolved_types = {}
for label in sorted({h["Operation Type"] for h in headers}):
    if ":" not in label:
        err("INVALID_OPERATION_TYPE_FORMAT", repr(label))
        continue
    wh_name = label.split(":", 1)[0].strip()
    matching = picking_types_by_warehouse.get(wh_name.casefold(), [])
    active = [pt for pt in matching if pt.active]
    if len(active) != 1:
        err("PICKING_TYPE_NOT_UNIQUE_OR_ACTIVE",
            f"{label!r} -> warehouse {wh_name!r}: active matching={len(active)}")
    else:
        resolved_types[label] = active[0]
        print("MAPPING:", repr(label), "=>",
              repr(active[0].display_name), "ID:", active[0].id)
for h in headers:
    if h["Operation Type"] not in resolved_types:
        err("HEADER_OPERATION_TYPE_UNRESOLVED", h["BOM_CODE"])

bom_model = env["mrp.bom"].sudo().with_context(active_test=False)
required_fields = ["product_tmpl_id", "product_id", "product_qty",
                   "product_uom_id", "type", "bom_line_ids", "picking_type_id", "code"]
for field in required_fields:
    if field not in bom_model._fields:
        err("MISSING_ODOO_BOM_FIELD", field)
line_model = env["mrp.bom.line"]
for field in ["product_id", "product_qty", "product_uom_id", "bom_id"]:
    if field not in line_model._fields:
        err("MISSING_ODOO_LINE_FIELD", field)
existing = bom_model.search_count([])
print("EXISTING BOMS:", existing)
if existing:
    err("EXISTING_BOM_REQUIRES_REVIEW", existing)

print("DISTINCT RESULT SKUS:", len(result_skus))
print("DISTINCT COMPONENT SKUS:", len({c["ID_COMPONENT"] for c in components}))
print("GROUPS WITH COMPONENTS:", len(groups))
print("CSV OPERATION TYPE LABELS:", len({h["Operation Type"] for h in headers}))
print("RESOLVED OPERATION TYPES:", len(resolved_types))
print("ISSUE SUMMARY:")
for category in sorted(problems):
    print(" ", category, "=", len(problems[category]))
    for example in problems[category][:15]:
        print("   -", example)
if problems:
    print("BOM_IMPORT_PREVIEW_BLOCKED (NO CHANGES MADE)")
else:
    print("BOM_IMPORT_PREVIEW_OK (NO CHANGES MADE)")
