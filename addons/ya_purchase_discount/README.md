# YA Purchase Discount (Odoo 19 CE)

Prototype for the **test clone only**. Do not install on `erp-yussyakmal`
until ORM, UI, vendor-bill, and taxes have passed end-to-end testing.

## Policy

- Exactly one mode: None, Per Line, or Global.
- Per-line discount is either percentage or an **absolute discount on the
  entire order line** (not per unit).
- Global discount is percentage or absolute PO currency amount, allocated
  proportionally as an equivalent percentage on each taxable line.
- Cannot mix line/global discounts; cannot discount over 100% of gross.
- Tax and vendor bills use Odoo's native `purchase.order.line.discount`.
- The addon depends on `ya_purchase_multi_uom`; its price and base-UoM
  calculations must remain unchanged.

## Before installation

Run from repository root:

```bash
python3 -m unittest discover -s addons/ya_purchase_discount/tests -v
python3 -m compileall -q addons/ya_purchase_discount
```

These tests cover **pure discount math only**, not Odoo ORM interactions.
Do not treat a passing math test or successful addon installation as approval
to enable real purchasing.

## Required Odoo integration checks on clone

1. Mode None: old draft PO prices/totals remain unchanged.
2. Per Line 10% and Rp20,000: discount only the selected line; taxes follow.
3. Global 10% and Rp30,000: correct proportional allocation and taxes.
4. Switching modes clears values of the previous mode.
5. No discounts over gross; no mixed modes; zero/negative/NaN rejected.
6. Change quantity, UoM, unit price, vendor, and product: discount remains
   mathematically correct; no stale computed discount.
7. Confirm test PO and create vendor bill: native invoice discount/total match.
8. Compare currency rounding; cancel/edit/duplicate RFQ behavior.

No production installation before all eight checks pass.

## Sales-style wizard UX (v19.0.1.1.0)

The PO product list shows only effective `Disc.%`. A **Discount** button
beneath order lines opens a modal with **Apply / Discard** and these choices:

- On All Order Lines (%)
- One Order Line (%) or (Rp) — select the target PO line
- Global Discount (%)
- Fixed Amount (Rp) across the PO

The wizard resets the previous discount mode in the same transaction before
applying the selected one. It must be used on a **saved draft/sent RFQ**.

After upgrading **only the test clone**, run the rollback-only smoke test:

```bash
sudo -u odoo19 /opt/odoo19/venv/bin/python3 \
  /opt/odoo19/odoo/odoo-bin shell -c /etc/odoo19.conf \
  -d erp-yussyakmal-integer-test --no-http \
  < script/test_purchase_discount_wizard_ya.py \
  > discount_wizard_test.txt 2>&1
```

A successful installation is not enough: do not enable operational transactions
until this ORM test and real UI/invoice tax tests have passed.
