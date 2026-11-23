"""READ ONLY: inspect Odoo 19 standard Picking Operations report before DO module install.

Run on erp-yussyakmal-mrp-test through odoo-bin shell. No writes.
"""
assert env.cr.dbname == "erp-yussyakmal-mrp-test", "REFUSED: wrong database"
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_NATIVE_PICKING_PRINT")
report = env.ref("stock.action_report_picking", raise_if_not_found=False)
assert report, "Missing standard Odoo stock.action_report_picking"
print("NATIVE_REPORT_XMLID: stock.action_report_picking")
print("NATIVE_REPORT_NAME:", report.name)
print("NATIVE_REPORT_MODEL:", report.model)
print("NATIVE_REPORT_TYPE:", report.report_type)
print("NATIVE_REPORT_TECHNICAL_NAME:", report.report_name)
assert report.model == "stock.picking"
assert report.report_type == "qweb-pdf"
assert report.report_name == "stock.report_picking"
print("NATIVE_PICKING_REPORT_AVAILABLE_OK")
print("NOTE: metadata verified; PDF with real DO lines needs GUI/report render test.")
