# YA Material Requirement — Read-Only MO → Kitchen → CDC

**Status:** source-only implementation, NOT installed or tested in an Odoo registry yet. Current source version 19.0.4.1.0. Use only the test DB `erp-yussyakmal-mrp-test`.

## Purpose and workflow

After `ya_store_ro` Packing batch is `Produksi OK` with confirmed `mrp.production` MO, open **Manufacturing → YA Production Capacity → Material Requirement**. Choose delivery date and slot, then **Hitung / Refresh Kebutuhan**. One screen, two tabs:

1. **Kebutuhan Bahan per Dapur:** each kitchen+raw product grouped from actual MO `move_raw_ids`, converted into product stock base UoM. Displays gross MO demand, physical and total reserved stock under that kitchen warehouse Stock internal sublocations, free stock, **minimum and maximum** possible shortages; highlighting where shortage definite or reservations ambiguous.
2. **Ringkasan CDC per Bahan:** same ingredient needed by multiple kitchens combined BEFORE CDC free stock is subtracted ONCE. Shows total need, aggregate kitchen shortage bounds, CDC physical/reserved/free, and potential unmet CDC shortage min/max. Shows **CDC shortage for Warehouse Admin information only**, without initiating a Purchasing workflow.

This is **NOT a definitive transfer request**: reservation ownership (including same-MO reserved stock), incoming transfers, lot / FEFO, and real availability must be verified before issuing CDC internal transfers. Any CDC replenishment via standard Odoo Purchase is handled independently by Warehouse Admin, outside this flow. New **Cetak Picking List CDC (Draft)** button creates a QWeb PDF for physical preparation only. No buttons create stock transfers, stock pickings, reservations, MOs or purchases.

Pilot guard restricts usage to exact database `erp-yussyakmal-mrp-test`. The wizard writes *only transient report records*, never business stock or MO.

**Critical formula:** where all stock is zero, `min shortage = max shortage = gross need`. When stock has reservations, `min shortage = max(need - physical, 0)`, `max shortage = max(need - (physical-reserved), 0)`. The CDC report deducts CDC free stock from the **SUM across kitchens**, not separately for every kitchen. Never sum different UoMs.

## Tests, installation

As Feri:

```bash
cd ~/odoofromzero
git pull
python3 script/check_material_requirement_source_readonly_ya.py
python3 script/test_material_requirement_rules_ya.py
```

Only after PASS and **GUI backup** of MRP test:

```bash
sudo cp -a addons/ya_material_requirement /opt/odoo19/custom-addons/
sudo chown -R odoo19:odoo19 /opt/odoo19/custom-addons/ya_material_requirement
sudo -u odoo19 /opt/odoo19/venv/bin/python3 \
 /opt/odoo19/odoo/odoo-bin -c /etc/odoo19.conf \
 -d erp-yussyakmal-mrp-test -i ya_material_requirement \
 --stop-after-init --no-http
echo "INSTALL_EXIT_CODE=$?"
```

If installation exits 0, coordinate `sudo systemctl restart odoo19` (shared service); open menu and audit date `2026-11-27` / slot `S1`. Check the number of MOs=20, raw move lines=247, kitchen/component lines=97 and CDC is identified. **No transfers yet.** If error exit nonzero, do NOT restart; inspect log and fix source first.

## Pilot audit evidence, 23 Nov 2026

User-provided read-only MO audit of `2026-11-27 S1`: Packing batch Produksi OK, 20 Confirmed MOs, 247 raw stock moves, 97 kitchen/product combinations, kitchens Dapur Asin and Dapur Gorengan; CDC uniquely mapped to warehouse code `CDC`, name Gudang Central, location `CDC/Stock`. The 75 printed material groups all showed zero stock/reservations in kitchens and CDC; report omitted 22 rows due to print cap, so do NOT assert all 97 are zero without full view. No stock source location mismatches. This evidence does not authorize a real transfer or purchase.

## Fixed scope: no purchasing workflow inside this module

