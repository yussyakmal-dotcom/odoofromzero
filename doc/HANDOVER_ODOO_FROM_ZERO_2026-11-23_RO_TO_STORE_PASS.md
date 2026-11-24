# ODOO FROM ZERO — HANDOVER UTAMA — 23 NOVEMBER 2026

**BACA INI TERLEBIH DAHULU.** Menggantikan status operasional yang bertentangan dalam handover lama, **bukan** menghapus riwayat sebelumnya.

- Repository: `yussyakmal-dotcom/odoofromzero`; branch `main`.
- Feri menangani terminal/server dan deploy; owner memvalidasi alur bisnis di UI.
- **DB aktif untuk pengujian Manufacturing:** `erp-yussyakmal-mrp-test` (BUKAN `erp-yussyakmal` produksi atau `erp-yussyakmal-integer-test`).
- Odoo 19 Community / Ubuntu 24; repo server `~/odoofromzero`.
- Custom addons deployed to `/opt/odoo19/custom-addons/`; Python `/opt/odoo19/venv/bin/python3`; binary `/opt/odoo19/odoo/odoo-bin`; config `/etc/odoo19.conf`; OS user `odoo19`; service `odoo19`.
- **Latest owner statement:** `sudah di test RO TOKO ---- > STOCK TOKO good` — **USER ACCEPTANCE PASS** for the principal flow, based on owner report on 23 Nov 2026. No detailed per-SKU stock reconciliation report was supplied with that final message. Do not assert audited numeric E2E PASS beyond the logs below.

## 1. CURRENT MAIN FLOW — OWNER-TESTED

```text
Production Planning (XLSX; Draft → Published)
  → RO Toko (XLSX; Confirmed)
  → RO Confirmed Koreksi [before Pre Produksi; reason audited]
  → RO Konsolidasi (per delivery date + slot, per kitchen + SKU)
  → Pre Produksi (locked RO allocation snapshot and proration/shortage)
  → Produksi OK (one confirmed MO per kitchen + SKU)
  → Material Requirement → CDC → kitchen raw material transfer
  → MO Done (WITHOUT Work Orders)
  → Produk Jadi ke Packing (one-click native Internal Transfer per kitchen per batch)
  → DO Toko generated automatically from frozen RO allocations
  → Picking Operations / Picking List (native Odoo report) for Packing staff
  → Operator checks actual Qty, zero Qty notes
  → Validate Packing DO: PCK/Stock → Inter-warehouse transit
  → Store Receipt: Transit → Store Stock only upon receipt validation
```

The owner has tested the **RO Toko → Stok Toko** journey in the UI and said `good`. Maintain this workflow and do **regression tests** before changes. Source code in GitHub does not prove it is present on main database.

## 2. MENU DESIGN APPROVED

Principle: **Menu follows workflow; system supports SOP; minimize operator clicks.** Grouped menu below **YA Production Capacity**:

- **SEBELUM PRODUKSI**: Production Planning; RO Toko - Download Template; RO Toko; RO Confirmed Koreksi; RO Konsolidasi; Pre Produksi.
- **PROSES PRODUKSI**: Material Requirement; MO Produksi. Native inventory operations (CDC→dapur) remain under their corresponding transactions where applicable.
- **SESUDAH PRODUKSI**: Produk Jadi ke Packing; DO Toko.
- Do not move an operational step to a misleading stage merely because Odoo labels it `Packing`. **Packing** refers to physically finished goods/preparation; **RO Konsolidasi** is before production.
- Current grouping provided by `ya_workflow_navigation`.

## 3. DATA CONTRACTS / OPERATOR POLICIES

- RO originates from Published Planning; one RO for each store+kitchen+date+slot. Upload Qty once; no repeated 500-SKU manual typing.
- Consolidation persists `ya.packing.batch`, `line_ids`, `allocation_ids`, `ro_ids`. Each `ya.packing.batch.allocation` stores store/product, `qty_requested`, `qty_allocated`, `qty_shortage`. MO by kitchen+SKU in released batch.
- **No WO** in current MO workflow; avoid reintroducing automatic WO.
- MO output is posted to source kitchen's stock. Transfer **only actual Done MO output for THIS batch** to PCK/Stock; do not transfer full kitchen on-hand. Dapur and Packing are co-located → one-step native completed Internal Transfer, no unnecessary pick/receipt on this handoff.
- WIP SKU `11076` (filling Jamur) explicitly excluded from finished-goods handoff in tested scenarios; more general WIP/package classification needs review rather than unverified blanket automation.
- DO demand comes **directly from frozen RO allocations**. One native DO per store per batch. Generating DO alone moves no stock.
- Packing preparations use the **standard Odoo Picking Operations PDF**, technical `stock.action_report_picking` (`stock.report_picking`); the unused custom QWeb file stays in repository but is **not listed in the addon manifest**. Standard report was checked via read-only report metadata; PDF output detail per operator must be checked if changed.
- On a DO, Qty Kirim 0 is legitimate if production cancelled/unavailable. **SKU and original RO allocation must remain visible**, with user-entered **Alasan Tidak Dikirim**; no fictitious shipment. Example SKU `10031` production cancelled; `11076` WIP not eligible. Custom `stock.move.ya_do_not_shipped_reason` and editable `description_picking` with `Catatan: ...` under SKU; preserve note and stock logic.
- On dispatch validation stock goes PCK/Stock → Inter-warehouse transit. **Store stock must not increase until the destination store validates its incoming receipt**. Avoid one-step direct transfer PCK→Store that posts stock early.
- Avoid negative stock; actual moved Qty must be <= available source Qty. Don't overwrite actual RO allocation to hide shortages or cancelled production.
- **Rakit Paket di Packing** is a separate manufacturing-like flow, explicitly postponed until **after** RO→store receipt worked. That condition is now met by owner testing: **this is the NEXT feature**, not canceled. Do not graft it into the stable DO flow until business design is reviewed.
- Owner preference: operational simplicity, low clicks, use native Odoo stock documents and SOP where possible, not excessive UI locks.

## 4. SPECIFIC LOGS AND EVIDENCE — do not inflate claims

- `script/test_finished_packing_transfer_rollback_ya.py` on DB `erp-yussyakmal-mrp-test`:
  `EXPECTED_KITCHEN_SKU: 12`, `EXPECTED_PICKINGS: 1`, `EXPECTED_WIP_EXCLUDED: 11076`; `NATIVE_TRANSFER_VALIDATION_PASS`, `STOCK_DELTAS_PASS`, `DOUBLE_CLICK_GUARD_PASS`, `ROLLBACK_VERIFIED_NO_PICKING_PERSISTED`, `FINISHED_PACKING_E2E_ROLLBACK_PASS`.
- Read-only audit `script/audit_packing_to_store_do_readonly_ya.py`:
  Batch `2026-Nov-25 S3` (Metro) one RO, 14 allocation lines, **no linked FG transfers at audit timestamp**; batch `2026-Nov-27 S1` (Kedaton + Sudirman) 3 RO, 34 allocations, completed FG pickings `GRG/INT/00001`, `ASN/INT/00001`. This is a snapshot, not permanent truth.
- Same audit showed SKU `10031` and `11076` PCK physical zero despite positive RO allocation. Don't silently ship them.
- Read-only transit audit `script/audit_packing_store_receipt_route_readonly_ya.py`:
  one `Inter-warehouse transit`, `PCK/Stock` and three store sample locations `T_KD/Stock`, `T_MET/Stock`, `T_SD/Stock`; paired PCK→transit and transit→store stock rules existed; `READ_ONLY_PACKING_STORE_RECEIPT_ROUTE_OK`. Native operation types PCK outgoing and store incoming verified.
- `script/audit_native_picking_report_readonly_ya.py`: `NATIVE_PICKING_REPORT_AVAILABLE_OK` for `stock.action_report_picking` on `stock.picking` / QWeb-PDF.
- Operator screenshot of a created DO showed standard form in Ready with `10031 Pastel Panggang Kecil` `Not Available`, Demand 47, Qty 0, and inline free text `Tidak di kirim Karena produksi Gagal`. Subsequent GitHub code synchronized `Catatan: ...` to non-shipment reason; **individual final UI retest of that small code change was not provided**.
- Owner directly reported full `RO TOKO ---- > STOCK TOKO good` after these steps. Status **USER-TESTED PASS**, not a separate technical proof of every accounting/valuation condition.

## 5. ADDONS AND RELEVANT CODE

- `ya_production_planning`: Production Planning.
- `ya_store_ro`: RO template/upload, Confirmed correction, consolidation, immutable allocations, preproduction release to MOs.
- `ya_material_requirement`: Material Requirement and CDC/kitchen components.
- `ya_finished_packing_transfer`: test-DB kitchen→PCK one-step stock transfer (native picking per kitchen per batch; WIP exclusion); batch form action.
- `ya_workflow_navigation`: 3 operational menu groups.
- `ya_packing_store_delivery`: generate DO per store, print standard Picking Operations, dispatch→transit, linked incoming receipt, zero-QTY reason.
- `addons/ya_packing_store_delivery/report/store_picking_list.xml` is **legacy unused code**; not in manifest, do not claim it is active.
- Previous purchasing/multi-UoM/receiving/OCA material is retained in older documents and remains a separate scope.

## 6. NEXT WORK — RAKIT PAKET DI PACKING

**OWNER CONFIRMED DEFINITION (23 NOV 2026):** **Produk Paket adalah SKU produk jadi yang dibuat melalui BoM; semua komponennya merupakan PRODUK JADI dari satu atau lebih dapur produksi.** Paket dirakit di Packing sebagai proses produksi/perakitan tahap kedua; bukan pembuatan ulang masing-masing komponen. Komponen produk jadi dari dapur masuk ke `PCK/Stock`, kemudian dikonsumsi oleh BoM Paket pada saat perakitan, dan outputnya adalah stok SKU Paket Jadi di Packing. Ini berbeda dari sekadar membungkus beberapa SKU tanpa membuat SKU produk jadi paket. Komponen harus berkurang dan SKU Paket harus bertambah sesuai kuantitas aktual hasil rakitan, tanpa stok ganda.

**Implementation still pending.** Do not code before read-only analysis of actual SKU Paket, their finished-product BoMs, warehouse/locations and stock. Do not assume package quantities, timing, reservations, batch splits, operator role or allocation policy without owner approval.

