# YA Material Requirement — Read-Only MO → Kitchen → CDC

**Status:** source-only implementation, NOT installed or tested in an Odoo registry yet. Current source version 19.0.5.1.1. Use only the test DB `erp-yussyakmal-mrp-test`.

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

## 19.0.5.0.0 — Native Standard Odoo Internal Transfer DRAFT from confirmed CDC picking

**Business requirement confirmed by Feri on 2026-Nov-23:** once CDC physical picking Qty has been confirmed, the team expects an item in Odoo Inventory standard **Internal Transfers**. Previous release `19.0.4.1.0` intentionally only recorded confirmed actual Qty; no `stock.picking` existed. This release connects the confirmed document explicitly to standard Odoo transfers.

**UI flow (always LIST→FORM→ACTION):**
`Manufacturing → YA Production Capacity → Material Requirement` → existing `Packing 2026-Nov-27 S1` in List → Form → `Konfirmasi Qty Picking CDC` → kitchen-document List → kitchen Form → `Konfirmasi Qty Picking` → **`Buat Internal Transfer (Draft)`** (visible only after Confirmed and before linking) → Odoo's native `stock.picking` Form. After creation, `Buka Internal Transfer` reopens that same linked transfer. The standard Odoo `Inventory → Operations → Transfers` or Internal Transfers list displays this native document with internal operation type when filters match.

**Source `models/cdc_pick_confirmation.py`:**
- Adds audit link `ya.cdc.pick.confirmation.internal_transfer_id` to the native `stock.picking`, locked down to a single explicit action by authorized Stock Manager (plus existing YA MRP/Packing role and `erp-yussyakmal-mrp-test` DB guard).
- One sheet per existing batch+destination warehouse; all rows use immutable actual physical Qty. Qty planned to transfer = `picked_qty` **once**, not `picked_qty + special_qty`. Existing MO Qty remains unchanged. Every material is a native `stock.move` demand line with description of breakdown `MO vs Special` in picking notes; negative and zero actual Qty excluded.
- Source = **CDC warehouse `lot_stock_id`**, destination = **selected kitchen warehouse `lot_stock_id`**, picking type = **CDC warehouse `int_type_id`**, explicitly required to be internal and same-company.
- Existing linked transfer opens instead of duplicating. The action obtains row lock on confirmation record, checks duplicate native `stock.picking.origin`, and links the created document atomically.
- The optional `special_reference` is checked against existing non-cancelled standard Odoo `stock.picking.name` or `origin`. If matched, action blocks for reconciliation to prevent re-dispatching an existing Special Transfer. No silent adoption/duplication of preexisting Special Transfers.
- Prior to creating a Draft, checks current CDC free stock and outstanding unfulfilled confirmed sheets for this source warehouse (conservative, possible overcount when another transfer has already reserved stock). This is NOT an actual stock reservation; recheck again when validating in Inventory. Note: external transfers without a populated Special reference cannot always be detected; Warehouse Admin must reconcile those.
- **Creates only native `stock.picking` and native `stock.move` in Draft**. NO `action_confirm`, `action_assign`, `button_validate`, stock quant mutation, receipt, MO change, or PO. Odoo handles actual stock movement and possible reservations **later** when Warehouse Admin processes the native transfer. FEFO/lot, intermediate transit routing, company and available stock must be verified before validation. We do not bypass Odoo's normal validations; no automatic marking Done.

**Safe rollout:** backup GUI `erp-yussyakmal-mrp-test`; `git pull`, run `python3 script/check_material_requirement_source_readonly_ya.py` and `python3 script/test_material_requirement_rules_ya.py`; copy addon to active custom-addons, `-u ya_material_requirement` on exact MRP test DB; restart only when safe. **Source is committed; not deployed/GUI-tested on server**. The user will execute upgrade and test one confirmed kitchen record. Verify native picking `state=draft`, `picking_type_id.code=internal`, source/destination, quantity, and single link. Reclick button/open link and verify no duplicate; **do not validate/assign the transfer yet**.

