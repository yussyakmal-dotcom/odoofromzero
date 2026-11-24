"""Minimal native STOCK MOVE no-negative guard verification after OCA install.

TEST ONLY, ALWAYS ROLLBACK. This is NOT another MO happy-path UAT.
Uses owner-confirmed SUL premix 10662, just opnamed to zero. Attempts to
consume 1 Bungkus via a native stock.move into virtual Production. It must
raise a negative-stock ValidationError; otherwise the script fails but rolls
back completely. NO production database, NO positive inventory seed.
"""
from odoo.exceptions import ValidationError
from odoo.tools import float_compare

assert env.cr.dbname == "erp-yussyakmal-mrp-test", (
    "REFUSED: TEST DATABASE ONLY")
Module = env["ir.module.module"].sudo()
Warehouse = env["stock.warehouse"].sudo()
Product = env["product.product"].sudo()
Quant = env["stock.quant"].sudo()
Move = env["stock.move"].sudo()

mod = Module.search([("name", "=", "stock_no_negative")], limit=2)
assert len(mod) == 1 and mod.state == "installed", (
    "REFUSED: OCA stock_no_negative is not installed on TEST")
assert callable(getattr(Quant, "check_negative_qty", None)), (
    "REFUSED: OCA registry quant validator missing")
sul = Warehouse.search([("code", "=", "SUL")], limit=2)
assert len(sul) == 1 and sul.lot_stock_id.complete_name == "SUL/Stock"
prod = Product.search([("default_code", "=", "10662")], limit=2)
assert len(prod) == 1 and prod.is_storable and prod.tracking == "none"
assert prod.uom_id.name.casefold() == "bungkus"
assert not prod.allow_negative_stock
assert not prod.categ_id.allow_negative_stock
assert not sul.lot_stock_id.allow_negative_stock
source = sul.lot_stock_id
production = env.ref("stock.location_production", raise_if_not_found=False)
assert production and production.usage == "production"
existing = Quant.search([
    ("product_id", "=", prod.id),
    ("location_id", "=", source.id),
    ("company_id", "=", sul.company_id.id),
])
base_qty = sum(existing.mapped("quantity"))
assert float_compare(base_qty, 0.0,
                     precision_rounding=prod.uom_id.rounding) == 0, (
    "REFUSED: SUL premix not zero; do not consume real inventory")
base_done_count = Move.search_count([("state", "=", "done")])
base_quant_count = Quant.search_count([])
print("DATABASE:", env.cr.dbname)
print("MODE: OCA_NEGATIVE_STOCK_NATIVE_MOVE_ALWAYS_ROLLBACK")
print("OCA_MODULE:", mod.name, mod.state, mod.installed_version)
print("SOURCE:", source.complete_name, "PRODUCT:", prod.display_name)
print("BASELINE_STOCK:", base_qty, prod.uom_id.name)
print("ATTEMPT: Move 1 Bungkus from 0 stock to virtual Production")
print("NOTE: This tests the OCA quant constraint via native stock.move; "
      "not separate MO behavior or all material policies.")
blocked = False
try:
    try:
        with env.cr.savepoint():
            move = Move.with_company(sul.company_id).create({
                "name": "YA_OCA_NO_NEGATIVE_TEST_MOVE_ALWAYS_ROLLBACK",
                "product_id": prod.id,
                "product_uom": prod.uom_id.id,
                "product_uom_qty": 1.0,
                "location_id": source.id,
                "location_dest_id": production.id,
                "company_id": sul.company_id.id,
            })
            move._action_confirm()
            move.write({"quantity": 1.0})
            move._action_done()
            env.flush_all()
            print("ERROR: Native move posted although 0 stock was available")
    except ValidationError as exc:
        blocked = True
        print("NEGATIVE_STOCK_VALIDATION_ERROR:", str(exc)[:500])
finally:
    env.cr.rollback()
    env.invalidate_all()

after_qty = sum(Quant.search([
    ("product_id", "=", prod.id),
    ("location_id", "=", source.id),
    ("company_id", "=", sul.company_id.id),
]).mapped("quantity"))
assert float_compare(
    after_qty, base_qty, precision_rounding=prod.uom_id.rounding
) == 0, "ROLLBACK ERROR: changed stock in SUL"
assert Move.search_count([("state", "=", "done")]) == base_done_count, (
    "ROLLBACK ERROR: persisted a Done move")
assert Quant.search_count([]) == base_quant_count, (
    "ROLLBACK ERROR: changed quant count")
print("OCA_TEST_TRANSACTION_ROLLBACK_VERIFIED")
assert blocked, (
    "BLOCKER: Native zero-stock consumption did not trigger OCA "
    "ValidationError; do not approve rollout")
print("OCA_STOCK_NO_NEGATIVE_GUARD_ROLLBACK_PASS")