Suggested *questions to resolve from real data*, not assumed policies:
1. Which SKU are finished **package SKUs**, their BoMs, and whether all components are finished-stock SKUs (no accidental WIP-only components).
2. Are package quantities driven by store RO allocations, a dedicated Packing assembly plan, or both? Decide how package demand fits the Planning→RO→MO pipeline without double producing.
3. On hand at PCK, reservations/other commitments, and product stock location/UoM per component.
4. How many clicks and which operator role; one native MO per package SKU/batch vs another documented mechanism, BoM quantities, WIP, expiry/FEFO, shortages and partial assembly rules.
5. Source of SKU/package completion/qty, actual component consumption, output package stock, per-store DO allocation and how all documents link.
6. Determine workflow for package assembly **before** or **after** the ordinary store DO generation when required, without delaying unrelated SKUs.
7. Build separate addon or narrow extension in **DB test** with non-negative stock and double-click guard; first read-only audit, then rollback E2E test, then GUI operator test.

**First deliverable:** a read-only package SKU/BoM/warehouse audit and a documented proposal for owner approval. **Do not prematurely create package MOs or move stock.**


## OWNER RULE — BOM PACKAGE EXPLOSION MUST HAPPEN IN RO CONSOLIDATION (23 NOV 2026)

**This rule is approved.** Before production, store RO for Paket SKU must be expanded into FINISHED-GOODS component demand according to Paket BoM. Component demand is added to direct store demand for that product, grouped by its SOURCE KITCHEN, and becomes production demand for kitchen MO. The Paket SKU itself is an assembly demand for Packing, **not a kitchen production line**.

Exact example from owner:
- Paket X BoM = 1 × finished Y + 1 × finished Z.
- RO store demands Y=10, Z=10, X=5.
- Pre-production consolidation / kitchen demand becomes **Y=15; Z=15**; Packing assembly requirement **X=5**.
- On arrival in PCK, allocate **Y=5 and Z=5 to assembly**, make **X=5**, then only **Y=10, Z=10, X=5** are destined to store.
- Never ship 15 Y and 15 Z to store; those include package components. Never count Paket X as an independent kitchen output or count component demand twice.

Formulas (same slot/date and relevant store demands):
```text
Kitchen demand(component C) = direct_store_RO(C)
  + sum_over_package_ROs(package_qty(P) * package_BoM_qty(C per P))

Packing assembly demand(P) = store_RO(P)
Store distribution demand(C) = direct_store_RO(C), NOT expanded kitchen qty
Store distribution demand(P) = store_RO(P) once assembly is completed
```

**Important implementation gap:** Existing owner-tested RO→store flow does not establish package BoM explosion in RO consolidation. Current immutable allocations and existing kitchen/MO generation must be audited BEFORE changes. Explosion must preserve independent vectors (direct store delivery vs component demand for assembly), link source RO/BoM/snapshot, and respect existing capacity/prorata/rounding decisions. Define treatment of shortages and final allocations if capacity limited; do not assume original formula can be applied unchanged in insufficient-capacity cases. Avoid changing established ordinary SKU behavior; regression-test no-paket RO, mixed paket+nonpaket, multi-kitchen components, multiple stores, duplicate components, cancellation, shortage, and inventory reconciliation.

**STATUS: business rule confirmed, implementation NOT YET DONE or TESTED.**


## OWNER RULE — IDENTIFY PACKAGE SKU BY PRODUCT CATEGORY

**Confirmed by owner on 2026-Nov-23:** A sellable Product Paket is identified by the product's Product Category **`All / Produk Jadi / Paket`**. At RO consolidation time, use the category master to distinguish Paket from normal finished goods. Do **not** infer Paket from a product name, code prefix, BoM existence alone, or manual hardcoded SKU list.

Implementation target:
- Resolve the category reliably using the full category path (Odoo `product.category.complete_name` and category hierarchy), rather than just matching the leaf label `Paket` since duplicate names are possible. Audit the exact category ID and whether subcategories are present before deciding whether descendants count.
- On positive Paket SKU demand from store RO, read its valid BoM and explode quantities of finished-component SKU into kitchen-production demand, keeping Package assembly demand separately.
- Example: Paket X contains Y×1 and Z×1. Direct RO Y=10, Z=10, X=5 → production demand Y=15, Z=15; Packing assembly X=5 consumes Y=5,Z=5; DO demand Y=10,Z=10,X=5.
- Do not silently classify a BoM-equipped **non-Paket** SKU as a package; it may be an ordinary kitchen product. If a categorized Paket has no valid BoM, report a blocker rather than guess.
- Package category and BoM detection **not yet deployed or runtime-tested**. Read-only category/BoM audit must come first; then implementation+regression test.

## 7. DEPLOY / HANDOVER RULES

- Read `doc/SKILL_ODOO19_ADDON_WORKFLOW.md`.
- GitHub commit → Feri `cd ~/odoofromzero && git pull` → Python source checks → backup DB test → copy only changed addon into `/opt/odoo19/custom-addons` → `sudo chown -R odoo19:odoo19` → `-i` new or `-u` upgrade using `-c /etc/odoo19.conf -d erp-yussyakmal-mrp-test --stop-after-init --no-http` → inspect exit/log → restart service when safe → GUI regression test. Git pull alone never deploys.
- **Never run untested custom inventory writes on primary DB `erp-yussyakmal`.** Don't overwrite live company master data with test DB content.
- For a new scope, produce source-only + read-only audit first, then rollback test on test DB, then owner UI acceptance. Store provenance, version, commit, dates and checks.

## 8. REFERENCES / HISTORICAL DOCS

- [Handover primary historical](HANDOVER_ODOO_FROM_ZERO.md)
- [MRP history](STATUS_PENGEMBANGAN_MRP.md)
- [Earlier 20 Nov handoff](ODOO_FROM_ZERO_HANDOFF_2026-11-20.md)
- [Packing DO source checkpoint](CHECKPOINT_2026-11-23_PACKING_STORE_DO_SOURCE.md)
- [Rakit Paket deferred and reactivated](CHECKPOINT_2026-11-23_PACKING_PACKAGE_ASSEMBLY_DEFERRED.md)
- [MO material CDC](CHECKPOINT_2026-11-23_MO_MATERIAL_CDC.md)
- [Kitchen buffer](CHECKPOINT_2026-11-23_KITCHEN_BUFFER.md)

## 9. COPY-PASTE HANDOVER TO NEW CHAT

> Lanjutkan project ODOO FROM ZERO dari `doc/HANDOVER_ODOO_FROM_ZERO_2026-11-23_RO_TO_STORE_PASS.md`. Database test yang boleh disentuh `erp-yussyakmal-mrp-test`, utama `erp-yussyakmal` dilarang untuk uji. Owner sudah mencoba UI `RO TOKO → STOCK TOKO` dan menyatakan **good**; jangan reset fase RO/MO/DO atau menganggap accounting/HPP seluruhnya terbukti. Menu mengikuti flow, NO WO, alokasi RO immutable, FG Dapur→PCK satu langkah, DO Packing→transit dan penerimaan baru posting stok toko, Picking Operations standar Odoo, Qty 0 dengan alasan yang bisa ditulis tepat di bawah SKU. Sekarang buka lagi milestone **RAKIT PAKET DI PACKING**. Audit read-only SKU paket, BoM, serta lokasi/stok terlebih dahulu; usulkan flow sederhana, baru tulis kode setelah keputusan bisnis jelas. Simpan bukti uji dan perbarui handover.

## AUDIT PACKAGE BOM — 23 NOV 2026: MIXED COMPONENT TYPES (IMPORTANT CORRECTION)

Feri ran `script/audit_package_category_bom_readonly_ya.py` on `erp-yussyakmal-mrp-test` and obtained `READ_ONLY_PACKAGE_CATEGORY_BOM_OK`. Feri states there are **more than 200** Paket SKUs; this is a user-provided approximation, not a verified exact count. Examples:
- Paket SKU 12298 `Wedding Sepinggan Tanah Lado Set B`: BoM 1584, 7 lines. Components include `All / Produk Jadi / Jajan Pasar`, `Legit`, `Pastry`, plus `All / Konsinyasi Masuk` and `All / Packaging`.
- Paket SKU 12299 `Wedding Wajik Pandan`: BoM 1429, 4 lines, containing `All / Konsinyasi Masuk` and `All / Packaging` but **no component under Produk Jadi** in the provided sample.

**Correction of earlier oversimplification:** Paket is identified by its own category `All / Produk Jadi / Paket`, but its BoM is **NOT necessarily composed only of products manufactured in kitchens**. `REVIEW_COMPONENT_NOT_UNDER_FINISHED_CATEGORY` in the old audit is a review marker, **not an invalid BoM error**. Real Paket BoMs may legally contain finished kitchen products, incoming consignment products, and packaging. Do not delete/modify such BoMs or assume consignment/packaging is wrong.

**Category-specific component requirements at RO consolidation:**
1. Finished-goods component from `All / Produk Jadi / ...` except the package root: add to the originating kitchen production demand (direct store RO + exploded package demand, allocated separately). Production route is subject to relevant master data.
2. `All / Konsinyasi Masuk`: require availability/procurement from consignment stock; do **not** generate kitchen MO automatically.
3. `All / Packaging`: require material for package assembly; do **not** generate kitchen MO automatically.
4. Unknown/other categories, package nested within package, or missing/multiple matching BoMs: **audit and flag**, do not silently create MOs or exclude quantities.
5. All BoM materials remain required for assembly in Packing; differentiate their replenishment paths. Never multiply shipped store quantities by component demand.

No runtime package expansion has been implemented or tested. Exact category census, multi-category handling, consignment ownership/location, packaging availability, and valid BoM selection still need read-only checks before implementation. Preserve existing RO→stock toko user-tested flow for non-package SKUs.

## OWNER SCOPE DECISION — TWO COMPONENT SOURCES; CONSIGNMENT PROCUREMENT OUT OF SCOPE

Confirmed by owner on 2026-Nov-23:

1. A Paket BoM can consume **manufactured kitchen finished goods** and **consignment products purchased from suppliers** (plus packaging as present in the existing BoMs).
2. **Kitchen-produced finished goods**: store RO Paket demand explodes its BoM into additional **kitchen production requirement before manufacturing**; the ordinary manufacturing and finished-goods-to-Packing flow provides stock in `PCK/Stock`.
3. **Consignment goods**: replenishment is handled by **a separate standard Odoo Purchasing/Inventory process**: buy from supplier and deliver/receive into the Packing warehouse. **PO creation, supplier purchasing, consignment receiving and replenishment rules are explicitly OUT OF SCOPE for the RO consolidation / Paket assembly workflow being implemented now.** Never auto-create Purchase Orders or incoming receipts as part of Paket consolidation. The existing procurement process remains independent.
4. **Interface/stock dependency**: package assembly still consumes its consignment SKU quantities from actual available Packing stock under the BoM; the custom workflow must not assume consignment stock magically arrives. Insufficient ingredients (manufactured, consignment, or packaging) must prevent fictitious successful assembly; report the shortage to the operator. The consignment supply process is independent, not an automatic extension.
5. Packing assembly consumes component quantities from all included categories and creates the finished Paket SKU. DO to stores draws on finished Paket available in Packing, preserving RO allocations and actual shipped qty.

