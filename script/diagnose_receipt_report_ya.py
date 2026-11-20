"""Read-only diagnosis for physical unit print on completed receipt."""
from lxml import html as html_parser

if env.cr.dbname != "erp-yussyakmal-integer-test":
    raise RuntimeError("TEST DB ONLY")
print("DATABASE:", env.cr.dbname)
print("MODE: RECEIPT PRINT DIAGNOSIS READ-ONLY")
po = env["purchase.order"].sudo().search([("name", "=", "P00009")], limit=1)
assert po
for picking in po.picking_ids:
    print("PICKING:", picking.name, "| STATE:", picking.state)
    for move in picking.move_ids:
        print(
            " MOVE:", move.id, "| SKU:", move.product_id.default_code,
            "| BASE:", move.quantity, move.product_uom.name,
            "| ORIGINAL:", move.ya_received_unit_qty,
            repr(move.ya_received_unit_label),
            "| MOVE LINES:", len(move.move_line_ids),
        )
        for line in move.move_line_ids:
            print("  DETAIL:", line.id, line.quantity, line.product_uom_id.name)
    if picking.state != "done":
        continue
    raw = env["ir.actions.report"].sudo()._render_qweb_html(
        "stock.report_picking", picking.ids
    )[0]
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    root = html_parser.fromstring(raw)
    rows = root.xpath("//tr")
    print("HTML TABLE ROW COUNT:", len(rows))
    for row in rows:
        cells = [" ".join(t.split()) for t in row.xpath(".//td//text()") if t.strip()]
        if cells:
            result = " | ".join(cells)
            if "Beras" in result or "Gram" in result or "Kg" in result or "25,400" in result:
                print(" HTML ROW:", result[:700])
print("RECEIPT_PRINT_DIAGNOSIS_OK: database tidak diubah")
