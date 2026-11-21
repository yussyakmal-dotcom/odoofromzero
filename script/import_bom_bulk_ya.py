"""YA BoM bulk loader for Odoo 19: PREVIEW / TEST (ROLLBACK) / APPLY.

CSV inputs remain PRIVATE and must be placed on the Odoo server.
This script must run via odoo-bin shell on the dedicated MRP test DB.
Modes:
  YA_BOM_MODE=preview  : validate source/refs, no ORM creation
  YA_BOM_MODE=test     : create all BoMs then ALWAYS roll back
  YA_BOM_MODE=apply    : create all BoMs, verify, then commit (explicit)
Default mode is preview. No work orders or operation steps are created.
"""
import csv
import hashlib
import os
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path

DB = "erp-yussyakmal-mrp-test"
EXPECTED_HEADERS = 955
EXPECTED_COMPONENTS = 8502
mode = os.environ.get("YA_BOM_MODE", "preview").strip().lower()
assert env.cr.dbname == DB, "Wrong database; refusing BoM work"
assert mode in {"preview", "test", "apply"}, "YA_BOM_MODE must be preview, test or apply"
assert os.environ.get("YA_APPLY") != "1", "Use YA_BOM_MODE only, not legacy YA_APPLY"

def load(key, columns):
    path = Path(os.environ.get(key, ""))
    assert path.is_file(), f"File missing/unreadable: {key}"
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        assert set(columns) <= set(reader.fieldnames or []), (key, reader.fieldnames)
        rows = [{k: (v or "").strip() for k, v in row.items()} for row in reader]
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    print("INPUT:", path.name, "SHA256:", sha, "ROWS:", len(rows))
    return rows

headers = load("YA_BOM_HEADER_CSV",
    ["BOM_CODE", "Product_code", "BoM Type", "Operation Type", "Quantity", "Unit"])
components = load("YA_BOM_COMPONENT_CSV",
    ["Product/Internal Reference", "ID_COMPONENT", "QTY_COMPONENT", "UOM_COMPONENT"])
assert len(headers) == EXPECTED_HEADERS, f"Expected {EXPECTED_HEADERS} headers, got {len(headers)}"
assert len(components) == EXPECTED_COMPONENTS, f"Expected {EXPECTED_COMPONENTS} component rows, got {len(components)}"

def positive_integer(raw, label):
    try:
        number = Decimal(raw)
    except InvalidOperation as exc:
        raise AssertionError(f"{label}: invalid quantity {raw!r}") from exc
    assert number.is_finite() and number > 0 and number == number.to_integral_value(), (
        f"{label}: quantity must be a positive integer: {raw!r}"
    )
    return float(number)

bom_codes = Counter(h["BOM_CODE"] for h in headers)
result_skus = Counter(h["Product_code"] for h in headers)
assert all(k and n == 1 for k, n in bom_codes.items()), "Blank or duplicate BOM_CODE"
assert all(k and n == 1 for k, n in result_skus.items()), "Blank or duplicate result SKU"
by_group = defaultdict(list)
for i, line in enumerate(components, 2):
    group = line["Product/Internal Reference"]
    assert group and line["ID_COMPONENT"], f"Missing component/group SKU at CSV row {i}"
    positive_integer(line["QTY_COMPONENT"], f"Component row {i}")
    by_group[group].append(line)
assert set(by_group) == set(result_skus), "Orphan component group or header with no components"
for h in headers:
    assert h["BoM Type"] == "Manufacture this product", h["BOM_CODE"]
    assert h["Operation Type"] and ":" in h["Operation Type"], h["BOM_CODE"]
    positive_integer(h["Quantity"], h["BOM_CODE"])

P = env["product.product"].sudo().with_context(active_test=False)
U = env["uom.uom"].sudo().with_context(active_test=False)
PT = env["stock.picking.type"].sudo().with_context(active_test=False)
B = env["mrp.bom"].sudo().with_context(active_test=False)
assert B.search_count([]) == 0, "Existing BoMs found; refusing creation to prevent duplicates"
needed_skus = sorted(set(result_skus) | {x["ID_COMPONENT"] for x in components})
products = defaultdict(list)
for offset in range(0, len(needed_skus), 300):
    for p in P.search([("default_code", "in", needed_skus[offset:offset+300])]):
        products[p.default_code].append(p)
assert all(len(products[sku]) == 1 for sku in needed_skus), (
    "Missing or ambiguous product SKUs: " +
    repr([sku for sku in needed_skus if len(products[sku]) != 1][:20])
)
products = {sku: items[0] for sku, items in products.items()}

units = defaultdict(list)
for unit in U.search([]):
    units[unit.name.strip().casefold()].append(unit)