**User decision, 23 Nov 2026:** When CDC stock is insufficient, **Warehouse Admin (Admin Gudang) independently replenishes CDC using standard Odoo Purchase outside the Material Requirement flow.** Do not build purchase request, purchase approvals, automated RFQ/PO, or replenishment queues here. Material Requirement only computes demand for kitchen CDC transfer, displays CDC stock shortage as **information**, and will later hand off to standard Odoo Internal Transfers subject to available stock, accurate reservations, and FEFO. After stock arrives in CDC through the separate standard workflow, refresh Material Requirement and fulfill kitchen demand. Do not extend this project into Purchasing.

## 19.0.2.0.0 — Picking List CDC DRAFT PDF (source only)

From **Material Requirement → Hitung / Refresh Kebutuhan**, click **Cetak Picking List CDC (Draft)**. Re-reads MO demand and current CDC/kitchen stocks immediately before printing. Refuses if shared CDC stock is inadequate or kitchen reservations make pickup Qty ambiguous. Separate page per destination kitchen, consolidated material SKU, output UoM, estimated CDC pickup Qty, and blank columns for prepared Qty, lot/FEFO, checkmark, signatures. Print is **NOT** a persisted and numbered requisition, not a stock reservation and does **not** validate an Internal Transfer. Staff still record actual prepared Qty on paper; confirmation/transfer implementation is a separate next stage.

QWeb report: `report/cdc_picking_list_report.xml`; button in wizard form. **Not yet installed or tested in real Odoo.** Only `erp-yussyakmal-mrp-test` may run it.

**If addon not yet installed:** use `-i ya_material_requirement` as above. **If already installed:** copy updated files and use `-u ya_material_requirement` on test DB. Always complete GUI backup first, check CLI exit 0, coordinated service restart, then browser test. Test 2026-11-27 S1: 20 MOs, 97 kitchen/product combinations; print PDF should contain one page per kitchen with materials needing pickup. Do not create transfer merely by printing.

## 19.0.2.1.0 — Mandatory menu navigation List → Form → triggers

User requires **every operational menu open a LIST first**. Users choose a prior record or click **New**, which opens the FORM; then and only then may they click **Hitung / Refresh Kebutuhan** and **Cetak Picking List CDC (Draft)**. Menu must never open Form immediately or execute methods implicitly. List displays date as `YYYY-Mon-DD` via computed `delivery_date_label`, slot, status, MO and material counts, shortages. `ya.material.requirement.wizard` is a **TransientModel**: test/report list rows may be cleared automatically by Odoo, so the list is a temporary audit history, **not a permanent requisition log**. Persisting requisitions is a later phase, not implemented here.

No menu trigger is configured for stock changes. This view/model field change requires `-u ya_material_requirement` after copying current source and backing up test DB; service restart after exit=0. Do not use `-i` when installed.

## 19.0.3.0.0 — FIX: Existing Packing batch is the only user-facing entrypoint

**Feri corrected the previous design**: no wizard List, no `New`, no repeated selection of delivery date or slot. The Material Requirement menu now opens the existing `ya.packing.batch` **List** filtered `state = production_ok` (e.g. `Packing 2026-Nov-27 S1`). Select that batch and open a dedicated read-only **Form** showing the existing batch's date/slot/MO count and two materials tables. On the **form header** (not footer), press `Hitung / Refresh Kebutuhan` to replace that batch's material **report snapshots**, then `Cetak Picking List CDC (Draft)`. Both operations act on the selected batch; no user-created record and no automatic actions on opening menu.

Implementation: `models/material_requirement_batch.py` extends existing protected Packing batch without writing its fields. Only creates/deletes `ya.material.requirement.snapshot.line` records attached to batch; reuses existing hidden transient MO/CDC calculation engine. `views/material_requirement_batch_views.xml` replaces menu action and provides list/form. Existing wizard remains as **internal calculation engine**, not linked by the visible menu. The list and form show complete date labels `YYYY-Mon-DD`.

**IMPORTANT**: Version 19.0.2.1.0 exposed wizard list and placed button in the form footer, which was not visible in the normal form. Version 19.0.3.0.0 corrects both structural issues. Source-only until upgraded and verified on server. Use test DB only; no movement of stock, Purchase, WO, or MO by calculate/print. Persistent report lines aren't actual request or reserved stock.