**Scope boundary:** implement Paket BoM demand explosion **only to kitchen manufacturing** for kitchen-produced components and actual assembly consumption/output in Packing; **do not implement a custom consignment procurement workflow**. The presence of consignment components in BoMs is valid. The earlier audit marker `REVIEW_COMPONENT_NOT_UNDER_FINISHED_CATEGORY` is NOT a BoM error.

**Status:** business policy confirmed, runtime implementation not yet done/tested. Packaging stock sourcing policy remains as in existing standard flow; do not invent a new procurement feature for it.

## PRIORITY OVERRIDE — PACKAGE COMPONENTS BEFORE DIRECT STORE ALLOCATION (OWNER 2026-11-23)

**Owner clarification (authoritative, overrides any older contradictory flow):** **Rakit Paket dilakukan sebelum alokasi toko.** Paket has higher allocation priority over store RO requests for ordinary finished-good SKUs that are also consumed as Paket components. This priority must be reflected in pre-production planning and in physical Packing allocation. DO must never allocate component stock to normal RO before Paket requirements are fulfilled.

Example: Paket X BoM = Y×1 + Z×1. Store RO Y=10, Z=10, Paket X=5 → kitchen gross demand Y=15 and Z=15. **First reserve/consume Y=5 and Z=5 to assemble X=5**, then assign remaining Y=10, Z=10 to direct store RO. Store receives 5 X, 10 Y, 10 Z, never 15 Y / 15 Z.

Shortage example: if finished Y actual=12 rather than 15, the package component requirement Y=5 has priority, leaving only Y=7 for ordinary store RO (shortage of 3). Package assembly completion nevertheless requires *all* BoM components present including Z, purchased consignment components, packaging and applicable source/location/traceability; do not post fictitious completed packages. For multiple Paket SKUs competing for scarce components or incomplete package components, the allocation/tie-break and handling of unbuildable reservation still require explicit detailed design, not arbitrary iteration order.

**Required logical sequence**:
1. RO consolidated across stores with Paket recognized from category `All / Produk Jadi / Paket` and BoM explosion; compute kitchen gross production demand including package component needs, without modifying direct RO demand.
2. Carry package component priority as a distinct *protected demand bucket* into Pre Produksi and actual Packing stock allocation; do not prematurely allocate all Y/Z to ordinary RO.
3. Following MO Done / kitchen→PCK receipts, ensure package components are available, then assemble Paket using native stock consumption and finished package receipt in PCK (subject to owner-approved shortages/timing).
4. **Only after package assembly/priority accounting** calculate and finalize direct-store allocations of leftover ordinary finished SKUs; package SKU itself allocated as finished package according to RO.
5. Generate DO → native Picking Operations → Dispatch → Transit → Store Receipt.

**CRITICAL INTEGRATION GAP:** existing RO Consolidation/Pre Produksi currently computes immutable store allocations before manufacturing; owner now specifies Paket is *before store allocation*. Existing code cannot be assumed compatible. Do not simply insert a Paket MO after frozen normal allocations. Study current models/actions and redesign only the necessary boundary between package-priority reservation and final store allocation. Preserve current RO→stock toko PASS path for batches without Paket, and regression test. **Business requirement confirmed; code NOT implemented/tested.** Consignment PO/receipt remains standard Odoo and outside custom flow.

## CODE REVIEW — PACKING PACKAGE INTEGRATION (23 NOV 2026)

Read actual current repository sources:
- `addons/ya_store_ro/wizard/packing_preview.py`: `action_preview` iterates **RO lines ONLY**, groups by `(planning_id, product_id)`; source SKU must be present in same RO's Published Planning; `allocate_capacity_prorata` immediately calculates per-store allocations; `action_move_to_preproduction` creates immutable batch/lines/allocations.
- `addons/ya_store_ro/models/packing_batch.py`: `action_generate_selected_mo` checks **each line.qty_requested = sum original RO direct demand**, compares `planned_keys = current_keys` from original RO lines, and final validates `sum(store allocated) + sum(MO rounding surplus) = sum(MO production)`. All three assumptions will be invalid if component production demand includes package explosion but package components are reserved first. **Do not patch preview demand calculation alone.**
- `ya.packing.batch.allocation` is immutable and is read by `ya_packing_store_delivery` to generate DO; need separate protected Paket component-demand snapshot (NOT fake store allocation rows). Ordinary store allocations must represent **direct RO only** and be finalized after higher-priority package allocation is protected.
- Package SKU in category `All / Produk Jadi / Paket` may or may not appear in normal Published Kitchen Planning; check this before deciding how RO importer and release handles it. Treat Pakets as Packing assembly output rather than kitchen MO output; existing code presently requires kitchen Planning for every RO line.
- Package BoMs actually contain finished kitchen, consignment and packaging lines. Only finished-kitchen components increase dapur MO demand; all classes must be available at package assembly. Supplier replenishment via standard Odoo is OUT OF SCOPE.
- **Source-only diagnostics committed:** `script/audit_package_ro_planning_link_readonly_ya.py` (read-only Odoo shell; category/planning/confirmed RO/BoM category matrix) and `script/test_package_priority_pure_ya.py` (standalone arithmetic regression for Y/Z/X, shortage, no package, competing packages). Scripts have **not been executed by Feri** as of this checkpoint.
- IMPORTANT: `script/test_package_priority_pure_ya.py` models component stock priority only and does NOT compute valid final quantities of assembleable full packages when any BOM component is missing. No package production feature is installed. Next: run both audits, inspect outputs, then design atomic allocation+package demand model and regression-test existing no-package path before deploying.

## ACCOUNTING GATE — OWNER PAUSED PACKAGE DEVELOPMENT (23 NOV 2026)

Owner noticed RO Toko→Stok Toko passed *operational* test, but asked whether **background Accounting/Inventory valuation/Manufacturing costing** was verified. **Answer: NO, end-to-end finance/valuation was not audited; do not infer success from stock quantity test.** Existing documentation already called out this cross-module requirement in 22 Nov accounting principles.

**New immediate priority:** validate finance before further Paket implementation. Source-only read-only diagnostic: `script/audit_mrp_inventory_accounting_readonly_ya.py`, only `erp-yussyakmal-mrp-test`. It reads installed modules (incl. `stock_account`, `mrp_account`), actual product/category costing & valuation, sample SKU costs, warehouses/transit and accounting/SVL model availability, and recent batch/picking states. It does **not** conclude journals are correct and does not modify DB.

**Required financial acceptance test (pending):** for an identifiable batch and stock moves, reconcile (a) starting and ending Qty, (b) stock valuation layer/value or relevant Odoo19 valuation mechanism, (c) raw material consumed and finished product cost from MO including correct WIP/overhead behavior (if configured), (d) internal Dapur→PCK→Transit→Toko transfer ownership/location and that it **does not represent customer sale** or prematurely recognize sales COGS, (e) general ledger movements/timing according to Odoo19 Community + installed OCA setup. Compare account balances on relevant dates, identify gaps, avoid claiming one journal per internal transfer is expected. No manufacturing-Paket or accounting posting changes until reviewed. Any test writes only on test DB with backup/rollback and documented reconciliation.

**User acceptance RO→Stok Toko PASS remains valid for logistics; accounting is a separate OPEN GATE.** Pause package integration until accounting review yields a scoped action plan. Historical manufacturing/RO pass must not be relabelled financial pass.

## ACCOUNTING READ-ONLY AUDIT RESULTS — 23 NOV 2026

Feri executed `script/audit_mrp_inventory_accounting_readonly_ya.py` on `erp-yussyakmal-mrp-test`. Output showed `READ_ONLY_MRP_INVENTORY_ACCOUNTING_AUDIT_OK`, meaning **diagnostic completed**, NOT accounting reconciliation success.

- Batch 3 `Packing 2026-Nov-23 S2`: `production_ok`, 1 MO; `PCK/OUT/00005` **done** (1 dispatch stock move); `T_RAI/IN/00001` **done** (1 store receipt move). **Preferred first finance trace target**.
- Batch 2 `Packing 2026-Nov-25 S3`: `production_ok`, 14 MOs, no store-transfer lines shown in this diagnostic.
- Batch 1 `Packing 2026-Nov-27 S1`: `production_ok`, 20 MOs; `PCK/OUT/00003` assigned (20 lines) and `PCK/OUT/00004` assigned (14 lines), so do not claim store receipt done for these.

**Next script (source-only; not yet run):** `script/audit_batch3_mrp_to_store_valuation_readonly_ya.py` retrieves Batch3 MO and stock moves, related store dispatch/receipt, source/destination usage, any `stock.valuation.layer` and directly linked `account.move` entries available. This audit must NOT be treated as a financial PASS just because it prints `READ_ONLY_BATCH3_FINANCIAL_TRACE_OK`. Odoo19 journal timing depends on configuration; zero directly linked GL moves can be legitimate and demands informed interpretation. Further reconcile actual values, costs, GL closing with accountant.

## ACCOUNTING BATCH 3 TRACE — ODOO 19 CORRECTION, 23 NOV 2026

Feri ran `script/audit_batch3_mrp_to_store_valuation_readonly_ya.py` on `erp-yussyakmal-mrp-test` and obtained `READ_ONLY_BATCH3_FINANCIAL_TRACE_OK` (diagnostic only).
- Batch 3, `2026-Nov-23 S2`: MO `PST/MO/00001` ID42, SKU `12379`, **Done 40 Pcs**. Ten Done raw moves IDs 941–950, finished move ID951 (40 pcs Production→PST/Stock).
- `PCK/OUT/00005` Done stock move ID966 (10 pcs SKU12379 PCK/Stock→Inter-warehouse transit); `T_RAI/IN/00001` Done stock move ID967 (same 10 pcs transit→T_RAI/Stock).
- `SVL_AVAILABLE: False`; `GL_AVAILABLE: True`; no directly linked GL entries and `production_cost` field missing. **These are not proof of accounting failure**, because Odoo 19 reworked inventory valuation and journal recognition (including posting on invoicing/closing, depending on settings). The original script is an older-model trace and is NOT a suitable financial signoff on its own.
- Also **do not infer an accounting PASS** solely from these moves: explicit costs, valuation, accounts and periodic/continuous timing have not been reconciled.

