"""Read-only inspection of effective tax for test PO P00009."""
assert env.cr.dbname == "erp-yussyakmal-integer-test", "TEST DATABASE ONLY"
po = env["purchase.order"].sudo().search([("name", "=", "P00009")], limit=1)
assert po, "P00009 missing"
print("DATABASE:", env.cr.dbname)
print("MODE: READ-ONLY PURCHASE TAX AUDIT")
print("PO:", po.name, "CURRENCY:", po.currency_id.name)
for line in po.order_line.filtered(lambda x: not x.display_type):
    print("LINE:", line.id, line.product_id.default_code,
          "| quantity:", line.product_qty, "| price_unit:", line.price_unit,
          "| discount:", line.discount,
          "| subtotal:", line.price_subtotal, "| tax:", line.price_tax)
    for tax in line.tax_ids:
        print(" TAX:", tax.id, repr(tax.name), "| amount:", tax.amount,
              "| type:", tax.amount_type, "| price_include:", tax.price_include_override,
              "| tax_group:", tax.tax_group_id.name)
        for child in tax.children_tax_ids:
            print("  CHILD:", child.id, child.name, "| amount:", child.amount,
                  "| type:", child.amount_type)
print("TOTAL:", "untaxed:", po.amount_untaxed,
      "tax:", po.amount_tax, "total:", po.amount_total)
if po.amount_untaxed:
    print("EFFECTIVE TAX PERCENT:",
          round(po.amount_tax / po.amount_untaxed * 100, 6))
print("PURCHASE_TAX_AUDIT_COMPLETE: database tidak diubah")
