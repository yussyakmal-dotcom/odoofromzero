"""Audit and classify ALL YA component UoM mismatches per SKU; READ ONLY.

Run inside Odoo shell in erp-yussyakmal-mrp-test. Produces a private
semicolon-delimited CSV report (not stored in public Git). It does NOT
change product master, BoMs, stock, or transactions.

Never automatically infer that 1 Gram = 1 Pcs just because Odoo's current
UoM implementation accepts the conversion.
"""
import csv
import os
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path

DB = "erp-yussyakmal-mrp-test"
assert env.cr.dbname == DB, "Only MRP test database is allowed"
target = Path(os.environ.get(
    "YA_UOM_REVIEW_CSV", "/var/lib/odoo19/import/review_component_uom_ya.csv"
))
assert target.parent.is_dir(), f"Output folder unavailable: {target.parent}"

B = env["mrp.bom"].sudo().with_context(active_test=False)
L = env["mrp.bom.line"].sudo().with_context(active_test=False)
P = env["product.product"].sudo().with_context(active_test=False)
assert B.search_count([]) == 955, "BoM count changed; inspect before using report"
assert L.search_count([]) == 8502, "Component count changed; inspect before using report"

def family(uom):
    # These are business-review categories only; not Odoo's conversion logic.
    token = str(uom.name).strip().casefold().replace(" ", "").replace(".", "")
    mass = {"gram", "g", "gr", "kg", "kilogram", "mg", "miligram"}
    volume = {"ml", "milliliter", "millilitre", "l", "liter", "litre", "cc"}
    count = {"pcs", "pc", "piece", "pieces", "butir", "buah", "botol", "paket",
             "lembar", "ikat", "toples", "pack", "kotak", "kaleng"}
    recipes = {"resep", "batch"}
    if token in mass:
        return "MASS"
    if token in volume:
        return "VOLUME"
    if token in count:
        return "COUNT"
    if token in recipes:
        return "RECIPE"
    return "OTHER"

per_product = defaultdict(list)
matched = 0
different = 0
errors = 0
for line in L.search([], order="product_id, bom_id, sequence, id"):
    product = line.product_id
    component_uom = line.product_uom_id
    base_uom = product.uom_id
    if component_uom.id == base_uom.id:
        matched += 1
        continue
    different += 1
    try:
        converted = component_uom._compute_quantity(
            line.product_qty, base_uom, raise_if_failure=True)
        conversion = f"{converted:.10g}"
        if converted <= 0:
            raise ValueError(f"nonpositive {converted}")
        factor = component_uom._compute_quantity(
            1, base_uom, raise_if_failure=True)
        factor_text = f"{factor:.10g}"
    except Exception as exc:
        errors += 1
        conversion = "ERROR: " + str(exc)
        factor_text = "ERROR"
    per_product[product.id].append({
        "sku": product.default_code or "",
        "name": product.name,
        "bom_code": line.bom_id.code or "",
        "line_id": line.id,
        "uom_name": component_uom.name,
        "uom_id": component_uom.id,
        "master_name": base_uom.name,
        "master_id": base_uom.id,
        "qty": line.product_qty,
        "base_qty": conversion,
        "factor": factor_text,
        "family_bom": family(component_uom),
        "family_master": family(base_uom),
    })

def count_refs(model_name, product_id):
    try:
        model = env[model_name].sudo().with_context(active_test=False)
    except KeyError:
        return "not_installed"
    if "product_id" not in model._fields:
        return "not_applicable"
    return str(model.search_count([("product_id", "=", product_id)]))

