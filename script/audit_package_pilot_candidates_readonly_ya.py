"""READ ONLY: identify simple, unambiguous Paket pilots for 2026-11-24 S1.

Pilot = package category exact, one active normal BOM, no nested/raw/WIP,
positive whole-unit BoM output and component requirement in base UoM,
one matching published kitchen Planning line per produced FG component
for same delivery date/slot. Consignment/packaging components are allowed
but sourced externally; a pilot is NOT proven to have PCK stock.
No RO / MO / stock / BoM writes.
"""
from collections import defaultdict, Counter
from odoo.tools.float_utils import float_compare
assert env.cr.dbname == "erp-yussyakmal-mrp-test", "TEST DB ONLY"
date = "2026-11-24"
slot = "S1"
Cat = env["product.category"].sudo()
Product = env["product.product"].sudo()
BoM = env["mrp.bom"].sudo()
Plan = env["ya.production.planning"].sudo()
category = Cat.search([("complete_name", "=", "All / Produk Jadi / Paket")])
assert len(category) == 1, "Package category ambiguous"
packages = Product.search([("categ_id", "=", category.id)])
plans = Plan.search([("delivery_date", "=", date), ("slot", "=", slot),
                     ("state", "=", "published")])
routes = defaultdict(list)
for plan in plans:
    for line in plan.line_ids:
        if line.max_capacity > 0:
            routes[line.product_id.id].append((plan, line))
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_PACKAGE_PILOT_CANDIDATES")
print("TARGET_DATE_SLOT:", date, slot, "PUBLISHED_PLANS:", len(plans))
print("PACKAGE_SKUS:", len(packages))
reasons = Counter()
examples = defaultdict(list)
viable = []
def reject(code, sku, detail):
    reasons[code] += 1
    if len(examples[code]) < 12:
        examples[code].append((sku, detail))
for package in packages:
    code = package.default_code or str(package.id)
    boms = BoM.search([
        ("active", "=", True), ("type", "=", "normal"),
        ("product_tmpl_id", "=", package.product_tmpl_id.id),
        "|", ("product_id", "=", False), ("product_id", "=", package.id),
    ])
    if len(boms) != 1:
        reject("MISSING_OR_AMBIGUOUS_BOM", code, len(boms))
        continue
    bom = boms[0]
    if not bom.bom_line_ids or not bom.product_qty or bom.product_qty <= 0:
        reject("INVALID_BOM_OUTPUT", code, bom.id)
        continue
    try:
        output = bom.product_uom_id._compute_quantity(
            bom.product_qty, package.uom_id, round=False)
    except Exception as exc:
        reject("PACKAGE_OUTPUT_UOM_ERROR", code, type(exc).__name__)
        continue
    if float_compare(output, 1.0, precision_rounding=package.uom_id.rounding) != 0:
        reject("NOT_SINGLE_UNIT_BOM_OUTPUT", code, output)
        continue
    manufactured = {}
    other = {}
    flagged = None
    for row in bom.bom_line_ids:
        component = row.product_id
        cname = component.categ_id.complete_name or ""
        try:
            qty = row.product_uom_id._compute_quantity(
                row.product_qty, component.uom_id, round=False)
        except Exception as exc:
            flagged = ("COMPONENT_UOM_ERROR", component.default_code)
            break
        rounded = round(qty)
        if qty <= 0 or abs(qty-rounded) > 1e-7:
            flagged = ("FRACTIONAL_COMPONENT_BASE_UOM", component.default_code)
            break
        if cname.startswith("All / Produk Jadi / Paket"):
            flagged = ("NESTED_PACKAGE", component.default_code)
            break
        if cname.startswith("All / Produk Jadi /"):
            matches = routes.get(component.id, [])
            if len(matches) != 1:
                flagged = ("MISSING_OR_AMBIGUOUS_SLOT_ROUTE", component.default_code)
                break
            plan, planning_line = matches[0]
            if planning_line.uom_id != component.uom_id:
                flagged = ("PLANNING_COMPONENT_UOM_MISMATCH", component.default_code)
                break
            manufactured[component.default_code] = (
                int(rounded), plan.kitchen_code, planning_line.max_capacity)
        elif cname.startswith("All / Konsinyasi Masuk"):
            other[component.default_code] = (int(rounded), "CONSIGNMENT")
        elif cname.startswith("All / Packaging"):
            other[component.default_code] = (int(rounded), "PACKAGING")
        else:
            flagged = ("OTHER_COMPONENT_CATEGORY", cname)
            break
    if flagged:
        reject(flagged[0], code, flagged[1])
        continue
    viable.append((code, package.display_name, bom.id,
                   manufactured, other))
print("STRICT_PILOT_CANDIDATE_COUNT:", len(viable))
for item in viable[:20]:
    print("PILOT:", item)
print("EXCLUSION_REASONS:", sorted(reasons.items()))
for key in sorted(examples):
    print("EXCLUSION_EXAMPLES:", key, examples[key])
print("NOTE: this is a structural pilot check, not PCK component stock,")
print("      assembly operation type, RO upload or multi-store allocation proof.")
print("READ_ONLY_PACKAGE_PILOT_CANDIDATES_OK")
