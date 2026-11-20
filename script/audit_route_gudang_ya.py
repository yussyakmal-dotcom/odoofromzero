"""Audit read-only warehouse routes/rules before configuring YA stock flows.

Usage: Odoo shell on erp-yussyakmal-integer-test (or primary for comparison).
No CREATE/WRITE/COMMIT and no FEFO/FIFO configuration changes.
"""


def main():
    e = globals().get("env")
    if e is None or e.cr.dbname not in (
        "erp-yussyakmal-integer-test", "erp-yussyakmal"
    ):
        raise RuntimeError("Database tidak termasuk target audit YA")
    print("DATABASE:", e.cr.dbname)
    print("MODE: AUDIT READ-ONLY ROUTE & STOCK RULE")
    for name in ("stock.warehouse", "stock.location", "stock.picking.type",
                 "stock.route", "stock.rule"):
        print("MODEL:", name, "| tersedia:", name in e.registry.models)
    WH = e["stock.warehouse"].sudo()
    Route = e["stock.route"].sudo().with_context(active_test=False)
    Rule = e["stock.rule"].sudo().with_context(active_test=False)
    Picking = e["stock.picking.type"].sudo()
    print("WAREHOUSE:", WH.search_count([]))
    print("ROUTES (TERMASUK ARSIP):", Route.search_count([]))
    print("STOCK RULES (TERMASUK ARSIP):", Rule.search_count([]))
    print("OPERATION TYPES:", Picking.search_count([]))
    print("=" * 75)
    for wh in WH.search([], order="code"):
        print("WAREHOUSE:", wh.code, "|", wh.name,
              "| STOCK:", wh.lot_stock_id.complete_name)
        for field in ("reception_steps", "delivery_steps", "buy_to_resupply",
                      "manufacture_to_resupply", "active"):
            if field in WH._fields:
                print("  CONFIG:", field, "=", wh[field])
        for field in ("route_ids", "buy_pull_id", "mto_pull_id"):
            if field in WH._fields:
                rec = wh[field]
                print("  ROUTE/REFERENCE:", field, "=",
                      [(r.id, r.display_name) for r in rec])
        op = Picking.search([("warehouse_id", "=", wh.id)])
        print("  OPERATION TYPES:", [(p.code, p.name) for p in op])
    print("=" * 75)
    for route in Route.search([], order="id"):
        print("ROUTE:", route.id, "|", route.name,
              "| ACTIVE:", route.active,
              "| RULE COUNT:", Rule.search_count([("route_id", "=", route.id)]))
        for field in ("product_selectable", "product_categ_selectable",
                      "warehouse_selectable", "supplied_wh_id", "supplier_wh_id"):
            if field in Route._fields:
                value = route[field]
                print("  CONFIG:", field, "=",
                      value.display_name if getattr(value, "_name", None) else value)
    print("=" * 75)
    for rule in Rule.search([], order="id"):
        def value(field):
            if field not in Rule._fields:
                return "N/A"
            rec = rule[field]
            return rec.complete_name if getattr(rec, "_name", None) == "stock.location" else (
                rec.display_name if getattr(rec, "_name", None) else rec
            )
        print("RULE:", rule.id,
              "| ROUTE:", value("route_id"),
              "| ACTION:", value("action"),
              "| FROM:", value("location_src_id"),
              "| TO:", value("location_dest_id"),
              "| OPERATION:", value("picking_type_id"),
              "| PROCURE:", value("procure_method"),
              "| ACTIVE:", value("active"))
    print("ROUTE_RULE_AUDIT_COMPLETE: tidak ada perubahan database")


main()
