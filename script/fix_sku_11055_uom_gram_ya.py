"""Correct YA SKU 11055 base UoM Pcs -> Gram, preserving BOM recipes.

Odoo 19 MRP test ONLY. Defaults to PREVIEW; use YA_UOM_MODE=test
for full ORM change with unconditional rollback, then YA_UOM_MODE=apply
ONLY after a successful test. No SQL or bypass of Odoo constraints.
BoM component lines may need to be recreated because the built-in Odoo
product UoM guard prevents a product UoM change while a line references it.
This script preserves each line's values but the two line IDs will change.
"""
from collections import Counter
from decimal import Decimal
import os

DB = "erp-yussyakmal-mrp-test"
SKU = "11055"
mode = os.environ.get("YA_UOM_MODE", "preview").strip().lower()
assert env.cr.dbname == DB, "Wrong database"
assert mode in ("preview", "test", "apply"), "Mode must be preview, test, apply"
assert os.environ.get("YA_APPLY") != "1", "Use YA_UOM_MODE instead"

P = env["product.product"].sudo().with_context(active_test=False)
U = env["uom.uom"].sudo().with_context(active_test=False)
B = env["mrp.bom"].sudo().with_context(active_test=False)
L = env["mrp.bom.line"].sudo().with_context(active_test=False)

product = P.search([("default_code", "=", SKU)])
assert len(product) == 1, f"SKU {SKU}: expected one product, got {len(product)}"
gram = U.search([("name", "=ilike", "Gram")])
assert len(gram) == 1, f"Expected exactly one Gram UoM, got {len(gram)}"
original_uom = product.uom_id
assert gram.name.strip().casefold() == "gram"
assert original_uom.name.strip().casefold() in {"pcs", "gram"}, (
    "Unexpected current base UoM: " + original_uom.name
)
assert B.search_count([]) == 955 and L.search_count([]) == 8502, (
    "Unexpected BoM/component counts; refusing change"
)

lines = L.search([("product_id", "=", product.id)], order="bom_id, sequence, id")
original = [(line.id, line.bom_id.id, line.bom_id.code,
             line.product_qty, line.product_uom_id.id, line.sequence)
            for line in lines]
print("DATABASE:", env.cr.dbname, "MODE:", mode.upper())
print("SKU:", SKU, "PRODUCT:", product.name,
      "CURRENT_UOM:", original_uom.name, "TARGET_UOM:", gram.name)
print("BOM_COMPONENT_REFERENCES:", len(lines))
for line_id, bom_id, code, qty, uom_id, sequence in original:
    print("REFERENCE:", code, "LINE_ID:", line_id, "QTY:", qty,
          "UOM:", U.browse(uom_id).name, "SEQUENCE:", sequence)

# No ledger/operational documents must exist for this SKU. A new UoM must
# not reinterpret quantities already recorded in stock, purchasing or sales.
checks = [
    ("stock.move", "product_id"),
    ("stock.move.line", "product_id"),
    ("stock.quant", "product_id"),
    ("stock.valuation.layer", "product_id"),
    ("mrp.production", "product_id"),
    ("purchase.order.line", "product_id"),
    ("sale.order.line", "product_id"),
]
blockers = []
for model_name, field in checks:
    try:
        model = env[model_name].sudo().with_context(active_test=False)
    except KeyError:
        print("CHECK_NOT_INSTALLED:", model_name)
        continue
    if field not in model._fields:
        print("CHECK_FIELD_UNAVAILABLE:", model_name, field)
        continue
    count = model.search_count([(field, "=", product.id)])
    print("TRANSACTION_CHECK:", model_name, count)
    if count:
        blockers.append(f"{model_name}: {count}")

# Every BOM in which this is the finished product must be reviewed separately:
# deleting a finished BOM to change UoM is NOT an option.
finished = B.search(["|", ("product_id", "=", product.id),
                     "&", ("product_id", "=", False),
                     ("product_tmpl_id", "=", product.product_tmpl_id.id)])
print("BOM_AS_FINISHED_PRODUCT:", len(finished),
      [(b.code, b.product_qty, b.product_uom_id.name) for b in finished])
if finished:
    blockers.append("Product is output of one or more BoMs; needs separate header-UoM handling")
assert not blockers, "BLOCKED: " + "; ".join(blockers)

assert len(lines) == 2, (
    f"Expected exactly two component uses based on prior audit; found {len(lines)}"
)
assert {x[2] for x in original} == {"BOM12499", "BOM12326"}, (
    "Reference BoMs changed; re-audit before correcting"
)
assert all(line.product_uom_id.id == gram.id for line in lines), (
    "Some component UoMs are not Gram; do not auto-convert"
)
assert all(line.product_qty > 0 for line in lines), "Invalid component quantity"

if original_uom.id == gram.id:
    print("ALREADY_CORRECT: no changes needed")
elif mode == "preview":
    print("UOM_CHANGE_PREVIEW_OK: can TEST, no changes made")
else:
    prior_count = L.search_count([])
    prior_bom_count = B.search_count([])
    # Odoo's UoM guard forbids changing the master while BoM component
    # records reference the SKU. Recreate ONLY its two BoM component lines,
    # preserving quantities, units and other copyable values through ORM.
    snapshots = []
    for line in lines:
        values = line.copy_data()[0]
        values.update({
            "bom_id": line.bom_id.id,
            "product_id": product.id,
            "product_qty": line.product_qty,
            "product_uom_id": line.product_uom_id.id,
            "sequence": line.sequence,
        })
        snapshots.append((line.bom_id.id, line.bom_id.code,
                          line.product_qty, line.product_uom_id.id,
                          line.sequence, values))
    try:
        lines.unlink()
        assert L.search_count([("product_id", "=", product.id)]) == 0
        product.write({"uom_id": gram.id})
        assert product.uom_id.id == gram.id, "Product base UoM not updated"
        for _, _, _, _, _, values in snapshots:
            L.create(values)
        env.flush_all()
        updated = L.search([("product_id", "=", product.id)],
                           order="bom_id, sequence, id")
        observed = Counter(
            (x.bom_id.id, str(Decimal(str(x.product_qty))), x.product_uom_id.id,
             x.sequence) for x in updated
        )
        expected = Counter(
            (bid, str(Decimal(str(qty))), uom_id, seq)
            for bid, _, qty, uom_id, seq, _ in snapshots
        )
        assert observed == expected, "Recreated line content differs"
        assert L.search_count([]) == prior_count, "Component total changed"
        assert B.search_count([]) == prior_bom_count, "BoM total changed"
        assert product.uom_id == gram, "Master was not changed"
        print("UOM_CHANGE_VERIFIED: SKU", SKU, "BASE:", product.uom_id.name,
              "RESTORED_LINES:", len(updated),
              "TOTAL_BOMS:", B.search_count([]),
              "TOTAL_LINES:", L.search_count([]))
        if mode == "apply":
            env.cr.commit()
            print("UOM_CHANGE_APPLY_OK COMMITTED")
        else:
            print("UOM_CHANGE_TEST_OK - rolling back")
    except Exception:
        env.cr.rollback()
        print("UOM_CHANGE_FAILED: ROLLED BACK")
        raise
    finally:
        if mode == "test":
            env.cr.rollback()
            env.invalidate_all()
            check_p = P.search([("default_code", "=", SKU)])
            assert check_p.uom_id.id == original_uom.id, "Rollback of product failed"
            assert L.search_count([]) == prior_count, "Rollback of component count failed"
            print("UOM_CHANGE_ROLLBACK_CONFIRMED: original master and lines retained")
