# YA Purchase Reports (Odoo 19)

**Test database only until QWeb render and PDF visual checks pass.** Do not install
this module on `erp-yussyakmal` main database without approval.

This module inherits standard Odoo QWeb templates:
- `purchase.report_purchaseorder_document` and RFQ: physical PO quantity, unit,
  and unit purchase price.
- `stock.report_picking`: actual physical receipt quantity and unit from the
  stock move snapshots; fallback to native units for split/multiple move lines,
  so lot/serial detail totals are never falsely represented.
- `account.report_invoice_document`: for purchase-linked vendor bill lines
  where invoice base quantity divides exactly by the SKU purchase factor,
  display physical quantity and corresponding multiplied unit price.
  Fallback to native unit if the conversion would be fractional.

**No modifications to native stock quantities, PO amount calculations, tax,
discount, invoice amount, or posted accounting move lines.** These are display-only.

Testing on `erp-yussyakmal-integer-test`:
1. Copy addon under `/opt/odoo19/custom-addons/ya_purchase_reports`.
2. Compile Python and validate XML syntax.
3. Install `-i ya_purchase_reports --stop-after-init --no-http`, check logs.
4. Execute `script/test_purchase_reports_ya.py` (QWeb HTML + draft bill rollback).
5. Manually preview/print PO, Receipt and Bill PDF, check prices, labels, layout,
   taxes, multi-line same SKU, and split stock-move lines.
6. Only after print checks should any main DB promotion be discussed.

Limitations:
- `account.report_invoice_document` can also be used for customer invoices.
  Helper fields only activate for vendor bill lines linked to a purchase rule.
- A single purchase order line partially received in a quantity not divisible
  by its purchase factor prints in the base UoM to avoid fractional packages.
- Other stock reports (`stock.report_delivery_document`, reception report)
  are unchanged; the `Picking Operations` print action is the targeted receipt document.
