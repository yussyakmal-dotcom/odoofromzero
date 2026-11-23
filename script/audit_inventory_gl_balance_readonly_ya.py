"""READ ONLY: actual Odoo19 inventory balance accounts vs posted GL.

Diagnostic only. A zero or nonzero balance is NOT a reconciliation verdict
without full opening balances, cutoff, costing and inventory valuation report.
Only for erp-yussyakmal-mrp-test. NO CREATE/WRITE/POST.
"""
assert env.cr.dbname == "erp-yussyakmal-mrp-test", "TEST DB ONLY"
company = env.company.sudo()
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_INVENTORY_GL_BALANCE")
print("COMPANY:", company.name, "CURRENCY:", company.currency_id.name)
print("SETTING:", "inventory_valuation=",
      company.inventory_valuation if "inventory_valuation" in company._fields else "N/A",
      "inventory_period=",
      company.inventory_period if "inventory_period" in company._fields else "N/A")
Category = env["product.category"].sudo()
cats = Category.search([
    "|", "|", "|",
    ("complete_name", "ilike", "All / Produk Jadi"),
    ("complete_name", "ilike", "All / Bahan Baku"),
    ("complete_name", "ilike", "All / Packaging"),
    ("complete_name", "ilike", "All / Konsinyasi Masuk"),
])
accounts = {}
def add_account(a, origin):
    if a:
        accounts.setdefault(a.id, {"account": a, "origins": []})["origins"].append(origin)
for cat in cats:
    for key in ("property_stock_valuation_account_id",
                "property_stock_account_input_categ_id",
                "property_stock_account_output_categ_id"):
        if key in cat._fields:
            add_account(cat[key], cat.complete_name + ":" + key)
if "account_stock_valuation_id" in company._fields:
    add_account(company.account_stock_valuation_id, "company.account_stock_valuation_id")
print("INVENTORY_RELATED_ACCOUNT_COUNT:", len(accounts))
print("NOTE: balance figures are test DB posted journal totals (not necessarily opening-adjusted).")
for account_id in sorted(accounts, key=lambda i: accounts[i]["account"].code):
    a = accounts[account_id]["account"]
    print("ACCOUNT:", a.code, a.name, "TYPE:", a.account_type)
    print("  MAPPING_SOURCES:", "; ".join(accounts[account_id]["origins"][:12]))
    for state in ("posted", "draft"):
        # Read-only aggregate; not claiming balances match real asset valuation.
        env.cr.execute("""
            SELECT COUNT(*), COALESCE(SUM(aml.debit), 0),
                   COALESCE(SUM(aml.credit), 0)
              FROM account_move_line aml
              JOIN account_move am ON am.id = aml.move_id
             WHERE aml.account_id = %s
               AND aml.company_id = %s
               AND am.state = %s
        """, (account_id, company.id, state))
        n, debit, credit = env.cr.fetchone()
        print("  GL:", state, "LINES:", n,
              "DEBIT:", debit, "CREDIT:", credit, "NET:", debit-credit)
print("=== SAMPLE PRODUCT / 2026-11-23 MO ===")
product = env["product.product"].sudo().search([
    ("default_code", "=", "12379")], limit=1)
if product:
    print("PRODUCT:", product.default_code,
          "CATEGORY:", product.categ_id.complete_name,
          "COST:", product.standard_price)
    for key in ("property_cost_method", "property_valuation",
                "property_stock_valuation_account_id"):
        if key in product.categ_id._fields:
            val = product.categ_id[key]
            print("  CATEGORY_FIELD:", key,
                  val.display_name if product.categ_id._fields[key].type == "many2one" and val else val)
print("NOTE: Compare the official Odoo19 inventory valuation as-of the")
print("      SAME cutoff and company, category, opening balances, and GL.")
print("NOTE: No accounts or stock records were changed.")
print("READ_ONLY_INVENTORY_GL_BALANCE_OK")