**Important remaining phase:** live FEFO/lot picking, route-specific Transit legs if configured, warehouse Dispatch and Kitchen Receive, inventory/accounting valuation must be separately configured and tested; no claim of end-to-end successful stock transfer at this stage.

## 19.0.5.0.1 — Odoo 19 stock.move field compatibility hotfix (2026-Nov-23)

Feri clicked `Buat Internal Transfer (Draft)` and sent server traceback (on exact `ya.cdc.pick.confirmation`): `ValueError: Invalid field 'name' in 'stock.move'` at `Move.create([...])`. This is an actual Odoo 19 runtime failure, not a harmless docutils warning. **Cause:** the prior transfer creator supplied legacy `'name': line.product_id.display_name` in native `stock.move` values; this field is absent in Feri's Odoo 19 `stock.move` registry.

**Fix:** remove `name` from stock.move payload. `product_id` still identifies the material; detailed MO-vs-Special breakdown remains in optional picking `note`. Add a runtime guard `Move._fields` for all move payload keys including `picking_id` before creating `stock.picking`, surfacing a readable `UserError` if a future Odoo schema differs. Static AST source guard explicitly forbids `name` in the `move_values.append` payload. **No automatic confirmation, reservation, stock deduction, validation or MO mutation.** Existing confirmed CDC picking should remain intact, since the RPC exception rolled back the failed request (the provisional stock.picking and stock.move are not committed by normal Odoo HTTP transactions). Nevertheless, inspect `internal_transfer_id` and search native Internal Transfers for that origin before retrying to rule out any prior separate successful actions.

**Rollout:** `git pull`, run `python3 script/check_material_requirement_source_readonly_ya.py`, backup MRP test DB, copy addon into active custom-addons, `-u ya_material_requirement` on exact `erp-yussyakmal-mrp-test`, restart Odoo service when safe, and retry **same confirmed CDC picking**. If Odoo generates draft successfully, verify native stock.picking state=Draft, route CDC→same kitchen, physical Qty including Special once; do NOT validate at this stage. This is a source patch and NOT a confirmed successful GUI test until Feri supplies evidence.

## 19.0.5.1.0 — Prefill Native Odoo Internal Transfer Demand and Qty (2026-Nov-23)

**Feri requested:** A single standard Odoo Internal Transfer can hold ~100 material SKUs. It must save operator time: when creating a transfer from already-confirmed physical CDC picking, initialize both **Demand** (`stock.move.product_uom_qty`) and **Qty** (`stock.move.quantity`) to the **same confirmed picked_qty** per SKU. Operators should edit only discrepancies on the native Odoo form. The Special Transfer amount is already part of `picked_qty` and must NOT be added again; MO requirement remains unchanged.

**Odoo 19 technical qualification:** `stock.move.quantity` is inverse/computed from `stock.move.line.quantity`. Writing a nonzero native Quantity creates/updates detail move lines, which **can reserve stock even when the top-level transfer still says Draft**. This is *not* a display-only copy and must never be implemented by bypassing native Odoo reservation/lot/FEFO. Official Odoo 19 stock.move / stock.move.line code documents these mechanisms.

