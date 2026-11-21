"""SHA-LOCKED APPLY of 72 YA product/BoM UoM corrections.

Input: YA_UOM_DECISIONS_CSV=/private/review/YA_UOM_KOREKSI_72_SKU.csv
Run via Odoo 19 shell on erp-yussyakmal-mrp-test.
Requires exact revised-2 CSV and YA_UOM_MODE=apply.
Keep numeric quantities unchanged as explicitly specified in decisions.
Changing kg -> Toples, for example, is NOT a real mass-to-package conversion.
"""
import csv
import hashlib
import os
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "Incorrect database"
assert os.environ.get("YA_UOM_MODE") == "apply", "Explicit YA_UOM_MODE=apply required"
source = Path(os.environ.get("YA_UOM_DECISIONS_CSV", ""))
assert source.is_file(), "Decision CSV missing"
EXPECTED_SHA256 = "5e120a0057a8c73c10abdef83b9def3eb1e94844da574d796bd16945f85c2d38"
actual_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()
assert source.name == "YA_UOM_KOREKSI_72_SKU_REVISI_2.csv", "Wrong revision filename"
assert actual_sha256 == EXPECTED_SHA256, (
    f"WRONG_CSV_REVISION: {actual_sha256}, expected {EXPECTED_SHA256}"
)
with source.open(encoding="utf-8-sig", newline="") as stream:
    reader = csv.DictReader(stream)
    assert {"SKU", "PRODUCT_NAME", "MASTER_UOM", "BOM_UOMS"} <= set(reader.fieldnames or [])
    rows = [{k: (v or "").strip() for k, v in row.items()} for row in reader]
assert len(rows) == 72 and len({x["SKU"] for x in rows}) == 72
assert all(x["MASTER_UOM"].casefold() == x["BOM_UOMS"].casefold() for x in rows)
decisions_by_sku = {x["SKU"]: x for x in rows}
assert (decisions_by_sku["10473"]["MASTER_UOM"], decisions_by_sku["10473"]["BOM_UOMS"]) == ("Resep", "Resep")
assert (decisions_by_sku["11074"]["MASTER_UOM"], decisions_by_sku["11074"]["BOM_UOMS"]) == ("Pcs", "Pcs")

P = env["product.product"].sudo().with_context(active_test=False)
U = env["uom.uom"].sudo().with_context(active_test=False)
B = env["mrp.bom"].sudo().with_context(active_test=False)
L = env["mrp.bom.line"].sudo().with_context(active_test=False)
assert B.search_count([]) == 955 and L.search_count([]) == 8502

units = defaultdict(list)
for u in U.search([]):
    units[u.name.strip().casefold()].append(u)

transaction_models = ["stock.move", "stock.move.line", "stock.quant",
                      "mrp.production", "purchase.order.line", "sale.order.line"]
targets = {}
for row in rows:
    sku = row["SKU"]
    products = P.search([("default_code", "=", sku)])
    target = units[row["MASTER_UOM"].casefold()]
    assert len(products) == 1, f"Product SKU not unique: {sku}"
    assert len(target) == 1, f"Target UoM not unique: {sku}, {row['MASTER_UOM']}"
    product, unit = products[0], target[0]
    assert len(product.product_tmpl_id.product_variant_ids) == 1, (
        f"{sku}: multiple product variants, unsafe to change template UoM")
    for model_name in transaction_models:
        try:
            model = env[model_name].sudo().with_context(active_test=False)
        except KeyError:
            continue
        if "product_id" in model._fields:
            assert not model.search_count([("product_id", "=", product.id)]), (
                f"{sku}: transaction exists in {model_name}")
    targets[product.id] = (sku, product, unit)

# Store ALL existing BOM line signatures, not just count, to detect accidental
# merges, deletions, changes in quantity or UoM on unrelated components.
def signature(line):
    return (line.bom_id.id, line.product_id.id,
            str(Decimal(str(line.product_qty))), line.product_uom_id.id,
            line.sequence)
before_lines = Counter(signature(line) for line in L.search([]))
before_bom_data = {
    b.id: (b.code, b.product_id.id, b.product_tmpl_id.id,
           str(Decimal(str(b.product_qty))), b.product_uom_id.id,
           b.picking_type_id.id, b.type)
    for b in B.search([])
}
original_units = {pid: record.uom_id.id for pid, (_, record, _) in targets.items()}
wanted_uom = {pid: target.id for pid, (_, _, target) in targets.items()}

