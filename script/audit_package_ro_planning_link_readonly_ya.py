"""READ ONLY: inspect Package category ↔ RO / Published Planning ↔ kitchen BoM.

Scope is deliberately diagnostic. NO stock moves/MOs/writes. Run only on
erp-yussyakmal-mrp-test. Resolve integration gaps before changing stable RO.
"""
from collections import Counter

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "REFUSED: wrong database"
Category = env["product.category"].sudo()
Product = env["product.product"].sudo()
Planning = env["ya.production.planning"].sudo()
RO = env["ya.store.ro"].sudo()
Bom = env["mrp.bom"].sudo()
cat = Category.search([("complete_name", "=", "All / Produk Jadi / Paket")])
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_PACKAGE_RO_PLANNING_LINK")
print("PACKAGE_CATEGORY_MATCHES:", len(cat))
if len(cat) != 1:
    print("BLOCKER: identify unique package category before change")
else:
    packages = Product.search([("categ_id", "=", cat.id)])
    ids = set(packages.ids)
    print("PACKAGE_SKU_COUNT:", len(packages))
    print("ACTIVE_PUBLISHED_PLAN_COUNT:", Planning.search_count([("state", "=", "published")]))
    stats = Counter()
    examples = []
    # Only published Planning lines: active source for RO import eligibility
    published = Planning.search([("state", "=", "published")])
    for plan in published:
        for line in plan.line_ids:
            if line.product_id.id in ids:
                stats["PACKAGE_IN_PUBLISHED_PLAN_LINES"] += 1
                if len(examples) < 12:
                    examples.append((plan.id, plan.kitchen_code, line.product_id.default_code, line.max_capacity))
    print("PACKAGE_PUBLISHED_PLAN_EXAMPLES:", examples)
    ro_lines = []
    for ro in RO.search([("state", "=", "confirmed")]):
        for line in ro.line_ids:
            if line.product_id.id in ids and line.qty_requested > 0:
                ro_lines.append((ro.name, ro.delivery_date, ro.slot, line.product_id.default_code, line.qty_requested))
    print("CONFIRMED_RO_PACKAGE_LINE_COUNT:", len(ro_lines))
    print("CONFIRMED_RO_PACKAGE_LINE_EXAMPLES:", ro_lines[:15])
    profiles = Counter()
    failed = []
    for package in packages:
        boms = Bom.search([
            ("active", "=", True),
            ("product_tmpl_id", "=", package.product_tmpl_id.id),
            "|", ("product_id", "=", False), ("product_id", "=", package.id),
        ])
        profiles["PACKAGE_SKUS_WITH_%s_BOM_MATCHES" % len(boms)] += 1
        if len(boms) != 1:
            if len(failed) < 20:
                failed.append((package.default_code, "BOM_MATCHES", len(boms)))
            continue
        for line in boms.bom_line_ids:
            component = line.product_id
            cname = component.categ_id.complete_name or ""
            if cname.startswith("All / Produk Jadi / Paket"):
                kind = "NESTED_PACKAGE"
            elif cname.startswith("All / Produk Jadi /"):
                kind = "FINISHED_GOOD"
            elif cname.startswith("All / Konsinyasi Masuk"):
                kind = "CONSIGNMENT"
            elif cname.startswith("All / Packaging"):
                kind = "PACKAGING"
            else:
                kind = "OTHER"
            profiles["BOM_LINE_" + kind] += 1
            if kind == "FINISHED_GOOD":
                # A finished-good component must be resolvable to a production
                # Planning line in the relevant delivery slot; global match alone
                # is only indicative, not a complete business authorization.
                candidates = [
                    (plan.kitchen_code, plan.delivery_date, plan.slot)
                    for plan in published
                    if component in plan.line_ids.mapped("product_id")
                ]
                if not candidates:
                    profiles["FINISHED_COMPONENT_NO_PUBLISHED_PLAN"] += 1
                    if len(failed) < 20:
                        failed.append((package.default_code, "NO_PUBLISHED_COMPONENT_PLAN", component.default_code))
                else:
                    profiles["FINISHED_COMPONENT_WITH_PUBLISHED_PLAN"] += 1
    print("PROFILES:", sorted(profiles.items()))
    print("REVIEW_EXAMPLES:", failed)
print("READ_ONLY_PACKAGE_RO_PLANNING_LINK_OK")
