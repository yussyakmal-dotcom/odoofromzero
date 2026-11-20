"""Audit read-only untuk desain YA Multi-UoM Receiving Odoo 19.

Jalankan melalui odoo-bin shell pada database TEST. Tidak CREATE/WRITE/COMMIT.
Tidak menampilkan nama vendor, harga, atau data kontak.
"""

def describe(model_name, names):
    if model_name not in env.registry.models:
        print("MODEL:", model_name, "| TIDAK TERSEDIA")
        return
    model = env[model_name]
    print("MODEL:", model_name, "| RECORDS:", model.search_count([]))
    for name in names:
        field = model._fields.get(name)
        if not field:
            print("  FIELD:", name, "| TIDAK ADA")
        else:
            compute = field.compute
            print(
                "  FIELD:", name,
                "| type:", field.type,
                "| relation:", getattr(field, "comodel_name", None),
                "| required:", field.required,
                "| readonly:", field.readonly,
                "| compute:", bool(compute),
                "| store:", field.store,
            )


def main():
    print("DATABASE:", env.cr.dbname)
    print("MODE: AUDIT READ-ONLY MULTI-UOM RECEIVING")
    print("MODUL:")
    for name in ["purchase", "purchase_stock", "stock", "stock_account",
                 "ya_purchase_multi_uom", "ya_integer_quantity",
                 "ya_purchase_discount"]:
        module = env["ir.module.module"].sudo().search([("name", "=", name)], limit=1)
        print(" ", name, "|", module.state if module else "TIDAK TERDAFTAR")

    describe("purchase.order", [
        "name", "state", "order_line", "picking_ids",
        "invoice_ids", "invoice_status", "currency_id",
    ])
    describe("purchase.order.line", [
        "product_id", "product_qty", "product_uom_id", "qty_received",
        "qty_received_method", "qty_invoiced", "price_unit",
        "ya_purchase_rule_id", "ya_purchase_price", "move_ids",
    ])
    describe("product.template", ["purchase_method", "uom_id", "purchase_ok"])
    describe("stock.picking", [
        "name", "state", "picking_type_id", "origin",
        "move_ids", "move_line_ids", "backorder_id",
        "backorder_ids", "location_dest_id",
    ])
    describe("stock.move", [
        "product_id", "product_uom_qty", "product_uom", "quantity",
        "picked", "state", "picking_id", "purchase_line_id",
        "move_line_ids", "location_dest_id", "allowed_uom_ids",
    ])
    describe("stock.move.line", [
        "product_id", "move_id", "picking_id", "quantity",
        "product_uom_id", "quantity_product_uom", "picked", "lot_id",
        "location_dest_id", "allowed_uom_ids",
    ])
    describe("stock.picking.type", [
        "code", "name", "create_backorder", "use_create_lots",
        "use_existing_lots",
    ])
    describe("ya.purchase.uom.rule", [
        "product_id", "purchase_label", "factor",
        "base_uom_id", "active",
    ])

    print("CONTOH PO P00009 (hanya identifier dan kuantitas):")
    orders = env["purchase.order"].sudo().search([("name", "=", "P00009")])
    for po in orders:
        print("  PO:", po.name, "| state:", po.state, "| lines:", len(po.order_line))
        for line in po.order_line:
            sku = line.product_id.default_code or "(tanpa SKU)"
            rule = getattr(line, "ya_purchase_rule_id", False)
            print(
                "    SKU:", sku,
                "| ordered_base:", line.product_qty,
                "| uom:", line.product_uom_id.name if line.product_uom_id else "-",
                "| received_base:", line.qty_received,
                "| rule:", (rule.purchase_label if rule else "-"),
                "| factor:", (rule.factor if rule else "-"),
            )
        for picking in po.picking_ids:
            print("  RECEIPT:", picking.name, "| state:", picking.state,
                  "| moves:", len(picking.move_ids),
                  "| dest:", picking.location_dest_id.complete_name)
            for move in picking.move_ids:
                print(
                    "    MOVE SKU:", move.product_id.default_code or "(tanpa SKU)",
                    "| demand:", move.product_uom_qty,
                    "| quantity:", move.quantity,
                    "| uom:", move.product_uom.name,
                    "| state:", move.state,
                )
                for ml in move.move_line_ids:
                    print(
                        "      MOVE LINE: id", ml.id,
                        "| quantity:", ml.quantity,
                        "| uom:", ml.product_uom_id.name,
                    )

    print("INCOMING OPERATION TYPES:")
    types = env["stock.picking.type"].sudo().search([("code", "=", "incoming")])
    for typ in types[:5]:
        print("  TYPE:", typ.id, "| code:", typ.code,
              "| backorder:", getattr(typ, "create_backorder", "FIELD TIDAK ADA"))
    print("AUDIT_MULTI_UOM_RECEIVING_COMPLETE: tanpa perubahan database")


main()
