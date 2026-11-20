"""Audit read-only titik ekstensi Multi-UoM Receiving pada Odoo 19."""
import inspect
import re


def method_info(model, names):
    obj = env[model]
    print("MODEL METHODS:", model)
    for name in names:
        fn = getattr(type(obj), name, None)
        if fn is None:
            fn = getattr(obj, name, None)
        if fn is None:
            print("  ", name, "| TIDAK ADA")
            continue
        try:
            signature = str(inspect.signature(fn))
        except (TypeError, ValueError):
            signature = "signature tidak tersedia"
        try:
            source = inspect.getfile(fn)
        except (TypeError, OSError):
            source = "source tidak tersedia"
        print("  ", name, "|", signature, "|", source)


def print_views(model, field_names, limit=35):
    views = env["ir.ui.view"].sudo().search([
        ("model", "=", model),
        ("active", "=", True),
        ("type", "in", ["form", "list"]),
    ], order="priority,id")
    print("ACTIVE FORM/LIST VIEWS:", model, len(views))
    matched = 0
    for view in views:
        xml = str(view.arch_db or "")
        if not any(re.search(r'name=[\'"]' + re.escape(n) + r'[\'"]', xml)
                   for n in field_names):
            continue
        refs = view.get_external_id()
        xmlid = refs.get(view.id, "-")
        print("  VIEW:", view.id, "|", xmlid,
              "|", view.name, "|", view.type,
              "| inherit:", view.inherit_id.id or "ROOT")
        for tag in re.findall(r"<(?:field|button)\b[^>]*>", xml):
            if any(re.search(r'name=[\'"]' + re.escape(n) + r'[\'"]', tag)
                   for n in field_names):
                print("    TAG:", tag[:500])
        matched += 1
        if matched >= limit:
            print("  ... output dibatasi, sisa view tidak ditampilkan")
            break


def main():
    print("DATABASE:", env.cr.dbname)
    print("MODE: AUDIT READ-ONLY RECEIVING HOOKS")
    method_info("stock.picking", [
        "button_validate", "_pre_action_done_hook", "_action_done",
        "_sanity_check", "_create_backorder", "action_cancel",
    ])
    method_info("stock.move", [
        "_action_done", "_split", "_prepare_move_split_vals",
        "_get_move_lines", "_quantity_done_set",
    ])
    method_info("stock.move.line", [
        "create", "write", "_action_done",
    ])
    method_info("purchase.order.line", [
        "_compute_qty_received", "_compute_qty_invoiced",
    ])
    print_views("stock.picking", [
        "move_ids_without_package", "move_ids", "move_line_ids",
        "quantity", "product_uom_qty", "button_validate",
    ])
    print_views("stock.move", [
        "quantity", "product_uom_qty", "product_uom",
    ])
    print_views("stock.move.line", [
        "quantity", "product_uom_id",
    ])
    print("PICKING TYPE CDC:")
    types = env["stock.picking.type"].sudo().search([
        ("code", "=", "incoming"),
        ("warehouse_id.code", "=", "CDC"),
    ])
    for typ in types:
        f = typ._fields.get("create_backorder")
        print("  ID:", typ.id, "| NAME:", typ.name,
              "| create_backorder:", typ.create_backorder,
              "| options:", f._description_selection(env) if f else "FIELD ABSENT")

    print("PRODUK UJI P00009:")
    po = env["purchase.order"].sudo().search([("name", "=", "P00009")], limit=1)
    if po:
        for line in po.order_line:
            p = line.product_id
            print("  SKU:", p.default_code,
                  "| purchase_method:", p.product_tmpl_id.purchase_method,
                  "| qty_received_method:", line.qty_received_method,
                  "| ordered_base:", line.product_qty,
                  "| received_base:", line.qty_received)
    print("RECEIVING_HOOKS_AUDIT_COMPLETE: database tidak diubah")


main()
