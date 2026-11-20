"""Rollback-only integration test for the standard Operations receipt UI."""
from odoo.exceptions import UserError

print("DATABASE:", env.cr.dbname)
assert env.cr.dbname == "erp-yussyakmal-integer-test", "TEST DB ONLY"
print("MODE: OPERATIONS ROWS ORM / VALIDATE / ALL ROLLBACK")
try:
    picking = env["stock.picking"].search([
        ("name", "=", "CDC/IN/00001"), ("origin", "=", "P00009")
    ], limit=1)
    assert picking and picking.state not in ("done", "cancel"), "Expected open test receipt"
    moves = picking.move_ids.filtered(lambda m: m.product_id.default_code == "10164")
    assert len(moves) == 2, "Expected two Beras Mawar lines"
    large = moves.filtered(lambda m: m.product_uom_qty == 25000)
    small = moves.filtered(lambda m: m.product_uom_qty == 500)
    assert len(large) == len(small) == 1
    Rule = env["ya.purchase.uom.rule"]
    kg = Rule.search([
        ("product_id", "=", large.product_id.id), ("purchase_label", "=ilike", "Kg"),
        ("factor", "=", 1000), ("active", "=", True)
    ], limit=1)
    gram = Rule.search([
        ("product_id", "=", small.product_id.id), ("factor", "=", 1),
        ("active", "=", True)
    ], limit=1)
    assert kg and gram, "Missing SKU rules"
    assert large.ya_demand_display == "25 Kg", large.ya_demand_display
    assert small.ya_demand_display == "500 Gram", small.ya_demand_display
    print("PASS: demand shows purchased physical quantity + unit")
    large.write({"ya_receipt_rule_id": kg.id, "ya_receipt_qty_units": 26})
    small.write({"ya_receipt_rule_id": gram.id, "ya_receipt_qty_units": 500})
    warning = large._onchange_ya_receipt_quantity_limit()
    assert warning.get("warning"), "Expected immediate over-demand UI warning"
    print("PASS: onchange warns immediately for 26 Kg > demand 25 Kg")
    try:
        with env.cr.savepoint():
            picking._ya_apply_physical_quantities()
    except UserError:
        print("PASS: received 26 Kg > demand 25 Kg rejected")
    else:
        raise AssertionError("Over-receipt was accepted")
    large.write({"ya_receipt_qty_units": 25})
    assert not large._onchange_ya_receipt_quantity_limit().get("warning")
    print("PASS: onchange accepts quantity equal to demand")
    picking._ya_apply_physical_quantities()
    assert large.quantity == 25000
    print("PASS: received 25 Kg = demand 25 Kg accepted")
    large.write({"ya_receipt_rule_id": kg.id, "ya_receipt_qty_units": 20})
    small.write({"ya_receipt_rule_id": gram.id, "ya_receipt_qty_units": 500})
    assert large.ya_receipt_qty_units == 20 and small.ya_receipt_qty_units == 500
    print("PASS: input directly on existing stock.move rows")
    picking.picking_type_id.write({"create_backorder": "never"})
    print("TEST ONLY: backorder policy ask -> never")
    result = picking.button_validate()
    assert picking.state == "done", f"Receipt not done: {result}"
    assert large.quantity == 20000 and small.quantity == 500
    assert large.ya_received_unit_qty == 20 and large.ya_received_unit_label == kg.purchase_label
    assert small.ya_received_unit_qty == 500
    assert not picking.backorder_ids
    assert large.purchase_line_id.qty_received == 20000
    assert small.purchase_line_id.qty_received == 500
    print("PASS: 20 Kg + 500 Gram => 20500 Gram in stock")
    print("PASS: receipt DONE, 0 backorders, PO received quantities correct")
    print("OPERATIONS_RECEIVING_VALIDATE_OK")
finally:
    env.cr.rollback()
    print("ROLLBACK_COMPLETE: no stock, PO or policy changes persisted")
