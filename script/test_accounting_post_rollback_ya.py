"""Test posting a vendor bill and inspect ledger entries, ALWAYS ROLLBACK.

Only on erp-yussyakmal-integer-test. No payment, no email, no commit.
"""
from decimal import Decimal

TEST_DB = "erp-yussyakmal-integer-test"
if env.cr.dbname != TEST_DB:
    raise RuntimeError("BLOCKED: test database only")

print("DATABASE:", env.cr.dbname)
print("MODE: ACCOUNTING POST TEST / ALL CHANGES ROLLBACK")

def close(a, b, tolerance="0.02"):
    return abs(Decimal(str(a)) - Decimal(str(b))) <= Decimal(tolerance)

po = env["purchase.order"].sudo().search([("name", "=", "P00009")], limit=1)
assert po and po.state in ("purchase", "done"), "Confirmed PO P00009 required"
assert not po.invoice_ids, "Existing vendor bill: stop and audit first"

company = po.company_id.sudo()
category = po.order_line.filtered(lambda l: l.product_id)[:1].product_id.categ_id
print("CONFIG: company:", company.name,
      "| inventory_valuation:", company.inventory_valuation,
      "| cost_method:", company.cost_method,
      "| anglo_saxon:", company.anglo_saxon_accounting)
print("CONFIG: category:", category.complete_name,
      "| valuation:", category.property_valuation,
      "| cost_method:", category.property_cost_method)
print("CONFIG: stock account:", company.account_stock_valuation_id.display_name,
      "| stock journal:", company.account_stock_journal_id.display_name)
print("CONFIG: category stock account:",
      category.property_stock_valuation_account_id.display_name)
print("CONFIG: category expense account:",
      category.property_account_expense_categ_id.display_name)
print("CONFIG: purchase journal:",
      env["account.journal"].sudo().search([
          ("company_id", "=", company.id), ("type", "=", "purchase")
      ], limit=1).display_name)
print("CONFIG: vendor payable account:",
      po.partner_id.sudo().with_company(company).property_account_payable_id.display_name)

try:
    eligible = po.order_line.filtered(
        lambda l: not l.display_type and l.product_id and l.qty_to_invoice > 0
    )
    assert eligible and all(l.product_id.purchase_method == "receive" for l in eligible), (
        "Received-quantity billing configuration required"
    )
    print("INVOICEABLE LINES:", [(l.id, l.qty_to_invoice) for l in eligible])
    po.action_create_invoice()
    env.invalidate_all()
    bills = po.invoice_ids.filtered(lambda b: b.move_type == "in_invoice")
    assert len(bills) == 1 and bills.state == "draft", "One draft vendor bill required"
    bill = bills
    print("DRAFT: untaxed:", bill.amount_untaxed,
          "| tax:", bill.amount_tax, "| total:", bill.amount_total)
    assert close(bill.amount_untaxed, 274320), "Unexpected net value"
    assert close(bill.amount_tax, 30175.2), "Unexpected VAT amount"
    assert close(bill.amount_total, 304495.2), "Unexpected bill total"
    assert bill.company_id == company, "Wrong company"
    assert bill.journal_id.type == "purchase", "Wrong journal type"

    bill.action_post()
    env.invalidate_all()
    assert bill.state == "posted", "Vendor Bill was not posted"
    print("POSTED TEMPORARILY:", bill.name, "| journal:", bill.journal_id.display_name)

    lines = bill.line_ids.filtered(lambda l: not l.display_type or l.display_type in ("product", "tax", "payment_term"))
    debits = sum(lines.mapped("debit"))
    credits = sum(lines.mapped("credit"))
    print("JOURNAL ITEMS:")
    for line in lines.sorted(key=lambda l: (l.account_id.code or "", l.id)):
        print(" ACCOUNT:", line.account_id.code,
              "|", line.account_id.name,
              "| TYPE:", line.account_id.account_type,
              "| DISPLAY:", line.display_type,
              "| DEBIT:", line.debit, "| CREDIT:", line.credit,
              "| TAX:", ",".join(line.tax_ids.mapped("name")))
    print("TOTAL JOURNAL: DEBIT:", debits, "| CREDIT:", credits)
    assert close(debits, credits), "Journal not balanced"
    assert close(debits, bill.amount_total), (
        "Unexpected journal gross debit total; inspect before accepting"
    )

    payable = lines.filtered(lambda l: l.account_id.account_type == "liability_payable")
    assert payable and close(sum(payable.mapped("credit")), bill.amount_total), (
        "Payable account credit differs from bill total"
    )
    tax_accounts = po.order_line.tax_ids.invoice_repartition_line_ids.filtered(
        lambda r: r.repartition_type == "tax" and r.account_id
    ).mapped("account_id")
    assert tax_accounts, "No VAT purchase account configured"
    tax_lines = lines.filtered(lambda l: l.account_id in tax_accounts)
    assert tax_lines and close(sum(tax_lines.mapped("debit")), bill.amount_tax), (
        "VAT input journal debit mismatch"
    )
    print("PASS: payable credit equals bill total")
    print("PASS: VAT purchase debit equals bill tax:", bill.amount_tax)
    print("PASS: journal debit equals credit; purchase discount and multi-UoM preserved")
    print("ACCOUNTING_POST_ROLLBACK_TEST_OK")
finally:
    env.cr.rollback()
    print("ROLLBACK_COMPLETE: no posted bill, journal entry or payment persisted")
