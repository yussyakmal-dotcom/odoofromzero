"""Odoo 19 accounting follow-up, READ ONLY, Manufacturing batch 3.
Inspect real per-move valuation, account links, production location and settings.
Do not use as financial signoff; no transactions or GL posting.
"""
assert env.cr.dbname == "erp-yussyakmal-mrp-test", "TEST DB ONLY"
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_BATCH3_ACCOUNTING_CLOSING")
company = env.company.sudo()
for key in ("inventory_valuation", "inventory_period", "cost_method",
            "account_stock_valuation_id", "anglo_saxon_accounting"):
    if key in company._fields:
        val = company[key]
        print("COMPANY_SETTING:", key, val.display_name if
              company._fields[key].type == "many2one" and val else val)
batch = env["ya.packing.batch"].sudo().search([
    ("delivery_date", "=", "2026-11-23"), ("slot", "=", "S2")])
assert len(batch) == 1 and batch.id == 3
mos = batch.line_ids.mapped("mo_id")
assert len(mos) == 1
mo = mos[0]
raw = mo.move_raw_ids.filtered(lambda m: m.state == "done")
finished = mo.move_finished_ids.filtered(
    lambda m: m.state == "done" and m.product_id == mo.product_id)
print("MO:", mo.name, mo.state, "SKU:", mo.product_id.default_code)
print("MO_RAW_VALUE_SUM:", sum(raw.mapped("value")))
print("MO_FINISHED_VALUE_SUM:", sum(finished.mapped("value")))
print("MO_VALUE_DELTA:", sum(finished.mapped("value")) - sum(raw.mapped("value")))
print("MO_EXTRA_COST:", mo.extra_cost if "extra_cost" in mo._fields else "UNAVAILABLE")
print("=== PRODUCTION LOCATION ACCOUNT CONFIG ===")
Location = env["stock.location"].sudo()
locations = Location.search([("usage", "=", "production")])
print("PRODUCTION_LOCATIONS:", len(locations))
for loc in locations:
    bits = []
    for field in ("valuation_in_account_id", "valuation_out_account_id",
                  "company_id"):
        if field in loc._fields:
            val = loc[field]
            bits.append("%s=%s" % (field, val.display_name if val else "-"))
    print("PRODUCTION_LOCATION:", loc.id, loc.complete_name, "|", "; ".join(bits))
print("=== STOCK MOVE VALUATION + DIRECT GL RELATION ===")
pickings = env["stock.picking"].sudo().search([("ya_store_batch_id", "=", batch.id)])
all_moves = raw | finished | pickings.mapped("move_ids")
for move in all_moves.sorted("id"):
    gl = move.account_move_id if "account_move_id" in move._fields else False
    print("MOVE:", move.id, "SKU:", move.product_id.default_code,
          "SOURCE:", move.location_id.usage, "DEST:", move.location_dest_id.usage,
          "QTY:", move.quantity, "VALUED:", move.is_valued,
          "VALUE:", move.value,
          "REMAINING_VALUE:", (move.remaining_value if
                               "remaining_value" in move._fields else "-"),
          "GL:", (gl.name if gl else "-"),
          "GL_STATE:", (gl.state if gl else "-"))
    if gl:
        for line in gl.line_ids:
            print("  GL_LINE:", line.account_id.code, line.account_id.name,
                  "DEBIT:", line.debit, "CREDIT:", line.credit)
print("=== INVENTORY VALUATION ACCOUNT ===")
account = company.account_stock_valuation_id if "account_stock_valuation_id" in company._fields else False
if account:
    print("ACCOUNT:", account.code, account.name)
    # Only account metadata, NOT an as-of stock balance / financial reconciliation.
    for field in ("account_type", "reconcile"):
        if field in account._fields:
            print("ACCOUNT_FIELD:", field, account[field])
print("NOTE: Manual closing or invoice posting may be required by valuation setup.")
print("NOTE: Review Accounting > Review > Inventory Valuation and draft closing")
print("      WITHOUT posting; reconcile valuation by product/category and GL date.")
print("READ_ONLY_BATCH3_ACCOUNTING_CLOSING_OK")
