"""READ-ONLY validation of private YA BoM header and component CSV files.

Runs inside Odoo 19 shell with env available. Does not create, write or commit.
Inputs are private and deliberately not committed to public Git.
"""
import csv
import os
from collections import Counter, defaultdict
from pathlib import Path

EXPECTED_DB = "erp-yussyakmal-mrp-test"
assert env.cr.dbname == EXPECTED_DB, "Wrong database; refusing audit"
header_path = Path(os.environ.get("YA_BOM_HEADER_CSV", ""))
component_path = Path(os.environ.get("YA_BOM_COMPONENT_CSV", ""))
assert header_path.is_file() and component_path.is_file(), "CSV files not readable"

def load(path, expected):
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        rd = csv.DictReader(fh)
        assert set(expected) <= set(rd.fieldnames or []), f"{path.name}: bad columns {rd.fieldnames}"
        return [{k: (v or "").strip() for k, v in row.items()} for row in rd]

H = load(header_path, ["BOM_CODE", "Product_code", "Quantity", "Unit", "Operation Type"])
C = load(component_path, [
    "Product/Internal Reference", "ID_COMPONENT", "QTY_COMPONENT", "UOM_COMPONENT"
])
print("DATABASE:", env.cr.dbname, "| MODE: READ-ONLY")
print("HEADER_ROWS:", len(H), "COMPONENT_ROWS:", len(C))

errors = defaultdict(list)
def issue(kind, msg):
    errors[kind].append(msg)

def positive_integer(value):
    try:
        from decimal import Decimal
        d = Decimal(value)
        return d > 0 and d == d.to_integral_value()
    except Exception:
        return False

h_codes = Counter(x["BOM_CODE"] for x in H)
h_skus = Counter(x["Product_code"] for x in H)
c_skus = Counter(x["Product/Internal Reference"] for x in C)
for key, count in h_codes.items():
    if not key or count != 1:
        issue("BOM_CODE_DUPLICATE_OR_BLANK", f"{key!r}: {count}")
for key, count in h_skus.items():
    if not key or count != 1:
        issue("HEADER_SKU_DUPLICATE_OR_BLANK", f"{key!r}: {count}")
for row in H:
    if not positive_integer(row["Quantity"]):
        issue("INVALID_HEADER_QTY", f'{row["BOM_CODE"]}: {row["Quantity"]!r}')
    if row.get("BoM Type") != "Manufacture this product":
        issue("UNEXPECTED_BOM_TYPE", f'{row["BOM_CODE"]}: {row.get("BoM Type")}')
    if not row["Operation Type"]:
        issue("EMPTY_OPERATION_TYPE", row["BOM_CODE"])
for key in set(c_skus) - set(h_skus):
    issue("COMPONENT_GROUP_WITHOUT_HEADER", key)
for key in set(h_skus) - set(c_skus):
    issue("HEADER_WITHOUT_COMPONENT_GROUP", key)
for i, row in enumerate(C, 2):
    if not row["ID_COMPONENT"] or not row["Product/Internal Reference"]:
        issue("EMPTY_SKU", f"component CSV row {i}")
    if not positive_integer(row["QTY_COMPONENT"]):
        issue("INVALID_COMPONENT_QTY", f'row {i}: {row["QTY_COMPONENT"]!r}')

product_codes = sorted(
    {row["Product_code"] for row in H} |
    {row["ID_COMPONENT"] for row in C}
)
P = env["product.product"].sudo().with_context(active_test=False)
product_map = defaultdict(list)
# Chunk to prevent oversized PostgreSQL parameter arrays.
for offset in range(0, len(product_codes), 300):
    for product in P.search([("default_code", "in", product_codes[offset:offset+300])]):
        product_map[product.default_code].append(product)
for code in product_codes:
    if len(product_map[code]) != 1:
        issue("SKU_MISSING_OR_AMBIGUOUS", f"{code}: {len(product_map[code])} product records")