# Only explicitly affected line UoMs should change. All quantities remain
# numerically unchanged. Include ALL references to changed product masters,
# even when their BoM UoM was already the requested target.
lines_to_detach = L.search([("product_id", "in", list(targets))], order="bom_id,sequence,id")
affected_header = B.search([
    "|", ("product_id", "in", list(targets)),
    "&", ("product_id", "=", False),
    ("product_tmpl_id", "in", [p.product_tmpl_id.id for _, p, _ in targets.values()])
])
# Header with product_id=False can ambiguously cover templates; preflight
# confirmed 1 variant per template.
target_by_template = {p.product_tmpl_id.id: unit.id for _, p, unit in targets.values()}

expected_lines = Counter()
for sig, count in before_lines.items():
    bom_id, product_id, qty, unit_id, sequence = sig
    expected_lines[(bom_id, product_id, qty, wanted_uom.get(product_id, unit_id), sequence)] += count
expected_boms = {}
for bom_id, data in before_bom_data.items():
    code, product_id, tmpl_id, qty, old_uom_id, picking_id, btype = data
    new_unit_id = (wanted_uom.get(product_id)
                   or (target_by_template.get(tmpl_id) if product_id == 0 else None)
                   or old_uom_id)
    expected_boms[bom_id] = (code, product_id, tmpl_id, qty,
                             new_unit_id, picking_id, btype)

modified_lines = sum(
    1 for line in lines_to_detach
    if line.product_uom_id.id != wanted_uom[line.product_id.id]
)
modified_headers = sum(
    1 for bom in affected_header
    if bom.product_uom_id.id !=
       (wanted_uom.get(bom.product_id.id) or target_by_template[bom.product_tmpl_id.id])
)
changed_products = sum(
    1 for pid, (_, p, unit) in targets.items() if p.uom_id.id != unit.id
)
print("DATABASE:", env.cr.dbname, "MODE: GUARDED APPLY")
print("DECISION_CSV_SHA256:", actual_sha256)
print("DECISION_SKUS:", len(targets))
print("PRODUCT_MASTER_CHANGES:", changed_products)
print("COMPONENT_REFERENCES_RECREATED:", len(lines_to_detach))
print("COMPONENT_UOM_CHANGES:", modified_lines)
print("FINISHED_BOM_HEADERS_REFERENCED:", len(affected_header))
print("FINISHED_BOM_HEADER_UOM_CHANGES:", modified_headers)
print("WARNING: numeric quantities stay unchanged; no physical conversion inferred")

# Odoo's native product UoM update expects each finished-product BoM
# header to be expressed in the OLD product UoM. Some imported headers are
# already expressed in the target UoM, while the master still uses the old
# unit. Record the exact headers needing temporary realignment, preserving
# all original quantities for end-to-end verification.
temporary_header_alignment = []
for bom in affected_header:
    matching = targets.get(bom.product_id.id)
    if not matching:
        matching = next((entry for entry in targets.values()
                         if entry[1].product_tmpl_id.id == bom.product_tmpl_id.id), None)
    assert matching, f"No target for finished BoM {bom.code}"
    sku, product, new_uom = matching
    if product.uom_id.id != new_uom.id and bom.product_uom_id.id != product.uom_id.id:
        # The pre-existing BoM header can use a THIRD unit (for example
        # Pcs vs old Resep vs approved target Bungkus). This is an approved revision-2
        # transformation and NOT an endorsement of their physical equality.
        # The final quantity and target UoM are checked against the full
        # expected data signatures; any ORM adjustment fails the test.
        temporary_header_alignment.append((bom, product.uom_id.id, sku,
                                            bom.product_uom_id.name,
                                            new_uom.name, bom.product_qty))
print("TEMPORARY_HEADER_ALIGNMENT:", len(temporary_header_alignment))
print("THIRD_UNIT_HEADERS:", sum(
    current.casefold() != target.casefold()
    for _, _, _, current, target, _ in temporary_header_alignment
))
for bom, old_id, sku, original_name, target_name, original_qty in temporary_header_alignment:
    print("  ALIGN:", bom.code, "SKU:", sku,
          "HEADER:", original_name,
          "OLD_MASTER:", U.browse(old_id).name,
          "TARGET:", target_name,
          "QTY_HELD:", original_qty)
