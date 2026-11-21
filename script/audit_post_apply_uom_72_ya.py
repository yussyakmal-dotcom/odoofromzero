"""Independent READ-ONLY verification after YA 72-SKU UoM APPLY.

Reads exact private revised-2 decision CSV and checks product master UoM,
every component reference and every finished BoM header for the 72 SKUs.
Also checks global 955/8502 totals and the business rule that no BoM output
is 1 Gram. Zero writes.
"""
import csv
import hashlib
import os
from collections import Counter, defaultdict
from pathlib import Path

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "Wrong DB"
src = Path(os.environ.get("YA_UOM_DECISIONS_CSV", ""))
assert src.is_file(), "Missing CSV"
assert src.name == "YA_UOM_KOREKSI_72_SKU_REVISI_2.csv", "Wrong CSV filename"
EXPECTED_SHA256 = "5e120a0057a8c73c10abdef83b9def3eb1e94844da574d796bd16945f85c2d38"
assert hashlib.sha256(src.read_bytes()).hexdigest() == EXPECTED_SHA256, "Wrong CSV contents"
with src.open(encoding="utf-8-sig", newline="") as handle:
    decisions = [{k: (v or "").strip() for k, v in r.items()}
                 for r in csv.DictReader(handle)]
assert len(decisions) == 72
assert len({r["SKU"] for r in decisions}) == 72

P = env["product.product"].sudo().with_context(active_test=False)
B = env["mrp.bom"].sudo().with_context(active_test=False)
L = env["mrp.bom.line"].sudo().with_context(active_test=False)
assert B.search_count([]) == 955, "Unexpected BoM count"
assert L.search_count([]) == 8502, "Unexpected component count"

issues = []
checked_lines = set()
checked_boms = set()
for r in decisions:
    sku = r["SKU"]
    products = P.search([("default_code", "=", sku)])
    if len(products) != 1:
        issues.append(f"{sku}: expected 1 product, got {len(products)}")
        continue
    product = products[0]
    wanted_master = r["MASTER_UOM"].casefold()
    wanted_bom = r["BOM_UOMS"].casefold()
    if product.uom_id.name.strip().casefold() != wanted_master:
        issues.append(f"{sku}: MASTER {product.uom_id.name} != {r['MASTER_UOM']}")
    for line in L.search([("product_id", "=", product.id)]):
        checked_lines.add(line.id)
        if line.product_uom_id.name.strip().casefold() != wanted_bom:
            issues.append(f"{sku}: COMPONENT line {line.id} UoM {line.product_uom_id.name} != {r['BOM_UOMS']}")
    headers = B.search([
        "|", ("product_id", "=", product.id),
        "&", ("product_id", "=", False),
        ("product_tmpl_id", "=", product.product_tmpl_id.id)
    ])
    for bom in headers:
        checked_boms.add(bom.id)
        if bom.product_uom_id.name.strip().casefold() != wanted_bom:
            issues.append(f"{sku}: HEADER {bom.code} UoM {bom.product_uom_id.name} != {r['BOM_UOMS']}")
        if abs(bom.product_qty - 1.0) < 1e-9 and bom.product_uom_id.name.strip().casefold() in {"gram", "g", "gr"}:
            issues.append(f"{sku}: HEADER {bom.code} violates qty 1 Gram rule")

global_bad = B.search([]).filtered(
    lambda b: abs(b.product_qty - 1.0) < 1e-9
    and b.product_uom_id.name.strip().casefold() in {"gram", "g", "gr"}
)
for bom in global_bad:
    issues.append(f"GLOBAL: Header {bom.code} output 1 Gram")

print("DATABASE:", env.cr.dbname)
print("MODE: INDEPENDENT READ-ONLY POST-APPLY")
print("CSV_SHA256:", EXPECTED_SHA256)
print("DECISION_SKUS:", len(decisions))
print("TOTAL_BOMS:", B.search_count([]))
print("TOTAL_COMPONENTS:", L.search_count([]))
print("INSPECTED_COMPONENT_REFERENCES:", len(checked_lines))
print("INSPECTED_FINISHED_BOM_HEADERS:", len(checked_boms))
print("GLOBAL_QTY_ONE_GRAM:", len(global_bad))
print("ISSUE_COUNT:", len(issues))
for issue in issues[:150]:
    print("ISSUE:", issue)
print("POST_APPLY_72_AUDIT_OK" if not issues else "POST_APPLY_72_AUDIT_FAILED")
assert not issues, f"Audit detected {len(issues)} mismatches"
print("NO_DATABASE_CHANGES")