U = env["uom.uom"].sudo().with_context(active_test=False)
units = U.search([])
uom_map = defaultdict(list)
for unit in units:
    uom_map[unit.name.strip().casefold()].append(unit)
def check_uom(code, unit_name, context):
    candidates = uom_map.get(unit_name.strip().casefold(), [])
    if not candidates:
        issue("UOM_NAME_NOT_FOUND", f"{context}: {unit_name!r}")
        return
    if len(candidates) != 1:
        issue("UOM_NAME_AMBIGUOUS", f"{context}: {unit_name!r}, found {len(candidates)}")
        return
    products = product_map.get(code, [])
    if len(products) != 1:
        return
    # Odoo 19 may not expose uom.uom.category_id. The native conversion
    # method validates whether source and product UoMs are compatible.
    source_uom = candidates[0]
    target_uom = products[0].uom_id
    try:
        converted = source_uom._compute_quantity(1, target_uom, raise_if_failure=True)
        if converted <= 0:
            issue(
                "UOM_CONVERSION_NONPOSITIVE",
                f"{context}: SKU {code}, {unit_name} -> {target_uom.name}: {converted}"
            )
    except Exception as exc:
        issue(
            "UOM_CONVERSION_FAILED",
            f"{context}: SKU {code}, {unit_name} -> {target_uom.name}: {type(exc).__name__}: {exc}"
        )

for row in H:
    check_uom(row["Product_code"], row["Unit"], f'BoM {row["BOM_CODE"]}')
for i, row in enumerate(C, 2):
    check_uom(row["ID_COMPONENT"], row["UOM_COMPONENT"], f"component row {i}")

# Operation Type is stock.picking.type, NOT mrp.routing.workcenter.
PT = env["stock.picking.type"].sudo().with_context(active_test=False)
picking_types = PT.search([("code", "=", "mrp_operation")])
def names_of(pt):
    names = {str(pt.name or "").strip().casefold(), str(pt.display_name or "").strip().casefold()}
    if "warehouse_id" in pt._fields and pt.warehouse_id:
        names.add(f"{pt.warehouse_id.name}: {pt.name}".strip().casefold())
    return names
pt_names = defaultdict(list)
for pt in picking_types:
    for name in names_of(pt):
        if name:
            pt_names[name].append(pt.id)
op_values = sorted({r["Operation Type"] for r in H if r["Operation Type"]})
print("MANUFACTURING_OPERATION_TYPE_RECORDS:", len(picking_types))
for name in op_values:
    matches = sorted(set(pt_names.get(name.strip().casefold(), [])))
    if len(matches) != 1:
        issue("OPERATION_TYPE_NOT_EXACTLY_MATCHED", f"{name!r}: {len(matches)} matches")
    print("OPERATION_TYPE:", repr(name), "matched_ids=", matches)

B = env["mrp.bom"].sudo().with_context(active_test=False)
print("EXISTING_BOM_COUNT:", B.search_count([]))
if B.search_count([]):
    issue("EXISTING_BOMS_REQUIRE_REVIEW", "Database contains BoMs; cannot assume fresh import")
print("UNIQUE_HEADER_SKUS:", len(h_skus), "UNIQUE_COMPONENT_GROUPS:", len(c_skus))
print("UNIQUE_COMPONENT_SKUS:", len({x["ID_COMPONENT"] for x in C}))
print("UNIQUE_UOMS:", len({x["Unit"] for x in H} | {x["UOM_COMPONENT"] for x in C}))
print("ISSUE_SUMMARY:")
for kind in sorted(errors):
    print(f"  {kind}: {len(errors[kind])}")
    for sample in errors[kind][:12]:
        print("    -", sample)
if not errors:
    print("BOM_AUDIT_OK: all tested cross-references resolved; no changes made")
else:
    print("BOM_AUDIT_NEEDS_REVIEW: no changes made")
