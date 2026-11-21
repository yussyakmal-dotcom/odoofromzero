"""End-to-end 3 DISTINCT SKU -> 3 native stock.scrap -> 1 YA batch.

Database is MRP TEST only. Temporary stock is seeded with stock.quant ORM,
then full transaction is ALWAYS rolled back. No stock or scrap persists.
This tests stock moves, origin, reason tags and common batch link.
"""
from collections import Counter
import traceback

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "Wrong database"
Batch = env["ya.scrap.batch"].sudo()
Scrap = env["stock.scrap"].sudo()
Move = env["stock.move"].sudo()
Loc = env["stock.location"].sudo()
Tag = env["stock.scrap.reason.tag"].sudo()
Quant = env["stock.quant"].sudo()
BoM = env["mrp.bom"].sudo()
assert "ya_batch_id" in Scrap._fields, "Addon not loaded"
assert "move_ids" in Scrap._fields, "Native stock.scrap.move_ids not found"
assert hasattr(Quant, "_update_available_quantity")

source = Loc.search([
    ("complete_name", "=", "TART/Stock"),
    ("usage", "=", "internal")
], limit=2)
assert len(source) == 1, "Expected a unique TART/Stock"
source = source[0]
company = source.company_id or env.company
dest = Loc.search([
    ("name", "=", "Scrap"), ("usage", "=", "inventory"),
    ("company_id", "=", company.id)
], limit=2)
assert len(dest) == 1, "Exactly one shared Scrap destination required"
dest = dest[0]
reason = Tag.search([("name", "=", "Rusak")], limit=2)
assert len(reason) == 1, "Rusak reason must be unique"
reason = reason[0]
bom = BoM.search([("code", "=", "BOM12499")], limit=2)
assert len(bom) == 1, "Known sample BOM missing or not unique"
products = []
seen = set()
for line in bom.bom_line_ids:
    p = line.product_id
    if p.id not in seen and p.type != "service" and (
        not p.company_id or p.company_id == company
    ) and p.tracking == "none":
        products.append(p)
        seen.add(p.id)
    if len(products) == 3:
        break
assert len(products) == 3, "Need 3 distinct, non-tracked BOM component SKUs"

baseline_batch = Batch.search_count([])
baseline_scrap = Scrap.search_count([])
baseline_move = Move.search_count([])
baseline_quants = {}
for p in products:
    baseline_quants[p.id] = Quant._get_available_quantity(p, source, strict=True)

print("DATABASE:", env.cr.dbname)
print("MODE: E2E_3_SKU_ALWAYS_ROLLBACK")
print("SOURCE:", source.complete_name, "SCRAP_DEST:", dest.complete_name)
print("SINGLE_REASON:", reason.name)
print("SINGLE_SOURCE_DOCUMENT: YA-E2E-3SKU-ROLLBACK")
print("EXAMPLE_SKUS:", ", ".join(p.default_code or p.display_name for p in products))
passed = False
try:
    # Controlled temporary quantity for each product. No inventory-adjustment
    # posting needed; this is not an accounting-valuation test.
    for p in products:
        current = Quant._get_available_quantity(p, source, strict=True)
        addition = max(0.0, 10.0 - current)
        if addition:
            Quant._update_available_quantity(p, source, addition)
    lines = [
        (0, 0, {
            "product_id": p.id,
            "qty": float(i + 1),
            "uom_id": p.uom_id.id,
        }) for i, p in enumerate(products)
    ]
    batch = Batch.with_company(company).create({
        "company_id": company.id,
        "location_id": source.id,
        "scrap_location_id": dest.id,
        "reason_tag_id": reason.id,
        "source_document": "YA-E2E-3SKU-ROLLBACK",
        "line_ids": lines,
    })
    assert len(batch.line_ids) == 3
    batch.action_validate()
    env.flush_all()
    scraps = Scrap.search([("ya_batch_id", "=", batch.id)])
    assert batch.state == "done", f"Batch state {batch.state}"
    assert len(scraps) == 3, f"Expected 3 native scraps, got {len(scraps)}"
    assert batch.scrap_count == 3, f"Smart button count: {batch.scrap_count}"
    assert len(set(scraps.mapped("product_id").ids)) == 3
    assert set(scraps.mapped("product_id").ids) == set(p.id for p in products)
    assert all(x.state == "done" for x in scraps)
    assert all(x.origin == batch.source_document for x in scraps)
    assert all(x.location_id == source for x in scraps)
    assert all(x.scrap_location_id == dest for x in scraps)
    assert all(x.scrap_reason_tag_ids.ids == [reason.id] for x in scraps)
    assert all(x.ya_batch_id == batch for x in scraps)
    all_moves = Move.browse()
    for x in scraps:
        moves = x.move_ids
        assert moves, f"Scrap {x.id} has no native stock move"
        assert all(m.state == "done" for m in moves), f"Move not Done: {moves.ids}"
        assert all(m.product_id == x.product_id for m in moves)
        assert all(m.location_id == source and m.location_dest_id == dest for m in moves)
        all_moves |= moves
        print("NATIVE_SCRAP:", x.name, "| SKU:", x.product_id.default_code,
              "| QTY:", x.scrap_qty, "| MOVES:", moves.ids,
              "| REASON:", ",".join(x.scrap_reason_tag_ids.mapped("name")),
              "| SOURCE_DOC:", x.origin, "| BATCH:", x.ya_batch_id.name)
    assert len(all_moves) == 3, f"Expected exactly 3 distinct stock moves, got {len(all_moves)}"
    assert all_moves.mapped("state") == ["done"] * 3
    for i, p in enumerate(products):
        qty = Quant._get_available_quantity(p, source, strict=True)
        expected = baseline_quants[p.id] + max(0, 10 - baseline_quants[p.id]) - (i + 1)
        assert abs(qty - expected) < 1e-5, (p.default_code, qty, expected)
        print("POST_SCRAP_STOCK:", p.default_code, "| SOURCE_QTY:", qty)
    passed = True
    print("E2E_3_SKU_3_NATIVE_SCRAPS_1_BATCH_OK")
except BaseException:
    print("E2E_TEST_EXCEPTION:")
    traceback.print_exc()
    raise
finally:
    env.cr.rollback()
    env.invalidate_all()
    assert Batch.search_count([]) == baseline_batch, "Rollback: batch count mismatch"
    assert Scrap.search_count([]) == baseline_scrap, "Rollback: scrap count mismatch"
    assert Move.search_count([]) == baseline_move, "Rollback: move count mismatch"
    for p in products:
        now = Quant._get_available_quantity(p, source, strict=True)
        assert abs(now - baseline_quants[p.id]) < 1e-5, (
            "Rollback quantity mismatch", p.default_code, now, baseline_quants[p.id]
        )
    print("E2E_3_SKU_ROLLBACK_CONFIRMED")
