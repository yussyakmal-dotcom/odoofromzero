# YA Material Requirement — Read-Only MO → Kitchen → CDC

**Status:** source-only implementation, NOT installed or tested in an Odoo registry yet. Current source version 19.0.2.0.0. Use only the test DB `erp-yussyakmal-mrp-test`.

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
