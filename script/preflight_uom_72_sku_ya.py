"""Read-only preflight for YA's private 72-SKU UoM correction decision.

Input CSV: YA_UOM_DECISIONS_CSV (SKU, PRODUCT_NAME, MASTER_UOM, BOM_UOMS).
Runs in Odoo shell only on erp-yussyakmal-mrp-test.
No edits. No commit. Prints exact impacted lines and header quantities.
STOP if stock/transaction references or ambiguity found.
"""
import csv
import os
from collections import Counter, defaultdict
from pathlib import Path

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "Wrong database"
path = Path(os.environ.get("YA_UOM_DECISIONS_CSV", ""))
assert path.is_file(), "Missing private decision CSV"
with path.open(encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    assert {"SKU", "PRODUCT_NAME", "MASTER_UOM", "BOM_UOMS"} <= set(reader.fieldnames or [])
    decisions = [{k: (v or "").strip() for k, v in r.items()} for r in reader]
assert len(decisions) == 72, f"Expected 72 target SKUs, received {len(decisions)}"
assert len({r["SKU"] for r in decisions}) == 72
assert all(r["MASTER_UOM"].casefold() == r["BOM_UOMS"].casefold() for r in decisions)
assert all(r["SKU"] and r["MASTER_UOM"] for r in decisions)

P = env["product.product"].sudo().with_context(active_test=False)
U = env["uom.uom"].sudo().with_context(active_test=False)
B = env["mrp.bom"].sudo().with_context(active_test=False)
L = env["mrp.bom.line"].sudo().with_context(active_test=False)
assert B.search_count([]) == 955 and L.search_count([]) == 8502, "BoM totals changed"
uoms = defaultdict(list)
for u in U.search([]):
    uoms[u.name.strip().casefold()].append(u)
errors = []
blocks = []
impact_lines = 0
impact_headers = 0
transaction_models = [
    "stock.move", "stock.move.line", "stock.quant",
    "mrp.production", "purchase.order.line", "sale.order.line"
]
def check_record(model, pid):
    try:
        m = env[model].sudo().with_context(active_test=False)
        return m.search_count([("product_id", "=", pid)]) if "product_id" in m._fields else "NO_FIELD"
    except KeyError:
        return "NOT_INSTALLED"

print("DATABASE:", env.cr.dbname, "MODE: READ-ONLY PREVIEW")
print("SOURCE_SKUS:", len(decisions))
for index, row in enumerate(decisions, 1):
    sku, wanted = row["SKU"], row["MASTER_UOM"]
    products = P.search([("default_code", "=", sku)])
    choices = uoms[wanted.casefold()]
    if len(products) != 1:
        errors.append(f"{sku}: product count={len(products)}")
        continue
    if len(choices) != 1:
        errors.append(f"{sku}: target UoM {wanted!r} count={len(choices)}")
        continue
    p, target = products[0], choices[0]
    if len(p.product_tmpl_id.product_variant_ids) > 1:
        blocks.append(f"{sku}: template has multiple variants")
    lines = L.search([("product_id", "=", p.id)], order="bom_id, sequence, id")
    output = B.search([
        "|", ("product_id", "=", p.id),
        "&", ("product_id", "=", False),
        ("product_tmpl_id", "=", p.product_tmpl_id.id)
    ], order="code")
    ops = {model: check_record(model, p.id) for model in transaction_models}
    if any(isinstance(v, int) and v > 0 for v in ops.values()):
        blocks.append(f"{sku}: operational refs {ops}")
    if not lines and not output:
        errors.append(f"{sku}: target has no component or finished BoM references")
    mismatched = [line for line in lines if line.product_uom_id.id != target.id]
    mismatch_headers = [bom for bom in output if bom.product_uom_id.id != target.id]
    impact_lines += len(mismatched)
    impact_headers += len(mismatch_headers)
    print(
        "SKU:", sku, "MASTER:", p.uom_id.name, "TARGET:", target.name,
        "COMPONENT_REFS:", len(lines),
        "COMPONENT_CHANGES:", len(mismatched),
        "FINISHED_BOMS:", len(output),
        "HEADER_UOM_CHANGES:", len(mismatch_headers),
        "TRANSACTIONS:", ops
    )
    for line in mismatched:
        print("  COMPONENT_CHANGE:", line.bom_id.code, "LINE_ID:", line.id,
              "BEFORE:", line.product_qty, line.product_uom_id.name,
              "AFTER_TARGET:", line.product_qty, target.name,
              "SAME_NUMBER_NOT_A_PHYSICAL_CONVERSION")
    for bom in mismatch_headers:
        print("  HEADER_CHANGE:", bom.code, "BEFORE:", bom.product_qty,
              bom.product_uom_id.name, "AFTER_TARGET:", bom.product_qty,
              target.name, "SAME_NUMBER_NOT_A_PHYSICAL_CONVERSION")
print("=== SUMMARY ===")
print("DECISIONS:", len(decisions))
print("COMPONENT_LINES_REQUIRING_UOM_CHANGE:", impact_lines)
print("FINISHED_BOM_HEADERS_REQUIRING_UOM_CHANGE:", impact_headers)
print("ERROR_COUNT:", len(errors), "BLOCKER_COUNT:", len(blocks))
for x in errors:
    print("ERROR:", x)
for x in blocks:
    print("BLOCKER:", x)
print("NOTE: This preview does not authorize automatic unit conversion or quantity reinterpretation.")
print("UOM_72_PREFLIGHT_OK" if not errors and not blocks else "UOM_72_PREFLIGHT_NEEDS_REVIEW")
print("NO_DATABASE_CHANGES")