**New source-only Odoo19-specific audit**: `script/audit_batch3_odoo19_cost_fields_readonly_ya.py` probes installed `stock_account`/`mrp_account`, company and category configuration, Odoo19 `stock.move` cost/valuation fields, MO costing fields, and actual Batch3 move values. Run READ ONLY; do not change accounting settings or install modules until its outputs are interpreted. Reference official docs: https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/inventory/inventory_valuation/cheat_sheet.html and https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/inventory/inventory_valuation/operations_valuation.html.

## ACCOUNTING — BATCH 3 COST TRACE FINDINGS (23 NOV 2026)

Feri ran `script/audit_batch3_odoo19_cost_fields_readonly_ya.py` on `erp-yussyakmal-mrp-test`, output `READ_ONLY_ODOO19_COST_FIELDS_OK`. Installed modules: account, stock, stock_account, mrp, mrp_account, purchase_stock, account_financial_report. Company inventory valuation `periodic`, inventory period `manual`, cost method `standard`, Anglo-Saxon `True`, valuation account `11300180 Inventory`. Category override for Bahan Baku, Konsinyasi Masuk, Packaging, Produk Jadi and Paket: cost method `average`, category valuation `real_time`, with specific inventory accounts (e.g. Bahan Baku 1130012, Barang Jadi 1130017), all to be interpreted against Odoo19 company effective settings.

For batch3 MO42 `PST/MO/00001`, SKU12379, 40 pcs:
- Raw stock.move IDs 941–950 were `is_valued=True`; their values: 9000 + 7600 + 123200 + 7800 + 33600 + 3062.5 + 7656.25 + 20570 + 10520 + 7000 = **230008.75**.
- Finished move 951 was `is_valued=True`, 40 pcs × unit cost `5750.21875`, `value=230008.75`.
- **Observed raw consumption value equals finished goods value exactly**, delta zero. This is a *material-to-finished product cost consistency check*, NOT proof of overhead/labor or company HPP account correct.
- PCK→transit outgoing 966, 10pcs, and transit→T_RAI incoming 967, 10pcs, both `is_valued=False` and `value=0` as internal/transit movements. **This does not itself mean the goods have zero asset value**, and does not create customer sale/COGS.
- Direct GL by stock move and accounting closing still requires checking; no automatic journal was observed in earlier legacy-style lookup. Odoo19 accounting may recognize inventory at invoices and at closing according to settings, not automatically one entry per move.

**Next:** read-only script `script/audit_batch3_accounting_closing_readonly_ya.py` to inspect direct `stock.move.account_move_id`, actual `remaining_value`, production location accounts, category/company settings. Subsequently accountant should compare Accounting > Review > Inventory Valuation and relevant posted/draft journal accounts and stock closing (do NOT post during diagnostic). **Accounting signoff NOT YET PASSED.** Paket work remains paused for accounting gate.

## ACCOUNTING — BATCH3 GL TRACE RESULTS (23 NOV 2026)

Feri ran `script/audit_batch3_accounting_closing_readonly_ya.py` in `erp-yussyakmal-mrp-test`, result `READ_ONLY_BATCH3_ACCOUNTING_CLOSING_OK`.
- Company: `inventory_valuation=periodic`, `inventory_period=manual`, `cost_method=standard`, `anglo_saxon_accounting=True`, inventory valuation account `11300180 Inventory` (`asset_current`). Category configs read earlier are average cost + real_time, and effective semantics remain subject to Odoo 19 accounting reconciliation.
- MO `PST/MO/00001` (SKU 12379): raw valued stock.move sum **230008.75**, finished stock.move 951 **230008.75**, delta **0**, `extra_cost=0`. Evidence supports **material-valued MO consistency**, not overhead/labor costing.
- Finished move `remaining_value=230008.75` as reported; do **not** misinterpret this alone as current value at individual store locations, since internal/transit movements `966`/`967` are nonvalued and 10 pcs passed to store.
- Raw valued moves 941–950 each `account_move_id=False`; finished move 951 `account_move_id=False`; internal/transit 966/967 `is_valued=False` and `account_move_id=False`. **No directly linked GL entries**: expected/not expected must be judged from Odoo19 company periodic/manual settings and closing process, not from pre-19 assumptions.
- Production Location ID 12, usage production, company My Company; no custom valuation in/out account fields appeared in the audit.
- **Financial close/reconciliation NOT YET PASSED.** Next read-only script `script/audit_inventory_gl_balance_readonly_ya.py` prints category/company inventory-related account mapping and posted/draft GL totals, plus SKU12379 effective category config. Compare with Odoo19 Inventory Valuation report at the same company/cutoff and opening balances; do not post manual valuation closing entries just to clear audit.

**Decision gate:** Continue to hold expansion to Package assembly until stock valuation vs financial reporting is assessed, or owner explicitly reprioritizes. Operational RO→store PASS remains intact.

## TENTATIVE OWNER ACCOUNTING POLICY — BOP GLOBAL, NOT PER-SKU BOM (23 NOV 2026)

Owner stated **possible** policy (not yet final approval): overhead production (BOP), including utilities such as electricity and gas, may be recorded/allocated globally rather than inserted into per-product BoMs. **Do not assume approved permanent financial treatment or make accounting configuration changes from this alone.**

- Existing Batch3 `PST/MO/00001`: direct material stock move values total `230008.75`, finished output `230008.75` for 40 units; `extra_cost=0`. This is currently a **material-based unit manufacturing cost**, and does not establish that electricity, gas, factory labor, depreciation or production overhead have been absorbed.
- Separate **operational/managerial product-level direct material cost** from **financial statement inventory valuation and COGS**. Not putting gas/electricity in SKU BoM is feasible; it **does not necessarily exempt relevant conversion overhead from financial inventory valuation**. PSAK 202 / IAS 2 generally require systematic allocation of applicable fixed and variable production overhead to conversion costs, depending on reporting framework; nonallocated abnormal overhead may go to expense. Have accounting professional define capitalization, timing, allocation basis, and period close.
- Decide explicitly which production labor, packaging, gas and electricity are direct components vs indirect BOP, accounting for the fact that packaging physically incorporated in products can already be included as a BoM component.
- Avoid custom BOP-per-SKU or automatic BOP global journals until owner/accounting determines methodology and GL reconciliation.
- Accounting valuation/GL closing audit remains OPEN; do not mark full HPP PASS based solely on raw=finished MO value.

## OWNER DECISION — BOP THROUGH SEPARATE ACCOUNTING TRANSACTIONS (2026-11-23)

Owner clarified the previously tentative BOP proposal: **electricity, gas and labor costs are to be recorded via their own Accounting transactions / manual journal at payment or the appropriate accounting recognition date**, not through automated manufacturing background postings, extra MO cost, or electricity/gas/labor lines in individual SKU BoMs. Accounting handles these transactions separately from the RO→MO→Packing→Store logistics workflow.

**Implementation boundary:** do not build automatic BOP allocations per SKU, do not silently add BOP to MO `extra_cost`, and do not change existing physical-component BoMs to carry nonphysical utility expenses. Operational SKU cost remains material-based unless separately configured by owner.

**Finance caution:** Payment date and expense recognition are not always identical (accruals, payroll payable, prepaid utilities); the Accounting team selects suitable entries. Under applicable financial reporting standards, eligible manufacturing conversion overhead may need systematic allocation into inventory/COGS at period end, even if not tracked in SKU BoMs. Such period-end adjustments belong in Accounting closing policy, not this automated production flow. This is a reporting caveat, NOT an instruction to implement automatic per-MO overhead.

**Existing accounting gate remains open:** Validate real stock.move costing and stock-to-GL reconciliation for materials and finished goods, separately from owner-managed manual BOP journals. The existing test of Batch3 materials matching finished goods does not establish fully absorbed financial HPP.

## SCOPE FREEZE — BOP STANDARD ACCOUNTING, NOT THIS MRP FLOW (OWNER RECONFIRMED)

Owner reconfirmed the prior BOP decision: BOP expenses (electricity, gas, labor, etc.) belong to a **separate flow in the standard Odoo Accounting module**, completely outside the active custom RO→Manufacturing→Packing→Store workflow. Do **not** request BOP allocation, modify BoMs to insert nonphysical utilities, or generate BOP journals as a prerequisite for the operational project. Any accounting policy / period-end financial reporting treatment remains the Accounting team's separate responsibility, not an extension of the current ERP production design.

**Current active accounting work ONLY:** validate material/finished-product operational valuation and how it reconciles to actual accounting ledger or Odoo19 periodic inventory closing. Script ready: `script/audit_inventory_gl_balance_readonly_ya.py`. Source exists in GitHub; run on test DB and inspect its posted and draft GL account balances. This is a diagnostic; a financial PASS requires comparing at a common cutoff with Inventory Valuation and opening balances. After accounting gate decision resume Package-first manufacturing & assembly. No production DB changes.

## ACCOUNTING GL ACCOUNT AUDIT — RESULTS AND 19.0 PERIODIC INTERPRETATION (23 NOV 2026)

Feri ran `script/audit_inventory_gl_balance_readonly_ya.py` on `erp-yussyakmal-mrp-test`; output `READ_ONLY_INVENTORY_GL_BALANCE_OK`, read-only only. `company.inventory_valuation=periodic`, `company.inventory_period=manual`, IDR, company `My Company`.

Posted ledger totals across all available dates (NOT same-cutoff or opening-adjusted):
- `1130012` Persediaan Bahan Baku: 6 posted lines; debit 379824.00; credit 0; net **379824.00**.
- `1130013` Persediaan Bahan Pembantu: 0 posted/draft, net 0.
- `1130014` Persediaan Barang Konsinyasi: 0 posted/draft, net 0.
- `1130017` Persediaan Barang Jadi: 0 posted/draft, net 0.
- `11300180` Inventory (company valuation account): 0 posted/draft, net 0.
- Sample SKU12379 Pastry: category average cost + category real_time, valuation account 1130017; product unit cost 5750.21875; test MO raw & finished stock.move value 230008.75 each.

**Interpretation:** source stock.move valuations DO EXIST and MO raw=finished. In **Odoo19 Periodic inventory accounting**, journal recognition for stock valuation can occur on inventory closing, rather than per each inventory move. Official Odoo19 documentation specifically says periodic valuation uses closing entries generated from Inventory Valuation report. This explains why zero posted product-finished ledger entries and no move-linked GL are plausible. **DO NOT call zero GL account entries a discovered failure, and DO NOT treat it as a successful reconciliation.** Test DB ledger totals are all-history aggregates and may contain purchases/import opening entries; the Rp379824 posted raw-material balance is NOT directly comparable with a single MO consumption of Rp230008.75.

