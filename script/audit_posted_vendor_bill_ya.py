"""Read-only audit of already posted vendor bill for PO P00009."""
from decimal import Decimal

assert env.cr.dbname == "erp-yussyakmal-integer-test", "TEST DATABASE ONLY"
print("DATABASE:", env.cr.dbname)
print("MODE: EXISTING POSTED BILL JOURNAL AUDIT, READ-ONLY")

po = env["purchase.order"].sudo().search([("name", "=", "P00009")], limit=1)
assert po, "PO P00009 missing"
bills = po.invoice_ids.filtered(lambda b: b.move_type == "in_invoice")
assert len(bills) == 1, "Expected exactly one linked vendor bill"
bill = bills
assert bill.state == "posted", "Bill is not posted"
print("BILL:", bill.id, bill.name, "| DATE:", bill.date,
      "| JOURNAL:", bill.journal_id.code, bill.journal_id.name,
      "| PARTNER:", bill.partner_id.display_name)
print("TOTALS:", "UNTAXED:", bill.amount_untaxed,
      "| TAX:", bill.amount_tax, "| TOTAL:", bill.amount_total)
print("COMPANY VALUATION:", bill.company_id.inventory_valuation,
      "| COST:", bill.company_id.cost_method)

lines = bill.line_ids
debit = sum(lines.mapped("debit"))
credit = sum(lines.mapped("credit"))
print("JOURNAL ITEMS:")
for line in lines.sorted(key=lambda l: (l.account_id.code or "", l.id)):
    account = line.account_id
    print(" LINE:", line.id,
          "| ACCOUNT:", account.code, account.name,
          "| TYPE:", account.account_type,
          "| DISPLAY:", line.display_type,
          "| DEBIT:", line.debit,
          "| CREDIT:", line.credit,
          "| TAX IDS:", ",".join(line.tax_ids.mapped("name")))
print("TOTAL DEBIT:", debit, "| TOTAL CREDIT:", credit)
assert abs(Decimal(str(debit)) - Decimal(str(credit))) <= Decimal("0.02"), (
    "Unbalanced posted bill"
)
payables = lines.filtered(lambda l: l.account_id.account_type == "liability_payable")
payable_credit = sum(payables.mapped("credit"))
print("PAYABLE CREDIT:", payable_credit)
assert abs(Decimal(str(payable_credit)) - Decimal(str(bill.amount_total))) <= Decimal("0.02"), (
    "Unexpected payable credit"
)

tax_accounts = po.order_line.tax_ids.invoice_repartition_line_ids.filtered(
    lambda r: r.repartition_type == "tax" and r.account_id
).mapped("account_id")
print("EXPECTED VAT ACCOUNTS:", [(a.code, a.name) for a in tax_accounts])
tax_lines = lines.filtered(lambda l: l.account_id in tax_accounts)
tax_debit = sum(tax_lines.mapped("debit"))
print("VAT PURCHASE DEBIT:", tax_debit)
assert tax_accounts and tax_lines, "Input VAT account not found in journal"
assert abs(Decimal(str(tax_debit)) - Decimal(str(bill.amount_tax))) <= Decimal("0.02"), (
    "VAT amount mismatch"
)
print("PASS: posted journal balanced")
print("PASS: payable credit matches bill total")
print("PASS: input VAT debit matches bill tax")
print("POSTED_VENDOR_BILL_JOURNAL_AUDIT_OK: database tidak diubah")
