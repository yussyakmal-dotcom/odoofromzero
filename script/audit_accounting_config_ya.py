"""Read-only accounting configuration audit for YA Odoo 19 test database.

No create/write/post/commit. Runs only on erp-yussyakmal-integer-test.
"""

if env.cr.dbname != "erp-yussyakmal-integer-test":
    raise RuntimeError("TEST DATABASE ONLY")

print("DATABASE:", env.cr.dbname)
print("MODE: ACCOUNTING CONFIG AUDIT READ-ONLY, NO CREATE/WRITE/POST/COMMIT")


def show_fields(record, field_names, label):
    print(label)
    for name in field_names:
        field = record._fields.get(name)
        if not field:
            print(" ", name, ": FIELD NOT FOUND")
            continue
        val = record[name]
        if field.type == "many2one":
            val = ("%s [%s]" % (val.display_name, val.id)) if val else "-"
        elif field.type in ("many2many", "one2many"):
            val = "records=%s" % len(val)
        print(" ", name, "|", field.type, "|", val)


print("=== INSTALLED MODULES ===")
module_names = [
    "account", "account_accountant", "stock", "stock_account",
    "purchase", "purchase_stock", "l10n_id",
    "ya_purchase_multi_uom", "ya_integer_quantity",
    "ya_purchase_discount", "ya_multi_uom_receiving", "ya_purchase_reports",
]
modules = env["ir.module.module"].sudo().search([("name", "in", module_names)])
for name in module_names:
    m = modules.filtered(lambda x: x.name == name)[:1]
    print(" MODULE:", name, "|", m.state if m else "NOT FOUND")

company = env.company.sudo()
print("=== COMPANY ===")
print(" ID:", company.id, "| NAME:", company.name, "| CURRENCY:", company.currency_id.name)
show_fields(company, [
    "country_id", "chart_template", "anglo_saxon_accounting",
    "inventory_valuation", "inventory_cost_method",
    "stock_valuation_account_id", "stock_valuation_journal_id",
    "account_stock_valuation_id", "account_stock_journal_id",
    "property_stock_account_input_categ_id", "property_stock_account_output_categ_id",
    "account_default_pos_receivable_account_id",
], "COMPANY ACCOUNTING / INVENTORY FIELDS:")

print("=== INVENTORY SETTINGS FIELD DISCOVERY ===")
for model in ("res.company", "product.category"):
    rec = company if model == "res.company" else env[model].sudo()
    for name in sorted(rec._fields):
        if ("valuation" in name or "cost_method" in name or
                "stock_journal" in name or "stock_account" in name):
            f = rec._fields[name]
            if f.type not in ("one2many", "many2many", "binary", "html"):
                print(" ", model, name, "|", f.type)

print("=== CHART OF ACCOUNTS ===")
Account = env["account.account"].sudo().with_company(company)
print(" TOTAL ACCOUNTS:", Account.search_count([]))
for account in Account.search([], order="code,id", limit=35):
    print(" ACCOUNT:", account.code, "|", account.name, "|", account.account_type,
          "| reconcile:", account.reconcile)

print("=== ACCOUNT JOURNALS ===")
journals = env["account.journal"].sudo().search([("company_id", "=", company.id)])
for j in journals:
    print(" JOURNAL:", j.id, "|", j.code, "|", j.name, "|", j.type)
    show_fields(j, ["default_account_id", "suspense_account_id",
                    "outstanding_receipt_account_id", "outstanding_payment_account_id"],
                "  JOURNAL ACCOUNTS:")

print("=== PRODUCT / CATEGORY ACCOUNTING ===")
product = env["product.product"].sudo().search([("default_code", "=", "10164")], limit=1)
assert product, "SKU 10164 missing"
print(" PRODUCT:", product.id, product.display_name, "| BASE UOM:", product.uom_id.name)
show_fields(product, [
    "standard_price", "cost_method", "valuation",
    "property_account_expense_id", "property_account_income_id",
], "PRODUCT:")
category = product.categ_id
print(" CATEGORY:", category.id, category.complete_name)
show_fields(category, [
    "property_cost_method", "property_valuation",
    "property_stock_valuation_account_id",
    "property_stock_account_input_categ_id",
    "property_stock_account_output_categ_id",
    "property_stock_journal",
    "property_account_expense_categ_id",
    "property_account_income_categ_id",
], "CATEGORY:")

print("=== TAX USED BY PO P00009 ===")
po = env["purchase.order"].sudo().search([("name", "=", "P00009")], limit=1)
assert po, "P00009 missing"
for tax in po.order_line.tax_ids:
    print(" TAX:", tax.id, "|", tax.name, "| amount:", tax.amount,
          "| type:", tax.amount_type, "| group:", tax.tax_group_id.name)
    show_fields(tax, ["invoice_repartition_line_ids", "refund_repartition_line_ids",
                      "cash_basis_transition_account_id", "tax_exigibility"],
                "  TAX FIELDS:")
    for rep in tax.invoice_repartition_line_ids:
        acc = rep.account_id
        print("  INVOICE REP:", rep.repartition_type,
              "| factor:", rep.factor_percent,
              "| account:", ("%s %s" % (acc.code, acc.name)) if acc else "-")

print("=== POSTED JOURNAL / VENDOR BILL COUNTS ===")
Move = env["account.move"].sudo().with_company(company)
for move_type in ("entry", "in_invoice", "out_invoice"):
    for state in ("draft", "posted"):
        count = Move.search_count([("move_type", "=", move_type), ("state", "=", state),
                                   ("company_id", "=", company.id)])
        print(" MOVE:", move_type, state, count)
print("PO:", po.name, "| STATE:", po.state,
      "| BILL COUNT:", len(po.invoice_ids),
      "| RECEIPT COUNT:", len(po.picking_ids))
print("ACCOUNTING_CONFIG_AUDIT_OK: database tidak diubah")