**Next decision/acceptance gate:** identify whether Accounting > Review > Inventory Valuation is available in this installed Odoo 19 Community + OCA setup. At consistent company and cutoff (after Batch3 2026-11-23), inspect inventory physical valuation and generated **draft/proposed closing variation** without posting, compare with ledger balances and account mapping. If menu missing, audit installed account valuation report/closing code and find supported equivalent; never claim manual postings are automatically handled. If the test DB carries synthetic inventory balances or has no clean opening balance, record limitation and only sign off the mechanics, not real company GL totals. Do not post closing or alter configuration on production.

**Scope reconfirmed:** BOP separate standard Accounting workflow, completely out of current custom RO/MRP/Packing development. No BOP adjustments in SKU BoMs or manufacturing code. Package implementation can resume after accounting valuation **mechanics** and missing closing step have been identified and the operational integration gate is documented; full financial policy/period-end closing remains with accountant.

Official Odoo19 references:
- https://www.odoo.com/documentation/19.0/applications/finance/accounting/get_started/inventory_valuation.html
- https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/inventory/inventory_valuation/cheat_sheet.html

## CURRENT NEXT STEP — PERIODIC INVENTORY VALUATION CLOSING CAPABILITY (23 NOV 2026)

Owner requested continue following GL balance audit: company `inventory_valuation=periodic`, `inventory_period=manual`, Odoo19 stock.move value correctly captured; GL inventory accounts largely zero and have not been reconciled. **No source evidence of posted stock closing yet.**

New read-only source audit committed `script/audit_odoo19_inventory_valuation_closing_access_readonly_ya.py`: examine Odoo 19 Community installed valuation/closing modules, actual `ir.ui.menu` and `ir.actions.act_window` report routes, relevant model registry and available methods, and valuation journals. Does not execute actions or post/modify anything. The goal is to determine **whether an actual built-in accounting closing/report path exists**, rather than assuming an Enterprise screen is in Community. Run it on `erp-yussyakmal-mrp-test` then interpret output; only afterward design equal-cutoff valuation-versus-GL comparison. A script suffix `_OK` means diagnostic execution success, NOT financial PASS.

Owner BOP decision reaffirmed: overhead paid/booked through standard Accounting transactions, not background MO or custom package costing. Do not distract from inventory/finished-goods costing and its financial reporting.

## CLOSING CAPABILITY AUDIT RESULT — 23 NOV 2026

Feri reran corrected `script/audit_odoo19_inventory_valuation_closing_access_readonly_ya.py` successfully in `erp-yussyakmal-mrp-test`; result `READ_ONLY_ODOO19_VALUATION_CLOSING_ACCESS_OK`.

Observed:
- Company 1 `My Company`: `inventory_valuation=periodic`, `inventory_period=manual`, `cost_method=standard`, `account_stock_valuation_id=11300180 Inventory`, `anglo_saxon_accounting=True`.
- Installed `account`, `stock`, `account_financial_report`, `stock_account`, `mrp_account`.
- `ir.actions.act_window` 408 **Valuation** `res_model=stock.move`; action 407 **Adjust Valuation** `res_model=product.value`. Valuation report model `stock_account.stock.valuation.report` found in registry. Inventory Valuation menu under Accounting not found among existing filtered menu candidates (does not mean functionality absent; could be action/no menu/user rights).
- Odoo `res.company` methods found: `action_close_stock_valuation`, `_action_close_stock_valuation`, `_cron_post_stock_valuation`, `_get_location_valuation_vals`, `_get_stock_valuation_account_vals`, `_get_valuation_product_domain`.
- Journal 8 `Inventory Valuation`, code `STJ`, type general.

**Meaning:** standard Odoo19 valuation/closing code is present, but actual closing semantics, account mapping, posting behavior, user exposure, dated report values, and ledger reconciliation remain **NOT VERIFIED**. Never invoke `action_close_stock_valuation` speculatively: it might create/post accounting entries. The lack of move-linked GL entries during material consumption and MO Done is consistent with periodic/manual setup but not a full finance PASS.

**Next read-only source inspection**: `script/audit_odoo19_stock_closing_implementation_readonly_ya.py` (commit 20a6172) reads Python signatures and source of closing and mapping functions using `inspect.getsource`, plus report action metadata. **Does not execute closing methods**, alter data, or post entries. After Feri runs it, inspect its output and design controlled dry-run with rollback if justified, with test DB only. Avoid inventing an Accounting menu or closing wizard without verifying real accessible UI.

BOP: strictly outside scope, booked independently through standard Odoo Accounting.

## OWNER SCOPE GATE CLOSED — ACCOUNTING AUDIT DEFERRED, RESUME PAKET (23 NOV 2026)

Owner explicitly instructed that **Accounting transaction audit, inventory valuation GL reconciliation, and actual closing are OUT OF SCOPE for current RO→Manufacturing→Packing→Store flow**; handle them later when working on the separate standard Odoo Accounting flow. **STOP requesting more finance audit scripts/logs or posting/creating journal closing as a prerequisite for Paket.** BOP remains entirely in standard Accounting, not custom manufacturing. This is a **scope closure**, NOT a financial accounting PASS.

Last source inspection supplied by Feri (`script/audit_odoo19_stock_closing_implementation_readonly_ya.py`, output `READ_ONLY_ODOO19_STOCK_CLOSING_IMPLEMENTATION_OK`):
- Odoo19 `res.company._action_close_stock_valuation(at_date=None)` computes candidate journal lines from location valuation, stock valuation account and realtime variation.
- `res.company.action_close_stock_valuation(at_date=None, auto_post=False)` actually **creates an `account.move` and saves closing ID**; with `auto_post=True` also posts it; NEVER call this in a read-only audit. Monthly/daily cron triggers posting for eligible companies; current company period is manual.
- Source stock.move value of Batch3 MO raw materials `230008.75` equals finished output value `230008.75`; finished-stock and internal transfer quantities checked operationally. GL reconciliation remains intentionally DEFERRED to Accounting project.
- Inventory valuation action 408 (`stock.move`) and report `stock_account.stock.valuation.report` present. Account journal STJ exists. No accounting customizations necessary for manufacturing flow on the basis of this inspection.

**NEXT ACTIVE PRIORITY:** resume Paket assembly, remembering owner rule Paket allocation is hierarchically prior to ordinary direct store SKU allocation. Demand explosion from Paket BoM must add only manufactured-finished kitchen SKU demand; supplier consignment procurement stays in standard Purchasing/Inventory outside scope, packaging sourced as stock. Study existing RO consolidated snapshot/immutable allocations and implement package-priority buckets, production release, physical assembly before final ordinary store allocation and DO, with no-Paket regression tests. Financial closing audit is NOT a gate to proceeding further.

## PACKAGE RESTART — SOURCE MATH CREATED, ODOO INTEGRATION NOT YET DEPLOYED (23 NOV 2026)

Accounting audit intentionally paused by owner as outside this RO→Packing flow. Restarted package-first manufacturing integration.

**Current code-review finding:** `addons/ya_store_ro/wizard/packing_preview.py` currently requires every RO SKU to be part of its own Published Kitchen Planning; its `action_preview()` groups RO by `(planning_id,product_id)` and immediately calls `allocate_capacity_prorata()` **before package component protection**. `action_move_to_preproduction()` freezes these allocations. `addons/ya_store_ro/models/packing_batch.py` release insists MO SKU keys/quantities match direct RO SKU keys/quantities, which would reject extra kitchen component demand from Paket and mistakenly treat Paket as kitchen MO. `addons/ya_packing_store_delivery/models/store_delivery.py` consumes batch `allocation_ids` directly for DO and requires kitchen FG handoff. **All of these must be reconciled before any package RO end-to-end test.** Preserve existing behavior for no-package batches.

**New pure, not-wired source code**: `addons/ya_store_ro/models/package_priority_rules.py` separates (1) direct finished SKU RO, (2) package finished SKU RO for stores, (3) protected kitchen manufactured components for package assembly, (4) consignment/packaging stock requirements in PCK, and (5) kitchen gross production need. It explicitly refuses unknown/nested component sources and noninteger base-UoM component ratios (pending UoM adapter and nested package policy). It does not create Odoo records or reserve stock.
**New pure test:** `script/test_package_demand_buckets_pure_ya.py`, run `python3 script/test_package_demand_buckets_pure_ya.py`; expected `PACKAGE_DEMAND_BUCKETS_PURE_PASS` but NOT executed on Feri server yet.
**Data audit already available and awaiting Feri execution**: `script/audit_package_ro_planning_link_readonly_ya.py`, on `erp-yussyakmal-mrp-test`; expected `READ_ONLY_PACKAGE_RO_PLANNING_LINK_OK`. Inspect exact category Paket vs Published Planning, whether Paket RO rows exist, and kitchen components' planning routing. Also existing `script/audit_package_bom_category_summary_readonly_ya.py` covers all 200+ package BoMs by categories.

**Important design distinction:** Priority of package assembly over ordinary direct store allocation applies to actual packing allocation/stock, while published planning/capacity before production must include extra package manufactured-component demand. Do not issue kitchen MO for Paket SKU itself. Do not buy consignment automatically. Do not allocate normal store SKU first. Multiple package SKUs competing for limited components, incomplete BOMs, source mapping across kitchens, and real physical assembly MO at PCK are still unimplemented; do not claim package flow operational/pass.

**Next technical step after audit output:** build Odoo-specific adapter resolving real BoM output-UoM and component-UoM quantities, matching components to Published Kitchen Planning by delivery slot; carefully extend preproduction snapshot and release invariants (package protected bucket separate from immutable direct store allocation); make Packing assembly before direct store allocation/DO; protect no-package regression. Test exclusively in `erp-yussyakmal-mrp-test`.

## PACKAGE MASTER AUDIT — FERI RESULT 2026-11-23

Feri ran pure `script/test_package_demand_buckets_pure_ya.py`: `PACKAGE_DEMAND_BUCKETS_PURE_PASS` (**source-only calculation, no Odoo flow implemented**). Ran `script/audit_package_ro_planning_link_readonly_ya.py` on `erp-yussyakmal-mrp-test`: `READ_ONLY_PACKAGE_RO_PLANNING_LINK_OK` (**diagnostic completed, not implementation pass**).

Observed:
- Category `All / Produk Jadi / Paket` unique, **208 Paket SKUs**. **195** match one active BoM, **13** match zero, none multiple. No confirmed RO package lines. Across 21 Published Plans, only **SKU 12228** appeared as a package SKU in **two** plan lines (plan IDs 78 and 7, kitchen PST, max 1). Current RO XLSX is locked to a kitchen Published Planning SKU list, therefore current RO path cannot represent arbitrary Paket requests.
- 195 BoM totals: FINISHED_GOOD **686 lines**; PACKAGING **171**; CONSIGNMENT **26**; NESTED_PACKAGE **2**; OTHER **60**. These are line counts, not SKU count. 33 finished component **lines** lack any Published Planning match, while 653 lines have at least one match across all dates. Neither figure proves same date+slot kitchen availability.
- Blockers to safe all-208 activation: 13 no BoM; classify 60 OTHER; handle/exclude 2 nested package BoM lines; resolve missing Published Planning kitchen/slot components, BOM output UoM & component conversions; define eligibility not to accidentally treat Paket as dapur SKU.
- Explicit supplier consignment procurement stays standard Odoo Purchasing/Inventory, not custom; assembly only checks real PCK availability.
- **Priority invariant:** Paket component gross kitchen need before direct-store allocation; do not create kitchen MO for Paket itself. Protect no-Paket flow.

