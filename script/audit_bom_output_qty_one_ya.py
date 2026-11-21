"""Read-only audit: BoM output qty=1 must NOT use Gram (YA business rule).

Checks all 955 finished BoM headers and the private 72-SKU decision CSV
(including 10473->Resep). Does not infer whether Resep or Bungkus is right.
No writes, no commit. Creates private CSV report and prints concise findings.

Usage: Odoo shell with YA_UOM_DECISIONS_CSV and YA_BOM_ONE_REPORT_CSV.
"""
import csv
import os
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "MRP test database only"
# Decision CSV is optional: an independent audit of all actual BoM headers
# must still work when the local revised CSV has not been installed yet.
raw_input = os.environ.get("YA_UOM_DECISIONS_CSV", "").strip()
input_path = Path(raw_input) if raw_input else None
report_path = Path(os.environ.get(
    "YA_BOM_ONE_REPORT_CSV",
    "/var/lib/odoo19/import/audit_bom_output_qty_one_ya.csv"
))
assert report_path.parent.is_dir(), "Report folder not found"
by_sku = {}
if input_path and input_path.is_file():
    with input_path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        assert {"SKU", "PRODUCT_NAME", "MASTER_UOM", "BOM_UOMS"} <= set(reader.fieldnames or [])
        decisions = list(reader)
    decisions = [{k: (v or "").strip() for k, v in r.items()} for r in decisions]
    assert len(decisions) == 72, f"Expected 72 decisions, found {len(decisions)}"
    by_sku = {r["SKU"]: r for r in decisions}
    assert len(by_sku) == 72, "Duplicate SKU in decision CSV"
    assert by_sku["10473"]["MASTER_UOM"].casefold() == "resep", (
        "Decision CSV is outdated: SKU 10473 master must be Resep"
    )
    assert by_sku["10473"]["BOM_UOMS"].casefold() == "resep", (
        "Decision CSV is outdated: SKU 10473 BoM must be Resep"
    )
    print("DECISION_CSV_STATUS: LOADED", input_path)
else:
    print("DECISION_CSV_STATUS: NOT_LOADED")
    if input_path:
        print("DECISION_CSV_NOT_FOUND:", input_path)
    print("INFO: audit will check actual BoM headers only; planned 72-SKU targets NOT checked")


B = env["mrp.bom"].sudo().with_context(active_test=False)
L = env["mrp.bom.line"].sudo().with_context(active_test=False)
P = env["product.product"].sudo().with_context(active_test=False)
assert B.search_count([]) == 955 and L.search_count([]) == 8502, (
    "BoM totals changed; stop and investigate"
)

def is_one(qty):
    return abs(float(qty) - 1.0) < 1e-9

def is_gram(unit):
    return unit and unit.name.strip().casefold() in {"gram", "g", "gr"}

def sku_from_bom(bom):
    product = bom.product_id
    if not product:
        variants = bom.product_tmpl_id.product_variant_ids
        if len(variants) != 1:
            return "", False
        product = variants[0]
    return product.default_code or "", True

def affected_bom_lines(product):
    return L.search_count([("product_id", "=", product.id)])

findings = []
counts = Counter()
bom_by_sku = defaultdict(list)
for bom in B.search([], order="code,id"):
    sku, unique = sku_from_bom(bom)
    product_name = bom.product_tmpl_id.name or ""
    decision = by_sku.get(sku)
    current_uom = bom.product_uom_id
    proposed = decision["BOM_UOMS"] if decision else current_uom.name
    flag_current = is_one(bom.product_qty) and is_gram(current_uom)
    flag_target = is_one(bom.product_qty) and proposed.strip().casefold() in {"gram", "g", "gr"}
    if unique:
        bom_by_sku[sku].append(bom)
    if not flag_current and not flag_target:
        continue
    if flag_current and flag_target:
        status = "CURRENT_AND_TARGET_GRAM_QTY_ONE"
    elif flag_current:
        status = "CURRENT_GRAM_QTY_ONE_TARGET_OTHER"
    else:
        status = "TARGET_GRAM_QTY_ONE"
    findings.append({
        "STATUS": status, "SKU": sku, "PRODUCT_NAME": product_name,
        "BOM_CODE": bom.code or "", "BOM_ID": bom.id,
        "OUTPUT_QTY": bom.product_qty, "CURRENT_BOM_UOM": current_uom.name,
        "CURRENT_MASTER_UOM": (
            bom.product_id.uom_id.name if bom.product_id else
            bom.product_tmpl_id.uom_id.name),
        "TARGET_BOM_UOM": proposed,
        "TARGET_MASTER_UOM": decision["MASTER_UOM"] if decision else "",
        "SKU_IN_72_DECISIONS": "YES" if decision else "NO",
        "SUGGESTED_ACTION": "VERIFY_RESEP_OR_BUNGKUS; do not infer automatically",
    })
    counts[status] += 1

# Some SKUs may not have their own finished BoM but still be components in
# others: report any approved Gram target that would affect a finished BoM
# output=1 (the checks above already handle all mapped finished BoMs).
missing = sorted(sku for sku in by_sku if sku not in bom_by_sku)
fields = [
    "STATUS","SKU","PRODUCT_NAME","BOM_CODE","BOM_ID","OUTPUT_QTY",
    "CURRENT_BOM_UOM","CURRENT_MASTER_UOM",
    "TARGET_BOM_UOM","TARGET_MASTER_UOM","SKU_IN_72_DECISIONS",
    "SUGGESTED_ACTION",
]
with report_path.open("w", encoding="utf-8-sig", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=fields, delimiter=";")
    writer.writeheader()
    writer.writerows(findings)
os.chmod(report_path, 0o600)

print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY")
print("RULE: OUTPUT_QTY=1 must not be Gram; choose Resep or Bungkus after business review")
print("BOM_TOTAL:", B.search_count([]))
print("COMPONENT_TOTAL:", L.search_count([]))
print("DECISION_SKUS:", len(by_sku))
print("TARGET_COMPARISON:", "ENABLED" if by_sku else "DISABLED")
print("SKUS_WITHOUT_OWN_FINISHED_BOM:", len(missing))
print("FINDING_COUNT:", len(findings))
for status, qty in sorted(counts.items()):
    print("CATEGORY:", status, qty)
for f in findings:
    print("FLAG:", f["STATUS"], "SKU:", f["SKU"], "BOM:", f["BOM_CODE"],
          "QTY:", f["OUTPUT_QTY"], "CURRENT:", f["CURRENT_BOM_UOM"],
          "TARGET:", f["TARGET_BOM_UOM"], "IN_72:", f["SKU_IN_72_DECISIONS"])
print("REPORT_CSV:", report_path)
print("AUDIT_BOM_ONE_OK: no database changes")
