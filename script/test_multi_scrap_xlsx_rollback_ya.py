"""Rollback-only smoke test for YA Multi-SKU Scrap addon (after install).

No stock posting. Creates a draft parent, imports 2 products from an in-memory
Excel workbook and checks shared reason/source and quantity/UoM. Rolls back.
"""
import base64
from io import BytesIO
from openpyxl import Workbook

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "Wrong DB"
B = env["ya.scrap.batch"].sudo()
L = env["stock.location"].sudo()
Tag = env["stock.scrap.reason.tag"].sudo()
P = env["product.product"].sudo()
S = env["stock.scrap"].sudo()
assert B.search_count([]) >= 0
src = L.search([("complete_name", "=", "TART/Stock")], limit=2)
assert len(src) == 1, "Source TART/Stock not found"
scrap = L.search([("name", "=", "Scrap"), ("usage", "=", "inventory")], limit=2)
assert len(scrap) == 1, "Install/configure the one shared Scrap location first"
reason = Tag.search([("name", "=", "Rusak")], limit=2)
assert len(reason) == 1, "Install/configure reason tag Rusak first"
products = []
for sku in ["10180", "10182"]:
    p = P.search([("default_code", "=", sku)], limit=2)
    assert len(p) == 1, f"SKU {sku} missing/duplicated"
    products.append(p[0])
before_batch = B.search_count([])
before_scrap = S.search_count([])
print("DATABASE:", env.cr.dbname, "MODE: DRAFT_XLSX_TEST_ALWAYS_ROLLBACK")
try:
    batch = B.create({
        "company_id": src.company_id.id or env.company.id,
        "location_id": src.id,
        "scrap_location_id": scrap.id,
        "reason_tag_id": reason.id,
        "source_document": "YA-TEST-SCRAP-XLSX-ROLLBACK",
    })
    wb = Workbook()
    ws = wb.active
    ws.append(["SKU", "Quantity", "UoM"])
    ws.append([products[0].default_code, 2, products[0].uom_id.name])
    ws.append([products[1].default_code, 3, products[1].uom_id.name])
    out = BytesIO()
    wb.save(out)
    batch.write({
        "import_file": base64.b64encode(out.getvalue()),
        "import_filename": "test_scrap.xlsx",
    })
    batch.action_import_xlsx()
    assert len(batch.line_ids) == 2
    assert set(batch.line_ids.mapped("product_id").ids) == set(p.id for p in products)
    assert sorted(batch.line_ids.mapped("qty")) == [2.0, 3.0]
    assert all(x.uom_id.id == x.product_id.uom_id.id for x in batch.line_ids)
    assert batch.state == "draft"
    assert S.search_count([]) == before_scrap
    print("MULTI_SCRAP_XLSX_DRAFT_TEST_OK: 2 SKU, 1 reason, 1 source doc")
finally:
    env.cr.rollback()
    env.invalidate_all()
    assert B.search_count([]) == before_batch, "Batch rollback failed"
    assert S.search_count([]) == before_scrap, "Native Scrap rollback failed"
    print("MULTI_SCRAP_TEST_ROLLBACK_CONFIRMED")