Next new source-only read-only diagnostic: `script/audit_package_exceptions_and_slot_readonly_ya.py` prints precise BoM-less Paket SKUs, OTHER component categories/examples, nested Paket examples, counts of unique missing component SKUs, and per-date/slot Published Planning route readiness. Run only in `erp-yussyakmal-mrp-test` before any RO/Pre Produksi ORM redesign. **Source audit script available, not executed.**

Current code gap: `ya.store.ro.planning_id` is required and RO import/template accepts only one Published Planning kitchen's SKU rows; a new Paket-demand entry design must maintain store/date/slot traceability without forcing a Packing SKU into fake kitchen Published Planning and without breaking existing direct RO. `packing_preview.py` and `packing_batch.py` both assume every planned MO corresponds to a direct store RO and must be refactored carefully with protected package-demand snapshot. `store_delivery.py` consumes existing final allocation rows, requiring final after package assembly. No Paket module installed, no end-to-end Paket test yet.

## PACKAGE EXCEPTION AUDIT RESULT — 2026-11-23 (READ-ONLY)

Feri ran `script/audit_package_exceptions_and_slot_readonly_ya.py` on `erp-yussyakmal-mrp-test`: `READ_ONLY_PACKAGE_EXCEPTIONS_AND_SLOT_OK`. Exact package category contains **208 SKUs**, **195 active normal unique BoMs**, **13 lacking active BoM**. No package RO confirmed so far.

13 no-BoM package SKUs: `12094,12099,12115,12122,12129,12140,12154,12181,12229,12230,12257,12267,12268`. Nested package lines: Paket `12100` contains Paket `12091`; Paket `12104` contains Paket `12094` (the latter has no active BoM). Do not automatically recurse these until supported, or manufacture nested package in kitchen.
60 OTHER component lines are actually **49 raw-material lines** (Buah 6, Bumbu Kering 10, Daging 1, Filling 2, Keju 1, Percetakan 24, Sayuran 1, Seeds 3, Tepung 1) plus **11 WIP Dapur** lines. Owner previously explicitly scoped kitchen-manufactured finished goods and purchased consignment; **handling of raw materials and WIP in package BoMs is not approved**; do not silently classify as packaging or kitchen finished goods. Mark these package SKUs as requiring explicit sourcing/routing design or master cleanup. Some 'Percetakan' raw items may be physical package materials but their category is Bahan Baku; only master owner can confirm intended handling.
**10 unique finished SKU components** absent from all published Planning: `10021,11628,11635,10023,10022,10034,12337,11653,12403,10030` (33 BoM lines). Historical plans may be incomplete, so **absence is not evidence missing kitchen manufacturing master**. Source routing must be resolved on the exact RO delivery date/slot.

Same-date-slot component routing over 195 BoM-bearing Paket SKUs (not sufficient to claim assembly-ready):
- `2026-11-22 S1`: 4 matching all finished components, 191 missing;
- `2026-11-23 S2`: 4 matching, 191 missing;
- `2026-11-24 S1`: **165 matching**, 30 missing;
- `2026-11-24 S3`: 4 matching, 191 missing;
- `2026-11-25 S3`: 33 matching, 162 missing;
- `2026-11-27 S1`: 17 matching, 178 missing.
These counts ignore raw/WIP/nested and stock state; therefore 165 is **potential route matches**, not 165 valid pilots.

**Next committed source-only script**: `script/audit_package_pilot_candidates_readonly_ya.py` (target 2026-11-24 S1) filters to exact Paket category, unique active normal BoM output one unit, integer base-UoM component quantities, no nested/raw/WIP, unique published same-slot kitchen route per finished component, and separated consignment/packaging stock needs. Intended as **conservative single pilot selector**, not a general rule that all Paket must have 1-output BoM or integer Gram. Output lists candidate Paket SKUs and reason-counts. It neither modifies master nor performs Odoo operations. Run before choosing controlled first Package RO/assembly E2E.

**Critical unmodified code:** RO template/import/confirmation presently requires kitchen Planning and template SKU eligibility; no actual Paket RO today. Need a proper Paket RO entry path or supervised pilot fixture tied to store/date/slot **without faking kitchen Planning**. Existing Pre Produksi frozen allocations and MO release still assume direct store RO = kitchen production; do not deploy package behavior by simply injecting component quantities. Preserve no-Paket flow.

## OWNER FINAL SCOPE CLARIFICATION — ALL NON-MANUFACTURING ITEMS ARRIVE VIA STANDARD ODOO (23 NOV 2026)

Owner explicitly clarified: **ALL Paket BoM components that are NOT manufactured in a kitchen** (purchased finished products, consignment goods, packaging, and other nonmanufacturing physical supplies) are **procured and received into Packing by a separate, existing standard Odoo flow**, and their procurement/receipts are **OUT OF SCOPE** for the custom RO→Manufacturing→Rakit Paket→DO flow. This supersedes any implicit restriction that nonmanufacturing components must have only category `All / Konsinyasi Masuk` or `All / Packaging`.

Inside current flow, Paket assembly consumes any valid BoM component **already in PCK stock**; if actual stock is insufficient, block/mark shortage rather than inventing source stock or POs. Only components routed through **Manufacturing dapur** add kitchen production demand. **Source routing must not rely solely on category prefix**: 24 lines categorized `All / Bahan Baku / Percetakan`, plus other raw and WIP categories, must be checked for their real owner-approved supply path; do not misroute them automatically as kitchen-made or silently discard. Category identifies Paket finished SKU `All / Produk Jadi / Paket`, while component procurement vs manufacturing sourcing is a separate determination.

Current `package_priority_rules.py` pure computation accepts only `FINISHED_KITCHEN`, `CONSIGNMENT`, `PACKAGING`; it must be generalized to distinguish `MANUFACTURED_KITCHEN` from `PCK_STOCK_STANDARD_FLOW` in a later update, after explicitly auditing sourcing metadata. It must not exclude purchased finished goods or other legitimate packing materials just because their category name is unusual. Avoid introducing automatic Purchasing/Accounting/BOP scope.

**Hierarchy remains**: package component demand and assembly prioritized ahead of direct RO ordinary SKU store allocations; final store DO contains completed Paket and remaining ordinary SKU, no component double-shipping.

## OWNER DECISION — PAKET CATEGORY STRICTLY CROSS-KITCHEN ASSEMBLY (2026-11-24)

Owner has chosen a SIMPLIFIED ROUTING RULE based on master product category:
- Finished SKU whose package is assembled entirely within ONE kitchen is **moved out of `All / Produk Jadi / Paket`** to the appropriate kitchen finished-product category. It follows the **existing ordinary manufacturing workflow**: kitchen MO for the packaged final SKU using its BoM, kitchen finished-goods transfer to Packing, then store DO. No Packing assembly MO for these SKUs.
- Category **`All / Produk Jadi / Paket` is reserved for packages involving manufactured components from MORE THAN ONE kitchen**, requiring consolidation/assembly at Packing. Each kitchen makes its components; Packing consumes components and outputs the Package SKU; delivery to stores is from Packing.
- Purchased goods, consignment, and packaging may be BoM components and must be stocked in Packing via a **separate standard Odoo acquisition/receiving flow outside this custom flow**. Do not create custom PO/replenishment.
- The previously audited **208 package SKUs / 122 strict pilot candidates** are a **pre-cleanup snapshot**, not a dependable post-reclassification target. Re-audit targeted category membership and BoM/planning routing **after owner/team changes master categories**. Do NOT automatically recategorize or update production BoMs solely on count of kitchens; business confirms category mapping.
- Category membership now selects Paket flow; this supersedes the prior proposed two-way additional assembly-routing setting, provided master maintenance enforces this strict category policy. Keep no-package ordinary flow untouched.
- Cross-kitchen package need is prioritized before allocation of corresponding ordinary finished goods to stores; do not double-consume or mistakenly manufacture Paket in individual kitchen.
- For a one-kitchen packaged final SKU, ensure its existing kitchen-specific BoM and Published Planning correctly identify the **final SKU itself** (not merely component SKUs) when preparing RO; otherwise its ordinary manufacturing path must be configured. Do not assume a category change alone makes it executable.

This is an owner-approved BUSINESS RULE only. No production master, category, BoM, RO, MO, or code was modified by this note.

## IMPLEMENTATION RESTART — SOURCE KIND INDEPENDENT OF PRODUCT CATEGORY (2026-11-24)

Owner's strict category policy stands: `All / Produk Jadi / Paket` is the cross-kitchen assembled final SKU, while one-kitchen packaged products become normal kitchen finished SKU. Only final Paket SKU category decides package assembly flow; **component category does not determine its procurement/source**.

Source-only pure helper `addons/ya_store_ro/models/package_priority_rules.py` updated to accept explicit source kinds `MANUFACTURED_KITCHEN` and `PCK_STOCK_STANDARD_FLOW`, with earlier `FINISHED_KITCHEN` / `CONSIGNMENT` / `PACKAGING` aliases for compatibility. Any BoM component classified as standard PCK stock may be a purchased finished item, printed pack, consignment, ordinary raw-category material, etc. **No procurement logic** added. Direct RO products must be explicitly kitchen-routed, guarding against treating purchased components or Paket finished SKUs as kitchen MO.

`script/test_package_demand_buckets_pure_ya.py` updated to test explicit routing, cross-source BoM and rejection of direct SKU wrongly supplied via Purchasing. Pending Feri output; do not claim PASS for modified code yet.

Still not integrated: RO import/template eligibility for Paket, immutable Pre Produksi shortage/capacity snapshot, kitchen MO component demand, Paket MO in PCK, and DO final SKU. **No live Odoo models or UI behavior were modified by this step.** Do not fabricate inventory source kind from product category: read actual Routing/BoM and owner-provided supply method. Newly cleaned Paket master needs fresh narrowly scoped test pilot verification (historical 122 number is stale after cleanup).

## NEW ISOLATED ADDON STAGED — RO PAKET PER TOKO (2026-11-24)