conversion_cache = {}
def uom_for(sku, label):
    key = (sku, label.casefold())
    if key in conversion_cache:
        return conversion_cache[key]
    matches = units[label.casefold()]
    assert len(matches) == 1, f"UoM unresolved or ambiguous: {label!r}"
    uom = matches[0]
    target = products[sku].uom_id
    assert uom._compute_quantity(1, target, raise_if_failure=True) > 0, (
        f"Incompatible UoM SKU {sku}: {label} -> {target.name}"
    )
    conversion_cache[key] = uom
    return uom

types_by_warehouse = defaultdict(list)
for picking in PT.search([("code", "=", "mrp_operation"), ("active", "=", True)]):
    if picking.warehouse_id:
        types_by_warehouse[picking.warehouse_id.name.strip().casefold()].append(picking)
resolved_types = {}
for label in {h["Operation Type"] for h in headers}:
    warehouse = label.split(":", 1)[0].strip().casefold()
    matches = types_by_warehouse[warehouse]
    assert len(matches) == 1, f"Manufacturing picking type ambiguous or absent: {label}"
    resolved_types[label] = matches[0]

prepared = []
total_lines = 0
for h in headers:
    result = products[h["Product_code"]]
    head_uom = uom_for(h["Product_code"], h["Unit"])
    cmds = []
    for line in by_group[h["Product_code"]]:
        component = products[line["ID_COMPONENT"]]
        component_uom = uom_for(line["ID_COMPONENT"], line["UOM_COMPONENT"])
        cmds.append((0, 0, {
            "product_id": component.id,
            "product_qty": positive_integer(line["QTY_COMPONENT"], h["BOM_CODE"]),
            "product_uom_id": component_uom.id,
        }))
    prepared.append((h["BOM_CODE"], {
        "code": h["BOM_CODE"],
        "product_tmpl_id": result.product_tmpl_id.id,
        "product_id": result.id,
        "product_qty": positive_integer(h["Quantity"], h["BOM_CODE"]),
        "product_uom_id": head_uom.id,
        "type": "normal",
        "picking_type_id": resolved_types[h["Operation Type"]].id,
        "bom_line_ids": cmds,
    }, len(cmds)))
    total_lines += len(cmds)
assert len(prepared) == EXPECTED_HEADERS and total_lines == EXPECTED_COMPONENTS
print("DATABASE:", DB, "MODE:", mode.upper())
print("VALIDATED HEADERS:", len(prepared), "COMPONENT LINES:", total_lines)
print("PRODUCT SKUS:", len(needed_skus), "MFG OPERATION TYPES:", len(resolved_types))
print("PRESERVING CSV LINE ORDER AND REPEATED COMPONENT SKUS")
print("WORK ORDER OPERATIONS: NONE")
if mode == "preview":
    print("BOM_BULK_PREVIEW_OK (NO CHANGES MADE)")
else:
    made = 0
    created_lines = 0
    try:
        for code, values, expected_lines in prepared:
            bom = B.create(values)
            assert bom.code == code and bom.product_id.id == values["product_id"], (
                f"Header mismatch: {code}"
            )
            assert bom.picking_type_id.id == values["picking_type_id"], (
                f"Operation type mismatch: {code}"
            )
            assert len(bom.bom_line_ids) == expected_lines, (
                f"Component line count mismatch: {code}"
            )
            assert not bom.operation_ids, f"Unexpected work-order steps on {code}"
            # Ensure quantities and component IDs are preserved in line order,
            # including intentionally repeated ingredients.
            actual_lines = sorted(bom.bom_line_ids, key=lambda x: (x.sequence, x.id))
            expected = values["bom_line_ids"]
            for idx, (actual, command) in enumerate(zip(actual_lines, expected), 1):
                wanted = command[2]
                assert actual.product_id.id == wanted["product_id"], (
                    f"Component product mismatch: {code} #{idx}"
                )
                assert actual.product_uom_id.id == wanted["product_uom_id"], (
                    f"Component UoM mismatch: {code} #{idx}"
                )
                assert abs(actual.product_qty - wanted["product_qty"]) < 1e-8, (
                    f"Component quantity mismatch: {code} #{idx}"
                )
            made += 1
            created_lines += len(bom.bom_line_ids)
            if made % 100 == 0:
                print("VERIFIED", made, "BoMs,", created_lines, "component lines")
        env.flush_all()
        assert made == EXPECTED_HEADERS and created_lines == EXPECTED_COMPONENTS
        assert B.search_count([]) == EXPECTED_HEADERS, (
            "Unexpected number of BoMs after ORM creation"
        )
        if mode == "test":
            print("BOM_BULK_TEST_OK created and verified:", made, created_lines)
        else:
            env.cr.commit()
            print("BOM_BULK_APPLY_OK COMMITTED:", made, created_lines)
    except Exception:
        env.cr.rollback()
        print("BOM_BULK_FAILED ROLLED BACK")
        raise
    finally:
        if mode == "test":
            env.cr.rollback()
            assert B.search_count([]) == 0, "Rollback verification failed"
            print("BOM_BULK_ROLLBACK_CONFIRMED: zero BoMs retained")
