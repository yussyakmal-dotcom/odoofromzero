"""YA negative-stock enforcement probe (real stock move, always rollback).

Tests 1 Gram of existing SKU 10180 from TART/Stock with zero available
to Odoo's Production virtual location. A direct stock move is NOT a full
MO Mark as Done test. The probe never commits.
"""
from odoo.exceptions import UserError, ValidationError

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "Wrong database"
SM = env["stock.move"].sudo()
Q = env["stock.quant"].sudo()
P = env["product.product"].sudo()
B = env["mrp.bom"].sudo()
L = env["mrp.bom.line"].sudo()
assert B.search_count([]) == 955 and L.search_count([]) == 8502

sku = P.search([("default_code", "=", "10180")], limit=2)
assert len(sku) == 1, "SKU 10180 missing or duplicated"
product = sku[0]
assert product.uom_id.name.casefold() == "gram"
bom = B.search([("code", "=", "BOM12499")], limit=2)
assert len(bom) == 1
source = bom.picking_type_id.default_location_src_id
assert source and source.usage == "internal", "Expected internal source location"
assert source.complete_name == "TART/Stock", (
    f"Unexpected source: {source.complete_name}"
)
production = env.ref("stock.location_production", raise_if_not_found=False)
assert production and production.usage == "production", (
    "Odoo production location missing"
)
demand = 1.0
available = Q._get_available_quantity(product, source, strict=False)
assert abs(available) < 1e-9, (
    f"Expected SKU 10180 source to have zero available; got {available}"
)
start_done = SM.search_count([("state", "=", "done")])
start_quants = Q.search_count([])
print("DATABASE:", env.cr.dbname)
print("MODE: NEGATIVE_STOCK_PROBE_ALWAYS_ROLLBACK")
print("PRODUCT:", product.default_code, product.name)
print("SOURCE:", source.complete_name, "DEST:", production.complete_name)
print("AVAILABLE_BEFORE:", available, product.uom_id.name)
print("ATTEMPT:", demand, product.uom_id.name)
print("NOTE: Direct stock move test, not MO completion")
outcome = "NOT_RUN"
try:
    # Savepoint prevents a business-level rejection from poisoning the
    # transaction; the outer finally still guarantees global rollback.
    try:
        with env.cr.savepoint():
            move = SM.create({
                "name": "YA_NEGATIVE_STOCK_PROBE_ROLLBACK",
                "product_id": product.id,
                "product_uom_qty": demand,
                "product_uom": product.uom_id.id,
                "location_id": source.id,
                "location_dest_id": production.id,
            })
            move._action_confirm()
            assert "quantity" in move._fields, (
                "Stock move has no quantity field; inspect Odoo 19 API"
            )
            move.write({"quantity": demand})
            move._action_done()
            env.flush_all()
            after = Q._get_available_quantity(product, source, strict=False)
            print("SOURCE_AVAILABLE_AFTER_MOVE:", after, product.uom_id.name)
            assert move.state == "done", (
                f"Move not posted, state={move.state}; API test inconclusive"
            )
            if after < -1e-9:
                outcome = "NEGATIVE_STOCK_ALLOWED"
                print("NEGATIVE_STOCK_ALLOWED: BLOCKER -- needs enforcement before MO completion")
            else:
                outcome = "POSTED_WITHOUT_NEGATIVE"
                print("UNEXPECTED_NONNEGATIVE_AFTER_POST: investigate quant/location rules")
    except (UserError, ValidationError) as exc:
        outcome = "BLOCKED_BY_BUSINESS_RULE"
        print("NEGATIVE_STOCK_BLOCKED_BY_BUSINESS_RULE:", str(exc))
    assert outcome != "NOT_RUN", "Probe did not complete"
    print("PROBE_OUTCOME:", outcome)
finally:
    env.cr.rollback()
    env.invalidate_all()
    assert SM.search_count([("state", "=", "done")]) == start_done, (
        "Rollback failed: done move count changed"
    )
    assert Q.search_count([]) == start_quants, (
        "Rollback failed: quant count changed"
    )
    final_available = Q._get_available_quantity(product, source, strict=False)
    assert abs(final_available - available) < 1e-9, (
        "Rollback failed: available quantity changed"
    )
    print("NEGATIVE_STOCK_PROBE_ROLLBACK_CONFIRMED")