Feri verified updated source-only demand calculator via `python3 script/test_package_demand_buckets_pure_ya.py`: `PACKAGE_DEMAND_BUCKETS_PURE_PASS`, no Odoo inventory/RO/MO/allocations touched.

New source-only **not installed, not upgraded, not UAT verified** add-on committed at `addons/ya_package_store_ro/`:
- `ya.package.store.ro`: independent Draft/Confirmed package request per **store, delivery_date, slot** with uniqueness, no fake kitchen Published Planning link; allowed product category `All / Produk Jadi / Paket` only.
- `ya.package.store.ro.line`: product, integer nonnegative qty, product UoM, unique SKU per package RO; confirmed order/lines immutable; confirm blocks any existing `ya.packing.batch` for the date/slot with same advisory lock `lock_ro_slot` as regular kitchen RO.
- Screens RO Paket Toko + ACLs staged for Manufacturing Manager edit, Packing Admin read-only. **No upload XLSX yet**. No MO/stock/GL effect. Existing add-on `ya_store_ro` was NOT modified.
- Current `ya.packing.preview` does **not** consume `ya.package.store.ro` and neither MO generation nor DO can deliver packages. **DO NOT install/present this addon to real users yet** as a standalone confirmed Paket RO would falsely imply processing readiness.
- Need develop atomic shared date-slot Pre Produksi snapshot for both regular confirmed RO and package confirmed RO; package Mo components protected before direct regular store prorata; true PCK native assembly MO (no WO), immutable package final SKU allocations and stock-delivery; no-package regression. Only after complete integration, controlled test DB module installation and UAT.
- Strict owner routing rule: category Paket exclusively cross-kitchen; products packaged in one kitchen use existing ordinary kitchen MO flow. Only manufactured components add kitchen demand; all nonmanufactured physical components sourced into PCK via standard Odoo flow outside project scope.

**Next verification:** on Feri repo after `git pull`, run source syntax checks `python3 -m compileall -q addons/ya_package_store_ro` and pure test. The new addon is not activated by git pull alone, and Odoo registry has NOT been changed. Review logic and integration in sandbox/test before `-u ya_package_store_ro`.

## OWNER SOP CORRECTION — SEPARATE RO MAKER AND PACKING CONSOLIDATOR (2026-11-24)

Owner explicitly says this separation ALREADY exists in this ODOO FROM ZERO workflow: RO creator/submitting section is different from the Packing consolidator. Confirmed RO does not imply Qty correction is forever impossible: only Packing can make an authorized, reasoned and audited correction BEFORE Pre Produksi; after Pre Produksi the frozen allocation snapshot cannot change.

Existing ya_store_ro already has a.packing.qty.correction and ya.store.ro.qty.audit: Packing Admin revises Confirmed RO quantity with compulsory reason before Pre Produksi. Existing operational RO code MUST remain unchanged.

New, uninstalled ya_package_store_ro addon source corrected to mirror SOP, but not deployed or UAT verified:
- Dedicated role ya_package_store_ro.group_ya_package_ro_creator (YA Paket - Pembuat RO) handles Draft and Confirm; Packing group ya_store_ro.group_ya_packing_admin is a DIFFERENT functional role, with RO read access.
- Confirmed Paket RO preserves original header/SKU identity. Qty correction only via Packing dialog ya.package.ro.qty.correction with compulsory reason and append-only ya.package.ro.qty.audit storing before/after, SKU, actor, date.
- Corrections are blocked once ya.packing.batch exists for the same date and slot; date/slot advisory lock is reused. Package RO Qty correction does not yet join existing Packing consolidation.
- Source only: no add-on install, Odoo registry modification, MO, picking, stock or accounting change. Do not enable package RO for users until full end-to-end integration and UAT.

SOP is the primary process rule; rights and immutability controls implement the SOP and protect the audit trail, rather than replace the SOP. Keep ODOO FROM ZERO project scope only.

## OWNER CHECKPOINT — PAKET BOM MUST OUTPUT EXACTLY ONE PACKAGE (2026-11-24)

Owner requires **ONE BoM = finished output Qty 1 Paket** for all current `All / Produk Jadi / Paket` SKU BoMs. Higher BoM outputs risk batch rounding, competing capacity filters and package priority allocation consistency. This rule is specific to **cross-kitchen Paket** category, NOT ordinary kitchen finished-product BoMs, which retain their existing batches.

Prior strict pilot audit found 122 old-category candidates whose BoM output converted to exactly one package, but **that does NOT prove every BoM in current category is output=1**. Category membership may have changed since audit.

Committed new test-DB read-only script `script/audit_package_bom_output_qty_readonly_ya.py` which enumerates every current Paket SKU and all active normal variant/template BoMs and converts `bom.product_qty` from `bom.product_uom_id` to product base UoM with `round=False`, reporting all output >1, <1, =1, missing/multiple BoMs and conversion errors. **Pending Feri execution, no numerical conclusion yet.** Run in `erp-yussyakmal-mrp-test` only. Audit does not modify BoM or anything else.

If any output !=1, flag exact SKU and BoM ID and review BoM component ratios before proposing a change; do not automatically change `product_qty` without simultaneously preserving intended component quantities. Later enforce output exactly one at Paket eligibility/confirmation and assembly, but **do not touch ordinary kitchen BoM rules**.

## OWNER 1-BOM=1-PAKET AUDIT — FERI RESULTS & CODE GUARD (2026-11-24)

Feri successfully ran `script/audit_package_bom_output_qty_readonly_ya.py` on `erp-yussyakmal-mrp-test`:
- Current `All / Produk Jadi / Paket` category id 75 has **207 SKUs** (previous 208 count was before master adjustment).
- **194 SKUs** have exactly one active normal BoM; **all 194 output exactly 1 Paket** (properly converted to base product UoM, Pcs); **zero** BoMs output >1, <1, 0 or have UoM conversion error; no multiple-BoM SKU found.
- **13 current Paket SKUs without an active normal BoM**: 12094, 12099, 12115, 12122, 12129, 12140, 12154, 12181, 12229, 12230, 12257, 12267, 12268. Do NOT generate Paket assembly MO from these until valid BoM is created; do NOT change master automatically.
- Script ended `READ_ONLY_PACKAGE_BOM_OUTPUT_QTY_OK`. This demonstrates master conformity of all *existing* Paket BoMs, not end-to-end assembly readiness.

**Additional staged, not installed** `addons/ya_package_store_ro/models/package_ro.py`: during `action_confirm()`, positive Paket order lines must have **exactly one active normal BoM with output qty exactly one in product base UoM**; reject missing/ambiguous BoM or other output. This is validation of a pre-existing OWNER business rule, not a new accounting/stock behavior. A zero-demand line does not require a BoM at confirmation. Later, again validate at Pre Produksi/assembly because a BoM can change after the RO is Confirmed. Stage is GitHub source only; no Odoo registry/database change and not yet UAT verified.

Next: Feri can run `python3 -m compileall -q addons/ya_package_store_ro` to verify code syntax (no module install). Keep focus on integration of regular RO and Paket RO into one immutable date-slot Pre Produksi and priority Paket-first capacity. Audit of all package masters need not be repeated.

## PACKAGE FIRST MO CAPACITY ENGINE — SOURCE-ONLY NEXT GATE (2026-11-24)

Feri pulled and ran `python3 -m compileall -q addons/ya_package_store_ro` successfully (no errors). This is **syntax PASS only**, not module install, user test or end-to-end integration.

Created a pure helper `plan_kitchen_capacity_with_package_priority(package_need, direct_by_store, bom_output, max_capacity)` in `addons/ya_store_ro/models/package_priority_rules.py`.
- Input: per kitchen/SKU gross components needed by all confirmed package RO + direct ordinary RO per store; kitchen BoM batch output and Published Planning Max.
- Plans kitchen MO at **whole original kitchen BoM batch multiples** up to published capacity.
- **First protects all package component demand** before assigning any output units to direct store allocation; then uses deterministic integer Hamilton prorata for ordinary store shortages; BoM surplus stays unallocated.
- If capacity cannot satisfy **the entire protected package component bucket**, return `blocked_package_capacity` with **qty_production=0** and zero executable allocations. Do NOT prorate/short incomplete Paket silently or run kitchen MOs that leave package assembly impossible. Later business policy may permit controlled partial Paket planning; NOT approved yet.
- No-package case must remain behaviorally identical to `allocate_capacity_prorata` in existing RO flow. Existing stable ordinary RO code UNMODIFIED.
- Created pure test `script/test_package_capacity_priority_pure_ya.py` for package=5, ordinary=10, capacity=12 (protected 5, ordinary 7); blocking capacity shortage; whole kitchen BoM batching; and 3x7x4 no-Paket regression comparisons against existing `allocation_rules.py`. **Feri has not run it yet**.
- This is a **source-only demand/capacity calculator**, not integrated into Odoo Pre Produksi snapshots, Paket assembly MO, or final store DO. Do not imply feature deployed or begin real package RO operations. Next gate: Feri source-only test; then build owner-approved package source classification/slot route adapters, immutable joint Pre Produksi snapshot, and end-to-end module testing exclusively in `erp-yussyakmal-mrp-test`. No extra broad master-data audit unless a specific integration blocker appears.

## OWNER CLARIFICATION — PACKAGE FIRST, THEN FULL KITCHEN BOM ROUND-UP (2026-11-24)

Owner emphasized that shortage of kitchen components for Paket should be **exceptional**, since package needs are prioritized above ordinary store SKU allocation, and kitchen production is rounded **UP to whole BoM batches**. Example: total needed for component Y = 15 (Paket demand 5 + ordinary store RO 10), kitchen production BoM output = 10 units, so release **2 kitchen BoM batches = 20 units** (provided Published Planning Max accommodates 20). Of the 20 produced, protect 5 for package assembly, allocate original 10 direct RO units to store, and keep 5 batch-surplus units separate/unallocated rather than silently increasing store allocations. The **Paket assembly BoM** remains a different BoM with exactly ONE final Paket output per recipe.

This is already the arithmetic behavior of `plan_kitchen_capacity_with_package_priority` when max >=20; do not replace it with a 15-unit kitchen MO or a mistaken one-batch blocking assumption. The separate `max_capacity` gate remains a hard Planning control: if published Max is below 20, a maximum-allowed whole-batch capacity may lead to ordinary store shortage, while preserving Paket priority. Shortage of Paket itself only blocks if even full protected component demand cannot fit. Owner expects that exceptional case to be rare; don't turn exceptions into the dominant design.

New pure test in `script/test_package_capacity_priority_pure_ya.py` explicitly covers 15-demand / 10-output => 20 production, Paket 5 protected, shop 10 allocated, 5 surplus; also tests restricted Planning Max 10. GitHub source-only pending Feri run, not an installed Odoo change.

