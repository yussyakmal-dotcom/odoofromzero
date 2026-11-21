"""ROLLBACK-ONLY Odoo 19 BoM ORM test for one real YA recipe.

Usage via Odoo shell -d erp-yussyakmal-mrp-test with:
  YA_BOM_HEADER_CSV=/private/path/BOMTOZERO_FINAL_UOM_PCS.csv
  YA_BOM_COMPONENT_CSV=/private/path/BOM_COMPONENT_FINAL_UOM_PCS.csv

Uses the actual BOM12499 recipe and all 16 component rows. Never commits.
This is NOT a production importer.
"""
import csv
import os
from decimal import Decimal
from pathlib import Path

DB = "erp-yussyakmal-mrp-test"
TEST_CODE = "BOM12499"
assert env.cr.dbname == DB, "Only manufacturing test database permitted"
assert os.environ.get("YA_APPLY") != "1", "Rollback test cannot APPLY"

def records(variable, columns):
    path = Path(os.environ.get(variable, ""))
    assert path.is_file(), f"File missing or inaccessible: {variable}={path}"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        assert set(columns) <= set(reader.fieldnames or []), (variable, reader.fieldnames)
        return [{k: (v or "").strip() for k, v in row.items()} for row in reader]

headers = records("YA_BOM_HEADER_CSV",
    {"BOM_CODE", "Product_code", "Quantity", "Unit", "Operation Type"})
lines = records("YA_BOM_COMPONENT_CSV",
    {"Product/Internal Reference", "ID_COMPONENT", "QTY_COMPONENT", "UOM_COMPONENT"})
chosen = [r for r in headers if r["BOM_CODE"] == TEST_CODE]
assert len(chosen) == 1, f"Expected exactly one {TEST_CODE} header"
head = chosen[0]
component_rows = [r for r in lines if r["Product/Internal Reference"] == head["Product_code"]]
assert len(component_rows) == 16, (
    f"{TEST_CODE} expected 16 component lines but received {len(component_rows)}"
)
assert head["BoM Type"] == "Manufacture this product"

P = env["product.product"].sudo().with_context(active_test=False)
U = env["uom.uom"].sudo().with_context(active_test=False)
PT = env["stock.picking.type"].sudo().with_context(active_test=False)
B = env["mrp.bom"].sudo().with_context(active_test=False)

def product_by_code(code):
    result = P.search([("default_code", "=", code)])
    assert len(result) == 1, f"SKU not uniquely resolved: {code}, count={len(result)}"
    return result

def uom_by_name(name, product):
    matches = U.search([("name", "=ilike", name)])
    assert len(matches) == 1, f"UoM unresolved: {name}, count={len(matches)}"
    # Existing preview was successful. Double-check native convertibility.
    assert matches._compute_quantity(1, product.uom_id, raise_if_failure=True) > 0
    return matches

def qty(value):
    number = Decimal(value)
    assert number.is_finite() and number > 0 and number == number.to_integral_value(), value
    return float(number)

assert B.search_count([]) == 0, "Rollback test requires empty BoM master"
product = product_by_code(head["Product_code"])
assert ":" in head["Operation Type"], "Missing warehouse prefix"
warehouse_name = head["Operation Type"].split(":", 1)[0].strip().casefold()
picking_types = PT.search([("code", "=", "mrp_operation"), ("active", "=", True)])
matches = [pt for pt in picking_types
           if pt.warehouse_id and pt.warehouse_id.name.strip().casefold() == warehouse_name]
assert len(matches) == 1, f"Manufacturing picking type unresolved: {warehouse_name}"
picking_type = matches[0]

commands = []
for row in component_rows:
    component = product_by_code(row["ID_COMPONENT"])
    unit = uom_by_name(row["UOM_COMPONENT"], component)
    commands.append((0, 0, {
        "product_id": component.id,
        "product_qty": qty(row["QTY_COMPONENT"]),
        "product_uom_id": unit.id,
    }))

print("DATABASE:", env.cr.dbname, "MODE: CREATE + VERIFY + ALWAYS ROLLBACK")
print("TEST BOM:", TEST_CODE, "PRODUCT:", product.default_code)
print("OPERATION TYPE:", picking_type.display_name, "ID:", picking_type.id)
print("COMPONENT LINES:", len(commands))
try:
    bom = B.create({
        "code": TEST_CODE,
        "product_tmpl_id": product.product_tmpl_id.id,
        "product_id": product.id,
        "product_qty": qty(head["Quantity"]),
        "product_uom_id": uom_by_name(head["Unit"], product).id,
        "type": "normal",
        "picking_type_id": picking_type.id,
        "bom_line_ids": commands,
    })
    env.flush_all()
    assert bom.exists(), "Created BoM not found"
    assert bom.code == TEST_CODE
    assert bom.product_id == product
    assert bom.picking_type_id == picking_type
    assert len(bom.bom_line_ids) == len(commands), (
        len(bom.bom_line_ids), len(commands)
    )
    assert len(bom.operation_ids) == 0, "No manufacturing operations expected"
    assert B.search_count([("code", "=", TEST_CODE)]) == 1
    print("ROLLBACK_TEST_OK: ORM created and verified", len(bom.bom_line_ids), "lines")
finally:
    env.cr.rollback()
    assert B.search_count([("code", "=", TEST_CODE)]) == 0, (
        "Rollback failed: BoM remains"
    )
    print("ROLLBACK_CONFIRMED: no BoM retained")