**Safety-aware implementation in `cdc_pick_confirmation.action_create_internal_transfer`:**
- Create native `stock.picking` + `stock.move` Demand for every positive confirmed picked product as previously.
- Map generated stock moves by **product ID** and write `move.quantity = picked_qty` via `move.write({'quantity': qty})` **only** for untracked materials (`product.tracking == 'none'`) with adequate *strict* free quant at the exact CDC `lot_stock_id` (unpackaged/unowned/untracked bin). This can reserve CDC stock via Odoo stock.move.line. Verify Odoo still reports `quantity == demand` and `move.state == draft`; exception rolls back all changes.
- SKUs with lots/serials, sublocations, packages/owner details, or insufficient free stock at exact CDC root do **not** receive a fabricated detailed quantity: Demand is still set, Qty remains for manual warehouse operator to fill after **lot/FEFO/bin/actual availability** check.
- Correct shared-stock claims for multiple kitchen confirmations: when checking CDC free quants, subtract only the **outstanding UNRESERVED** picked Qty of other confirmed sheets. For existing linked native pickings with move lines, `stock.quant.reserved_quantity` has already reduced free stock; don't double subtract it. Completed transfers have already affected on-hand stock. The same helper is used during physical picking confirmation and transfer creation.
- Never call native Odoo Confirm, Assign, Validate or other Done/transfer completion automatically. No stock is moved from CDC to kitchen at draft creation; *however reservation may occur* and is operationally meaningful.
- Date formatting `YYYY-Mon-DD`, Menu→List→Form→Action and permanent document source reference remain unchanged.

**Source-only until tested in server GUI.** Rollout only on `erp-yussyakmal-mrp-test`: backup, `git pull`, static check + rules tests, copy module to active addons, `-u ya_material_requirement`, restart safe. Create a **new** draft only from a confirmed physical kitchen picking with no existing native link; existing draft is **not retroactively rewritten**. Start with one kitchen and inspect Demand, Qty, move lines, reserved stock, lot/FEFO cases, Draft state and that Validate was not called; test no negative stock. For already-linked drafts, do not click/create another transaction to fill Qty; edit existing native Odoo transfer manually after checking stock.

## 19.0.5.1.1 — Fix false Invalid Operation for Odoo 19 Assigned/Ready (2026-Nov-23)

**Real GUI error Feri observed after creating Internal Transfer** for product `[10278] Garam Dolphin 12x1Kg`: `Invalid Operation: Odoo did not preserve Draft Demand=Qty ... Transaction rolled back`. Source v19.0.5.1.0 had an overly strict condition: `move.write({'quantity': qty})` followed by `move.state != 'draft'` raised `UserError`.

**Root cause confirmed in native Odoo 19 source** (public `odoo/odoo` branch `19.0`, `addons/stock/models/stock_move.py`): `stock.move.quantity` is stored computed/inverse from move lines; writing Quantity creates/reserves native stock.move.line, then `_recompute_state()` sets move state to `assigned` when `quantity >= product_uom_qty`. Native `stock.picking._compute_state()` can report **Ready** when moves are assigned. This is **not a transfer Done** and does not imply product tracking/FEFO was activated. Consequently, insisting every move stay Draft conflicts with native Odoo 19 reservation workflow.

**Fix:** while safely pre-filling `Demand = Qty` for eligible untracked materials, allow native Odoo to transition to `assigned` / `partially_available` or any other non-final normal state. Require actual `move.quantity` equals confirmed picked Qty; reject `done` / `cancel` on both move and picking. If Qty mismatch, error now displays Demand, actual Qty, product, and move state. Button label changed to **`Buat Internal Transfer Odoo`** rather than implying exact Draft status; form explicitly explains Quantity may reserve CDC stock and make transfer Ready while still unvalidated. No auto-validation, no physical stock deduction/arrival.

**Rollout:** source patch committed on GitHub, **not server-tested yet**. Backup MRP-test DB, `git pull`, run the source checker and rules tests, deploy to active addon path, `-u ya_material_requirement` for `erp-yussyakmal-mrp-test`, restart Odoo when safe. Retry button on **SAME existing confirmed CDC picking record**; previous RPC `UserError` rolled back transaction, so no new picking should have been committed from that failed click. Still first check linked `internal_transfer_id` and existing native Inventory transfers to rule out other successful clicks. Do NOT recreate Picking List, confirmed sheet, MO or SO. Expect native transfer to be **Ready** or Draft depending on whether/how the Odoo 19 ORM reserved items; do NOT Validate yet. Verify Qty=Demand on eligible rows including Garam Dolphin and no stock quantity moved. Confirmed Special quantity remains included once in physical actual.