## CRITICAL OWNER CORRECTION — BOM ROUNDING SURPLUS MUST BE ALLOCATED PRORATA TO STORES (2026-11-24)

Owner explicitly corrected earlier assistant assumption: **All extra finished kitchen units from rounding production UP to complete kitchen BoM batches MUST BE AUTOMATICALLY DISTRIBUTED PRORATA to STORES THAT ORDERED that SKU**, rather than left as unallocated production surplus. This must apply to ordinary RO non-Paket **and** mixed Paket + ordinary RO. Highest priority remains protecting the exact manufactured-component quantities for Paket, then original normal store orders, then distribute residual rounding surplus to those normal stores proportionate to their original RO quantities (stable Hamilton/largest remainder, ties by ascending store ID). No store demand for SKU means no valid direct recipient, so any residual is not silently allocated to unrelated stores. Do not inflate the number of Paket produced solely from rounding a kitchen component BoM.

Example: manufactured component Y needed for Paket 5 + direct store RO total 10, kitchen BoM produces 10 → 2 batches → produced 20, protect Paket 5, original shop demand 10, **surplus 5 distributed to stores**. Store A original 4 gets 6 (+2); Store B original 6 gets 9 (+3); final conservation: 5 Paket-protected + 6 + 9 = 20. If no package, ordinary shop demand 15 with BoM=10 → output20 → spread surplus5 among ordering stores.

**Important source-code discrepancy discovered by reopening actual GitHub files:**
- `addons/ya_store_ro/models/allocation_rules.py` contains original historical `allocate_surplus_prorata()` which implements exactly this (Hamilton). `script/test_ro_packing_prorata_pure_ya.py` directly tests it.
- BUT active `addons/ya_store_ro/wizard/packing_preview.py` calls `allocate_capacity_prorata()`, which intentionally does **not** distribute batch-rounding surplus; it even rejects any nonzero store surplus.
- `addons/ya_store_ro/models/packing_batch.py` existing snapshot/release invariants enforce `allocation.qty_surplus == 0` and `allocation.qty_allocated + shortage == requested`; these MUST be updated together to `allocated = requested - shortage + surplus` and conservation across Paket-protected component demand + all direct store allocations + any genuinely unallocatable surplus. Do not change only the arithmetic or bypass existing staging/release invariants.
- `addons/ya_packing_store_delivery/models/store_delivery.py` creates DO from `allocation_ids.qty_allocated`, so corrected allocation values should flow to DO only after staged snapshot is valid and consistent and actual PCK stock is available.
- Existing code previously was operational-tested but not under this now-reconfirmed surplus distribution rule. Treat as **behavioral gap / pending code change + UAT**, NOT claim it's already operationally working.
- The existing `script/test_capacity_prorata_ya.py` explicitly expects no surplus, while `script/test_ro_packing_prorata_pure_ya.py` expects surplus. Consolidate the competing test expectations when implementing owner-approved target behavior.

**Source-only Paket helper corrected** in `addons/ya_store_ro/models/package_priority_rules.py`: `plan_kitchen_capacity_with_package_priority()` now prorates residual rounded surplus to original direct RO store demand after Paket priority, with a `surplus` field per-store and aggregate `qty_surplus_distributed`. Its `qty_surplus` now specifically means residual NOT assigned to any shop (e.g. no shop ordered SKU). Old no-Paket target tests are replaced by comparison to the historical surplus helper when demand fits, and current capacity-shortage helper when capacity does not fit. Updated `script/test_package_capacity_priority_pure_ya.py` is **PENDING Feri execution**. No Odoo add-on installed/upgraded, no established operational RO logic changed yet. DO NOT label this no-Paket comparison a regression PASS against current active runtime, which intentionally differs.

Scope remains ODOO FROM ZERO, Paket, kitchen MO, Packing, store DO. Purchasing/accounting not in scope. Update joint immutable snapshot and validation before deploying surplus-prorata flow.

## IMPLEMENTED IN GITHUB SOURCE — ORDINARY RO SURPLUS PRORATA FIX (2026-11-24)

Feri verified Paket source-only arithmetic `PACKAGE_CAPACITY_PRIORITY_PURE_PASS` and `NO_PACKAGE_HISTORICAL_SURPLUS_RULE_TEST_PASS`. The current owner business rule supersedes prior 'no surplus distribution' behavior: EVERY rounding surplus created when rounding kitchen MO output up to complete kitchen BoM batches must be distributed by deterministic Hamilton prorata to STORES THAT ORDERED THE SKU, after protecting exact Paket component needs. Original RO Qty is immutable; final store allocation = original RO - shortage + surplus. Physical Packing flow must transfer full completed kitchen MO output and ship final allocation, no speculative stock.

**Actual operational ordinary-RO SOURCE has now been changed in GitHub, but NOT UPGRADED/EXECUTED IN TEST ODOO YET:**
- `addons/ya_store_ro/models/allocation_rules.py`: `allocate_capacity_prorata` now calls existing `allocate_surplus_prorata` when rounded MO fits Published Max, returning positive per-store `surplus`, original demand, zero shortage, and higher final `allocated`. If Max is insufficient, legacy integer capacity shortage prorata remains unchanged; if fewer than one BoM batch fits, remains `blocked`.
- `addons/ya_store_ro/wizard/packing_preview.py`: removed prohibition of allocating surplus, checks `allocated = requested - shortage + surplus`, `MO = allocations + truly unallocated remainder`, shows `total_surplus_distributed`. Original RO remains unchanged, Qty audit/freeze unchanged.
- `addons/ya_store_ro/models/packing_batch.py`: Produksi OK release validates the updated frozen snapshot invariants with positive store surplus rather than rejecting `allocation.qty_surplus != 0`; global MO Qty conservation unchanged.
- `addons/ya_store_ro/views/packing_preview_views.xml` and `views/packing_batch_views.xml`: new column `Tambahan Surplus BoM`, `Jatah Final Toko`, grand total surplus, and corrected confirmation message. Historical Qty, capacity shortage acknowledgement, and all normal RO workflow permissions unchanged.
- `addons/ya_store_ro/__manifest__.py` bumped to **19.0.8.1.3** for intentional behavior change.
- `script/test_capacity_prorata_ya.py` now tests owner-approved surplus distribution, shortage, Hamilton ordering, conservation and invalid cases. `script/check_capacity_prorata_source_readonly_ya.py` updated old static guards to expect surplus, and old manifest checks updated in `check_packing_preproduction_source_readonly_ya.py` and `check_packing_generate_mo_source_readonly_ya.py`.
- Existing `script/test_ro_packing_prorata_pure_ya.py` continues to test original surplus allocation arithmetic; `script/test_package_capacity_priority_pure_ya.py` should remain compatible.

**PENDING FERI TESTS** (source-only, no Odoo DB writes):
`python3 script/test_capacity_prorata_ya.py`
`python3 script/test_ro_packing_prorata_pure_ya.py`
`python3 script/test_package_capacity_priority_pure_ya.py`
`python3 script/check_capacity_prorata_source_readonly_ya.py`
`python3 script/check_packing_preproduction_source_readonly_ya.py`
`python3 script/check_packing_generate_mo_source_readonly_ya.py`
`python3 -m compileall -q addons/ya_store_ro`

Do not claim active Odoo PASS after source tests; safe -u and UAT in `erp-yussyakmal-mrp-test` (NEVER production database) are required to verify Preview→Pre Produksi→Produksi OK→finished-goods transfer→DO store. New `ya_package_store_ro` addon remains uninstalled, Paket cross-kitchen integration still pending. Do not change accounting/procurement.

## OWNER CORE INVARIANT — ZERO UNALLOCATED FINISHED OUTPUT AT PACKING (2026-11-24)

Owner clarified why previously stated surplus=0: Packing is an immediate DISTRIBUTION POINT, NOT a storage location for finished production output. The true invariant is **ZERO UNALLOCATED finished units when arriving in Packing**. Never confuse this with the per-store BoM-rounding surplus column, which can and MUST be positive when original store RO demand exists. Example: kitchen component BoM output 10, Paket needs5, RO shops A4/B6: 2 batches produce20; reserve5 for Paket assembly; allocated A6 (4+2) and B9 (6+3); leftover at PCK=0. This explicitly supersedes earlier wrong wording that BoM surplus should stay unallocated.

**Priority CURRENT:** Paket manufactured components first, then ordinary store RO, and any BoM rounded extra distributes prorata to *stores that ordered that SKU*. **Priority FUTURE ONLY when Sales Order to Manufacturing exists:** 1. Sales Order, 2. Paket, 3. RO Toko. DO NOT implement SO now; retain extension design with protected higher-priority demand buckets.

Do not increase confirmed Paket Qty solely to absorb extra component production and do not send SKU to stores without an actual RO for the SKU. If rounded kitchen BoM creates surplus with NO direct store recipient, block release/flag it explicitly until a legitimate distribution path or production plan exists. Do not silently store output in Packing. A materials/packaging PCK stock replenished by standard Odoo flows is conceptually different from finished output waiting unallocated.

**Source changes staged in GitHub only, NOT applied to Odoo runtime:**
- Ordinary Packing Preview ya.store.ro wizard action_move_to_preproduction now refuses total_unallocated !=0 and any preview line qty_surplus !=0 (line-level field means *unallocated*, not store-extra), while preserving positive allocation.qty_surplus per store.
- Existing ya.packing.batch.line action_generate_selected_mo now refuses any frozen batch line qty_surplus !=0; it still allows store allocation.qty_surplus >0. This hard stop is appropriate for old ordinary RO batches too; no creation of unfinished/undistributed production.
- Source-only Paket capacity helper returns blocked_no_distribution_destination, with qty_production=0, and reports would_produce/unallocatable_qty if component BoM batch rounding leaves units without any RO store. Does NOT auto-generate unauthorized extra packages or random store shipments.
- Added Paket pure test: no-store surplus block, exact Paket quantity no-store valid, and store original 1 gets all 4 extras. Existing test check_capacity_prorata_source_readonly_ya.py now expects the two no-unallocated guards.

**Not yet covered operationally:** actual MO Done output vs immutable planned Qty and PCK inventory transfer, assembly of Paket in Packing, and final DO/receipt; these must be verified and guarded before end-to-end deployment. No claim that Packing runtime currently guarantees zero physical leftovers. Existing RO flow repository source previously modified for store prorata (ya_store_ro 19.0.8.1.3), but not upgraded/tested by Feri yet.

Next Feri source-only tests: python3 script/test_capacity_prorata_ya.py ; python3 script/test_package_capacity_priority_pure_ya.py ; python3 script/check_capacity_prorata_source_readonly_ya.py ; python3 -m compileall -q addons/ya_store_ro. NEVER upgrade production database.
