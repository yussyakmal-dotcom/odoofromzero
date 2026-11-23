"""Read-only Odoo 19-specific inspection of stock costing and accounting mechanisms.

NO writes, NO posting, NO account changes. DB: erp-yussyakmal-mrp-test.
Unlike older Odoo, Odoo 19 may not expose stock.valuation.layer. Inspect
stock.move cost fields and accounting configuration rather than assuming
an SVL/journal per internal stock move.
"""
assert env.cr.dbname == "erp-yussyakmal-mrp-test", "REFUSED: WRONG DB"
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_ODOO19_COST_FIELDS")
Mods = env["ir.module.module"].sudo()
for module in ["account", "stock", "stock_account", "mrp", "mrp_account",
               "purchase_stock", "account_financial_report"]:
    record = Mods.search([("name", "=", module)], limit=1)
    print("MODULE:", module, record.state if record else "NOT_FOUND")
company = env.company.sudo()
for key in sorted(company._fields):
    if any(t in key for t in ("valuation", "inventory", "cost_method", "anglo_saxon")):
        field = company._fields[key]
        if field.type in ("binary", "one2many", "many2many", "html"):
            continue
        try:
            value = company[key]
            if field.type == "many2one":
                value = value.display_name if value else "-"
            print("COMPANY_FIELD:", key, "TYPE:", field.type, "VALUE:", value)
        except Exception as ex:
            print("COMPANY_FIELD_ERROR:", key, type(ex).__name__)
print("=== PRODUCT CATEGORIES ===")
Category = env["product.category"].sudo()
for category in Category.search([("complete_name", "in", [
        "All / Produk Jadi", "All / Produk Jadi / Paket",
        "All / Bahan Baku", "All / Packaging", "All / Konsinyasi Masuk",
    ])]):
    values = []
    for field in ("property_cost_method", "property_valuation",
                  "property_stock_valuation_account_id",
                  "property_stock_journal", "property_account_expense_categ_id"):
        if field in category._fields:
            value = category[field]
            if category._fields[field].type == "many2one":
                value = value.display_name if value else "-"
            values.append("%s=%s" % (field, value))
    print("CATEGORY:", category.complete_name, "|", "; ".join(values))
print("=== ODOO19 MOVE VALUATION FIELD DISCOVERY ===")
StockMove = env["stock.move"].sudo()
for key in sorted(StockMove._fields):
    if any(t in key for t in ("value", "cost", "price", "valuation", "account")):
        print("STOCK_MOVE_FIELD:", key, StockMove._fields[key].type)
print("=== MO COST FIELD DISCOVERY ===")
MO = env["mrp.production"].sudo()
for key in sorted(MO._fields):
    if any(t in key for t in ("cost", "price", "value", "valuation")):
        print("MO_FIELD:", key, MO._fields[key].type)
print("=== BATCH 3 ACTUAL MOVE DATA ===")
Batch = env["ya.packing.batch"].sudo()
batch = Batch.search([("delivery_date", "=", "2026-11-23"), ("slot", "=", "S2")])
assert len(batch) == 1 and batch.id == 3
ids = set()
for mo in batch.line_ids.mapped("mo_id"):
    ids.update((mo.move_raw_ids | mo.move_finished_ids).ids)
for picking in env["stock.picking"].sudo().search([
        ("ya_store_batch_id", "=", batch.id)]):
    ids.update(picking.move_ids.ids)
for move in StockMove.browse(sorted(ids)):
    vals = []
    for name in ("price_unit", "value", "cost", "standard_price", "is_valued",
                 "product_qty", "quantity", "state"):
        if name in move._fields:
            try:
                vals.append("%s=%s" % (name, move[name]))
            except Exception as ex:
                vals.append("%s=<%s>" % (name, type(ex).__name__))
    print("MOVE:", move.id, "SKU:", move.product_id.default_code,
          "SRC:", move.location_id.usage, "DST:", move.location_dest_id.usage,
          "|", "; ".join(vals))
print("=== PRODUCT COST SAMPLE ===")
for code in ["12379", "10357", "10275"]:
    product = env["product.product"].sudo().search([
        ("default_code", "=", code)], limit=1)
    if product:
        print("PRODUCT:", code, "COST:", product.standard_price,
              "CATEGORY:", product.categ_id.complete_name)
print("NOTE: This reports observable fields, not accepted cost correctness.")
print("READ_ONLY_ODOO19_COST_FIELDS_OK")
