"""Single focused read-only gate for implementing YA SO confirmation.

Run as odoo19 shell on RO_SO CLONE. No ORM writes, no commits.
Print IDs/fields/configuration, not customer names or private sales values.
"""
EXPECTED_DB = "erp-yussyakmal-mrp-test-RO_SO"
assert env.cr.dbname == EXPECTED_DB, "STOP_WRONG_DATABASE"

print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_FASE2_YA_CONFIRM_INPUT_GATE")
SO = env["sale.order"].sudo()
SOL = env["sale.order.line"].sudo()
print("SALE_ORDER_FIELDS:", {
    key: key in SO._fields for key in (
        "ya_is_capacity_so", "ya_delivery_date", "ya_slot",
        "commitment_date", "expected_date", "warehouse_id", "picking_ids",
        "state", "order_line",
    )
})
print("SALE_LINE_FIELDS:", {
    key: key in SOL._fields for key in (
        "order_id", "product_id", "product_uom_qty", "product_uom_id",
        "product_uom", "discount", "display_type", "is_downpayment",
        "route_id", "tax_id",
    )
})
print("SALE_GLOBAL_DISCOUNT_HELPER:", hasattr(SOL, "_is_global_discount"))
print("SALE_CONFIRM_METHOD:", hasattr(SO, "action_confirm"))
print("YA_ORDER_TOTAL:", SO.search_count([("ya_is_capacity_so", "=", True)]))
print("YA_CONFIRMED_TOTAL:", SO.search_count([
    ("ya_is_capacity_so", "=", True), ("state", "in", ["sale", "done"])
]))

latest = SO.search([
    ("ya_is_capacity_so", "=", True), ("state", "in", ("draft", "sent"))
], order="id desc", limit=3)
print("YA_DRAFT_SAMPLE_COUNT:", len(latest))
Planning = env["ya.production.planning"].sudo()
for order in latest:
    print("YA_DRAFT:", order.id, "DATE:", str(order.ya_delivery_date or ""),
          "SLOT:", order.ya_slot or "", "LINES:", len(order.order_line))
    planning = Planning.search([
        ("delivery_date", "=", order.ya_delivery_date),
        ("slot", "=", order.ya_slot),
        ("state", "=", "published"),
    ]) if order.ya_delivery_date and order.ya_slot else Planning.browse()
    print("PUBLISHED_KITCHENS_FOR_QUOTE:", len(planning),
          "PUBLISHED_SKU_LINES:", sum(len(p.line_ids) for p in planning))
    for line in order.order_line[:8]:
        p = line.product_id
        flag = (
            "DISCOUNT" if hasattr(line, "_is_global_discount") and line._is_global_discount()
            else "DISPLAY" if line.display_type
            else "PRODUCT" if p else "UNCLASSIFIED"
        )
        print("QUOTE_LINE:", line.id, "KIND:", flag,
              "PRODUCT_ID:", p.id if p else None,
              "CATEGORY:", p.categ_id.complete_name if p else None,
              "QTY:", line.product_uom_qty,
              "UOM_ID:", line.product_uom_id.id
              if "product_uom_id" in line._fields else None,
              "ROUTE_ID:", line.route_id.id if "route_id" in line._fields else None)
        if not p or flag != "PRODUCT" or not planning:
            continue
        routes = planning.mapped("line_ids").filtered(lambda x: x.product_id == p)
        print("PLANNING_ROUTE_COUNT:", p.id, len(routes))
        for route in routes[:3]:
            print("  ROUTE:", route.planning_id.kitchen_code,
                  "MAX:", route.max_capacity, "UOM_ID:", route.uom_id.id,
                  "BOM_ID:", route.bom_id.id)

pkg = env["product.product"].sudo().search([
    ("categ_id.complete_name", "=", "All / Produk Jadi / Paket")
], limit=1)
print("SAMPLE_PACKAGE_SKU_ID:", pkg.id if pkg else "NONE")
if pkg:
    boms = env["mrp.bom"].sudo().search([
        ("active", "=", True), ("type", "=", "normal"),
        ("product_tmpl_id", "=", pkg.product_tmpl_id.id),
        "|", ("product_id", "=", False), ("product_id", "=", pkg.id),
    ])
    print("SAMPLE_PACKAGE_BOM_COUNT:", len(boms))
    if len(boms) == 1:
        print("SAMPLE_PACKAGE_BOM_OUTPUT:", boms.product_qty,
              "UOM_ID:", boms.product_uom_id.id)
        print("SAMPLE_PACKAGE_COMPONENT_COUNT:", len(boms.bom_line_ids))

print("READ_ONLY_FASE2_YA_CONFIRM_INPUT_GATE_COMPLETE")
