"""READ ONLY: explain package BoM exceptions and active date/slot routing.

No stock, MO, RO or planning mutation. Run on erp-yussyakmal-mrp-test.
Global published-plan hits do NOT imply same-slot availability.
"""
from collections import Counter, defaultdict
assert env.cr.dbname == "erp-yussyakmal-mrp-test", "TEST DB ONLY"
C = env["product.category"].sudo()
P = env["product.product"].sudo()
B = env["mrp.bom"].sudo()
Planning = env["ya.production.planning"].sudo()
cat = C.search([("complete_name", "=", "All / Produk Jadi / Paket")])
assert len(cat) == 1, "Package category not unique"
pkgs = P.search([("categ_id", "=", cat.id)])
active = Planning.search([("state", "=", "published")])
by_product = defaultdict(list)
by_slot = defaultdict(list)
for plan in active:
    by_slot[(str(plan.delivery_date), plan.slot)].append(plan)
    for row in plan.line_ids:
        if row.max_capacity > 0:
            by_product[row.product_id.id].append((
                str(plan.delivery_date), plan.slot, plan.kitchen_code, row.id))
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_PACKAGE_EXCEPTIONS_AND_SLOT")
print("PACKAGE_COUNT:", len(pkgs))
print("PUBLISHED_DATE_SLOT_COUNTS:", sorted(
    [(d, s, len(v)) for (d, s), v in by_slot.items()])[-30:])
missing = []
other = Counter()
other_examples = defaultdict(list)
nested = []
finished_missing = Counter()
missing_examples = []
bom_kind = Counter()
boms_ok = 0
package_finished_parts = {}
for pkg in pkgs:
    boms = B.search([
        ("active", "=", True),
        ("product_tmpl_id", "=", pkg.product_tmpl_id.id),
        "|", ("product_id", "=", False), ("product_id", "=", pkg.id),
    ])
    if len(boms) != 1:
        missing.append((pkg.default_code, pkg.display_name, len(boms)))
        continue
    bom = boms[0]
    boms_ok += 1
    package_finished_parts[pkg.id] = [
        row.product_id.id for row in bom.bom_line_ids
        if (row.product_id.categ_id.complete_name or '').startswith('All / Produk Jadi /')
        and not (row.product_id.categ_id.complete_name or '').startswith('All / Produk Jadi / Paket')
    ]
    bom_kind[bom.type] += 1
    for row in bom.bom_line_ids:
        comp = row.product_id
        category = comp.categ_id.complete_name or ""
        if category == "All / Produk Jadi / Paket" or category.startswith("All / Produk Jadi / Paket /"):
            nested.append((pkg.default_code, comp.default_code, float(row.product_qty)))
        elif category.startswith("All / Produk Jadi /"):
            if not by_product.get(comp.id):
                finished_missing[comp.default_code or "NO_SKU"] += 1
                if len(missing_examples) < 25:
                    missing_examples.append((pkg.default_code, comp.default_code, category))
        elif category.startswith("All / Konsinyasi Masuk"):
            pass
        elif category.startswith("All / Packaging"):
            pass
        else:
            other[category] += 1
            if len(other_examples[category]) < 8:
                other_examples[category].append((
                    pkg.default_code, comp.default_code,
                    float(row.product_qty), row.product_uom_id.name))
print("VALID_SINGLE_BOM_PACKAGES:", boms_ok)
print("BOM_TYPE_DISTRIBUTION:", sorted(bom_kind.items()))
print("MISSING_OR_AMBIGUOUS_BOM_COUNT:", len(missing))
print("MISSING_OR_AMBIGUOUS_BOM:", missing[:35])
print("NESTED_PACKAGE_COMPONENTS:", nested[:25])
print("OTHER_CATEGORY_COUNTS:", sorted(other.items()))
for name in sorted(other):
    print("OTHER_CATEGORY_EXAMPLES:", name, other_examples[name])
print("FINISHED_WITHOUT_ANY_PUBLISHED_PLANNING_UNIQUE_SKUS:", len(finished_missing))
print("FINISHED_WITHOUT_ANY_PUBLISHED_PLANNING_LINES:", sum(finished_missing.values()))
print("FINISHED_WITHOUT_ANY_PUBLISHED_PLANNING_FREQUENT:", finished_missing.most_common(25))
print("FINISHED_WITHOUT_ANY_PUBLISHED_PLANNING_EXAMPLES:", missing_examples)
# Identify only existing published dates for which a package's finished
# components all have same-date/slot eligible kitchen planning lines.
for (date, slot), plans in sorted(by_slot.items())[-12:]:
    eligible = defaultdict(set)
    for plan in plans:
        for row in plan.line_ids:
            if row.max_capacity > 0:
                eligible[row.product_id.id].add(plan.kitchen_code)
    viable = 0
    missing_route = 0
    ambiguous_route = 0
    for package_id, parts in package_finished_parts.items():
        if any(len(eligible[p]) == 0 for p in parts):
            missing_route += 1
        elif any(len(eligible[p]) > 1 for p in parts):
            ambiguous_route += 1
        else:
            viable += 1
    print("SLOT_ROUTING_SUMMARY:", date, slot,
          "ONE_BOM_PACKAGES_WITH_ALL_FINISHED_COMPONENT_PLANS:", viable,
          "MISSING_ANY_FINISHED_COMPONENT:", missing_route,
          "AMBIGUOUS_COMPONENT_KITCHEN:", ambiguous_route)
print("NOTE: matches only date/slot master data; still validate BoM UoM,")
print("      stock sourcing, nested package, and assembly before using a Paket.")
print("READ_ONLY_PACKAGE_EXCEPTIONS_AND_SLOT_OK")