Upgrade after GUI backup:
```bash
cd ~/odoofromzero
git pull
python3 script/check_material_requirement_source_readonly_ya.py
python3 script/test_material_requirement_rules_ya.py
sudo cp -a addons/ya_material_requirement/. /opt/odoo19/custom-addons/ya_material_requirement/
sudo chown -R odoo19:odoo19 /opt/odoo19/custom-addons/ya_material_requirement
sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin \
  -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test \
  -u ya_material_requirement --stop-after-init --no-http
echo "UPGRADE_EXIT_CODE=$?"
```
Restart Odoo service only if CLI exit 0 and safe for other DB users. Test opening menu directly into **existing batch List**, click `Packing 2026-Nov-27 S1`, verify visible header button and click Refresh. Expected MO count=20, kitchen/component groups=97; then test PDF. Error logs from Odoo/docutils need interpretation separate from exit 0.

## 19.0.4.1.0 — Field staff confirms physical picked Qty before native Odoo transfer

**Current operator decision (2026-Nov-23):** Picking List is printed and material is physically assembled. Next step is **Konfirmasi Qty Picking CDC**. Actual physical Qty is allowed to **exceed MO Picking List Qty** when the same source CDC sends additional stock to the **same destination kitchen** via **Special Transfer**. This is not an MO increase.

On Material Requirement existing `Packing 2026-Nov-27 S1` Form, click `Konfirmasi Qty Picking CDC`. This explicitly creates only one **persistent** `ya.cdc.pick.confirmation` draft per existing batch/kitchen, then opens a **LIST** of those documents. Pick a kitchen row to enter its **FORM** and edit Qty physically picked. The initial physical Qty is copied from the last approved material snapshot; do not automatically confirm it. **No user-created batch or repeated date/slot choice.**

For each product on a kitchen:
- `Qty Picking List (MO)`: immutable requirement from confirmed MOs.
- `Qty Fisik Dipicking`: operator-editable actual measured Qty, may be less/equal/more.
- `Qty Extra / Special`: computed `max(physical - MO, 0)`.
- To allow `physical > MO`, checkbox `Special Transfer?` and enter mandatory `Alasan Special`; optionally record `Referensi Special` (number of existing special request/transfer if known). This request **must be for the same destination kitchen**; never move extra to another kitchen's document.
- New extra-only SKU not in current MO may be entered on this destination's draft with `Qty Picking List (MO) = 0`, `Qty Fisik > 0`, Special Transfer checkbox and reason.
- A short physical pick is also allowed; shortfall remains visible and must not be silently counted as delivered.
- `Konfirmasi Qty Picking` validates material UoM/storability, non-negative Qty, uniqueness, permitted excess + reason, CDC free stock aggregated across confirmed kitchen sheets of this batch, and locks the document from editing. Uses a CDC warehouse SQL row lock to serialize confirmations within this flow.

**This is a confirmation/audit, NOT a stock reservation or Internal Transfer**. It does not write inventory, pickings, MOs, Purchase or accounting. A native CDC→Dapur internal transfer must later reconcile actual Qty vs already existing Special Transfers to avoid duplicate movements; check FEFO, actual bin lots, all reservations and shared CDC free stock again at transfer time. The confirmation's free-stock check is not a guarantee availability will remain unchanged. The source at 19.0.4.1.0 is **not yet independently confirmed installed or GUI-tested**. User confirmed the previous 19.0.3.0.0 PDF generation, NOT this picking confirmation action.

After GUI backup test DB, `git pull`, run `python3 script/check_material_requirement_source_readonly_ya.py`, copy addon to live custom-addons, upgrade with `-u ya_material_requirement` on exact `erp-yussyakmal-mrp-test`, check exit 0, coordinate `sudo systemctl restart odoo19`. Then open existing Packing batch → Konfirmasi Qty Picking CDC → list of kitchen sheets → select a kitchen form → edit actual Qty / Special entries → Confirm. **Do not manually create native stock transfer as an unlinked copy before reconciliation of Special.**
