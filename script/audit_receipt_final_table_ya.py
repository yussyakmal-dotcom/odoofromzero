"""Read-only audit of visible receipt tables and native-table QWeb condition."""
from lxml import html as html_parser, etree

assert env.cr.dbname == "erp-yussyakmal-integer-test", "TEST DB ONLY"
view = env.ref("stock.report_picking")
arch = view._get_combined_arch()
if isinstance(arch, str):
    arch = etree.fromstring(arch.encode())
print("DATABASE:", env.cr.dbname)
print("MODE: RECEIPT FINAL TABLE DIAGNOSIS READ-ONLY")
for node in arch.xpath("//table[contains(concat(' ',normalize-space(@class),' '),' o_main_table ')]"):
    print("COMBINED TABLE t-if:", node.get("t-if"), "| style:", node.get("style"))
po = env["purchase.order"].sudo().search([("name", "=", "P00009")], limit=1)
pick = po.picking_ids.filtered(lambda p: p.state == "done")[:1]
data = env["ir.actions.report"].sudo()._render_qweb_html("stock.report_picking", pick.ids)[0]
if isinstance(data, bytes):
    data = data.decode()
print("HTML HAS TECHNICAL 24975:", "24975" in data)
root = html_parser.fromstring(data)
for idx, table in enumerate(root.xpath("//table"), 1):
    print("HTML TABLE:", idx, "class:", table.get("class"))
    for row in table.xpath(".//tr"):
        cells = [" ".join(" ".join(td.itertext()).split()) for td in row.xpath("./th|./td")]
        if cells:
            print(" ROW:", " | ".join(cells)[:550])
print("RECEIPT_FINAL_TABLE_AUDIT_OK: database tidak diubah")