line_values = []
for line in lines_to_detach:
    data = line.copy_data()[0]
    data.update({
        "bom_id": line.bom_id.id,
        "product_id": line.product_id.id,
        "product_qty": line.product_qty,
        "product_uom_id": wanted_uom[line.product_id.id],
        "sequence": line.sequence,
    })
    line_values.append(data)

passed = False
try:
    # Temporarily detach lines so Odoo's product-UoM change guard does not
    # reject an otherwise unused product simply because it is in a BoM.
    lines_to_detach.unlink()
    assert L.search_count([]) == 8502 - len(line_values)
    # Temporarily align previously mismatched finished BoM headers with the
    # OLD master UoM so Odoo's own _update_uom can make the target change.
    # We do not recalculate quantities. The complete final signatures are
    # compared against originals/approved targets below.
    for bom, old_id, sku, original_name, target_name, original_qty in temporary_header_alignment:
        bom.write({"product_uom_id": old_id})
        assert abs(bom.product_qty - original_qty) < 1e-9, (
            f"Temporary alignment unexpectedly changed quantity: {bom.code}"
        )
        print("TEMP_HEADER_ALIGNED:", bom.code, "SKU:", sku)
    # IMPORTANT (Odoo 19): product._update_uom() checks the units of
    # existing finished-product BoM headers AGAINST THE OLD MASTER UOM,
    # then rewrites those headers itself to the new UoM.
    # Changing BoM header UoMs BEFORE changing master triggers UserError.
    # Because all component references have been detached above, update
    # masters FIRST and allow Odoo to update related BoM headers natively.
    for sku, product, new_unit in targets.values():
        if product.uom_id.id != new_unit.id:
            print("UPDATING_MASTER:", sku, product.uom_id.name, "->", new_unit.name)
            product.write({"uom_id": new_unit.id})
    # Handle BoM headers whose product master was ALREADY at target but
    # header was still different. This cannot interfere with a master write
    # because master changes have completed.
    for bom in affected_header:
        next_uom = (wanted_uom.get(bom.product_id.id)
                    or target_by_template[bom.product_tmpl_id.id])
        if bom.product_uom_id.id != next_uom:
            bom.write({"product_uom_id": next_uom})
    # Restore each component as its own row, preserving duplicates and qty.
    for data in line_values:
        L.create(data)
    env.flush_all()

    assert B.search_count([]) == 955, "BoM count changed"
    assert L.search_count([]) == 8502, "Component line count changed"
    assert all(p.uom_id.id == u.id for _, p, u in targets.values()), (
        "At least one master UoM did not change"
    )
    actual_lines = Counter(signature(line) for line in L.search([]))
    assert actual_lines == expected_lines, (
        "BoM lines differ beyond the explicitly requested unit changes"
    )
    actual_boms = {
        b.id: (b.code, b.product_id.id, b.product_tmpl_id.id,
               str(Decimal(str(b.product_qty))), b.product_uom_id.id,
               b.picking_type_id.id, b.type)
        for b in B.search([])
    }
    assert actual_boms == expected_boms, (
        "BoM headers differ beyond the requested output unit changes"
    )
    gram_headers = B.search([]).filtered(
        lambda bom: abs(bom.product_qty - 1.0) < 1e-9
        and bom.product_uom_id.name.strip().casefold() in {"gram", "g", "gr"}
    )
    assert not gram_headers, (
        "BUSINESS_RULE_FAIL: qty 1 Gram on: "
        + ", ".join(bom.code or str(bom.id) for bom in gram_headers)
    )
    print("FINAL_QTY_ONE_GRAM_FINDINGS: 0")
    print("UOM_72_BULK_VERIFIED: 72 SKU, 955 BoMs, 8502 components")
    env.cr.commit()
    passed = True
    print("UOM_72_APPLY_OK COMMITTED")
except BaseException:
    if not passed:
        env.cr.rollback()
        env.invalidate_all()
        print("UOM_72_APPLY_FAILED_ROLLBACK_CONFIRMED")
    raise