fieldnames = [
    "SKU", "PRODUCT_NAME", "MASTER_UOM", "BOM_UOMS",
    "DIFFERENT_BOM_LINES", "DIFFERENT_BOMS",
    "CROSS_FAMILY_LINES", "CONVERSION_ERROR_LINES",
    "SAMPLE_BOM_CODES", "LINE_DETAILS", "PROPOSED_HANDLING",
    "STOCK_MOVES", "STOCK_MOVE_LINES", "STOCK_QUANTS", "MANUFACTURING_ORDERS",
    "PURCHASE_LINES", "SALES_LINES", "BOM_AS_FINISHED_PRODUCT"
]
out = []
counts = Counter()
for product_id, entries in sorted(
    per_product.items(), key=lambda item: (item[1][0]["sku"], item[0])
):
    product = P.browse(product_id)
    cross = sum(
        x["family_bom"] != x["family_master"] and
        "OTHER" not in (x["family_bom"], x["family_master"])
        for x in entries
    )
    bad = sum(x["factor"] == "ERROR" for x in entries)
    if bad:
        handling = "BLOCKED_CONVERSION_FAILED"
    elif cross:
        handling = "REVIEW_MASTER_OR_BOM_MEANING"
    elif any(x["family_bom"] == "OTHER" or x["family_master"] == "OTHER"
             for x in entries):
        handling = "REVIEW_UNCLASSIFIED_UNIT"
    else:
        handling = "REVIEW_EQUIVALENT_OR_CONVERTIBLE"
    counts[handling] += 1
    # Protect finished-product BoMs; changing product UoM may also affect header.
    finished = B.search_count([
        "|", ("product_id", "=", product_id),
        "&", ("product_id", "=", False),
        ("product_tmpl_id", "=", product.product_tmpl_id.id)
    ])
    detail = " || ".join(
        f'{x["bom_code"]}:{x["qty"]} {x["uom_name"]} '
        f'-> {x["base_qty"]} {x["master_name"]} (factor={x["factor"]})'
        for x in entries
    )
    out.append({
        "SKU": entries[0]["sku"],
        "PRODUCT_NAME": entries[0]["name"],
        "MASTER_UOM": entries[0]["master_name"],
        "BOM_UOMS": ", ".join(sorted(set(x["uom_name"] for x in entries))),
        "DIFFERENT_BOM_LINES": len(entries),
        "DIFFERENT_BOMS": len(set(x["bom_code"] for x in entries)),
        "CROSS_FAMILY_LINES": cross,
        "CONVERSION_ERROR_LINES": bad,
        "SAMPLE_BOM_CODES": ", ".join(
            sorted({x["bom_code"] for x in entries})[:12]),
        "LINE_DETAILS": detail,
        "PROPOSED_HANDLING": handling,
        "STOCK_MOVES": count_refs("stock.move", product_id),
        "STOCK_MOVE_LINES": count_refs("stock.move.line", product_id),
        "STOCK_QUANTS": count_refs("stock.quant", product_id),
        "MANUFACTURING_ORDERS": count_refs("mrp.production", product_id),
        "PURCHASE_LINES": count_refs("purchase.order.line", product_id),
        "SALES_LINES": count_refs("sale.order.line", product_id),
        "BOM_AS_FINISHED_PRODUCT": finished,
    })

with target.open("w", encoding="utf-8-sig", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=fieldnames, delimiter=";")
    writer.writeheader()
    writer.writerows(out)
os.chmod(target, 0o600)

print("DATABASE:", env.cr.dbname)
print("MODE: READ-ONLY REVIEW GENERATION")
print("TOTAL_COMPONENT_LINES:", L.search_count([]))
print("EXACT_COMPONENT_LINES:", matched)
print("DIFFERENT_COMPONENT_LINES:", different)
print("DIFFERENT_SKUS:", len(out))
print("CONVERSION_ERROR_LINES:", errors)
for category in sorted(counts):
    print("CATEGORY:", category, counts[category])
print("REVIEW_CSV:", str(target))
print("=== CROSS-FAMILY SKUS (REVIEW FIRST) ===")
for item in out:
    if item["CROSS_FAMILY_LINES"]:
        print("REVIEW:", item["SKU"], "|", item["PRODUCT_NAME"],
              "| MASTER", item["MASTER_UOM"], "| BOM", item["BOM_UOMS"],
              "| LINES", item["DIFFERENT_BOM_LINES"],
              "| MOVES", item["STOCK_MOVES"],
              "| FINISHED_BOMS", item["BOM_AS_FINISHED_PRODUCT"])
print("UOM_REVIEW_REPORT_OK: no database changes")
