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

## OWNER OVERRIDE — INTERNAL TRANSFER IS THE FALLBACK FOR UNALLOCATABLE MO OUTPUT (2026-11-24)

The owner corrected the preceding hard-stop rule. **A kitchen MO may produce finished goods that cannot be automatically allocated by system prorata to the stores' original RO. Packing sends those remaining finished goods to a store via STANDARD ODOO INTERNAL TRANSFER.** Do NOT block RO Pre Produksi, Produksi OK or a package component MO solely because of leftover BoM rounding output. Packing still is not meant for overnight storage: transfer must take place in the operational flow. No fake RO/store destination and no invented automatic distribution.

Allocation semantics:
- Highest priority NOW: Paket assembled cross-kitchen; next ordinary RO toko. Later planned, **not implemented**: Sales Order > Paket > RO toko.
- Package-manufactured component demand is protected; ordinary RO stores then receive requested Qty and ALL automatically allocatable BoM-rounding extras by proportional Hamilton prorata. This is represented by positive per-store `allocation.qty_surplus` and goes on the normal RO-backed DO.
- If any kitchen MO finished output is NOT automatically allocatable (for example Paket components need 5 and a kitchen BoM outputs 10 but no store ordered that component SKU), keep that residual on immutable batch-line `line.qty_surplus` / `total_unallocated`. The remaining physical goods are received at Packing with the full kitchen MO output and later dispatched separately to a legitimate store using **standard Odoo internal transfer**, not automatically through RO-backed DO. Actual destination is chosen operationally, not fabricated from absent RO. Record transfer and prevent stranded overnight Packing stock by SOP.
- **Two prior guards are withdrawn:** in `addons/ya_store_ro/wizard/packing_preview.py` do NOT reject `total_unallocated > 0`; in `addons/ya_store_ro/models/packing_batch.py` do NOT reject positive `batch.line_ids.qty_surplus`. Existing conservation checks `sum(RO allocated) + sum(batch unallocated) = sum(MO production)` remain intact.
- **Package pure calculator** `plan_kitchen_capacity_with_package_priority` no longer blocks status `blocked_no_distribution_destination`; it preserves `qty_production`, `package_component_qty_protected`, `qty_surplus` and reports `qty_pending_internal_transfer` (positive residual) so it can be routed through standard internal transfer. `script/test_package_capacity_priority_pure_ya.py` now checks 10-output/5-Paket/no-ordinary-RO => 5 pending internal transfer and no block; expected extra test marker `PACKING_INTERNAL_TRANSFER_FALLBACK_TEST_PASS`.
- Static preflight `script/check_capacity_prorata_source_readonly_ya.py` updated to forbid the erroneous hard-stops, while retaining source conservation checks. UI labels in Packing preview and persisted batch now call the *batch-line* residual `Sisa untuk Internal Transfer`; store-line `qty_surplus` remains `Tambahan Surplus BoM`.

**This newer owner instruction supersedes the earlier 'zero unallocated before Pre Produksi' block instruction.** No actual live Odoo module upgrade performed by source GitHub commits yet. There is NOT YET a new automated internal-transfer creation workflow for this exception: use the standard Odoo Internal Transfer process. Do not claim integration is complete without the test DB UAT. We must eventually verify kitchen actual MO Done Qty, Packing physical moves, DO allocated shipments and remaining standard internal transfer close out; no accounting/purchasing work in this scope.

Suggested Feri source-only tests:
`python3 script/test_capacity_prorata_ya.py`
`python3 script/test_package_capacity_priority_pure_ya.py`
`python3 script/check_capacity_prorata_source_readonly_ya.py`
`python3 -m compileall -q addons/ya_store_ro`

## FERI PURE REGRESSIONS PASS — MOVE TO TEST DB REGISTRY/UAT (2026-11-24)

Feri ran Git pull and supplied actual results from repository source:
- `script/test_capacity_prorata_ya.py` -> `CAPACITY_SURPLUS_PRORATA_REGRESSION_PASS`; cases cover BoM rounding surplus prorata, planning capacity shortage, zero demand, malformed Qty.
- `script/test_package_capacity_priority_pure_ya.py` -> `PACKAGE_CAPACITY_PRIORITY_PURE_PASS`, `NO_PACKAGE_HISTORICAL_SURPLUS_RULE_TEST_PASS`, `PACKING_INTERNAL_TRANSFER_FALLBACK_TEST_PASS`; Paket component protection + MO batch round-up + separate standard internal transfer residual.
- `script/check_capacity_prorata_source_readonly_ya.py` -> `ERROR_COUNT: 0`, `CAPACITY_SURPLUS_PRORATA_SOURCE_OK`.
- `python3 -m compileall -q addons/ya_store_ro` returned no syntax errors.
- No Odoo transaction was run, no MO/RO/stock was modified and **no installed Odoo module upgrade/UAT PASS** yet.
- Removed stale success-message text in `script/test_package_capacity_priority_pure_ya.py` that still claimed the ordinary RO source lacked surplus distribution. Source does prorate now; **loaded Odoo registry and UI are NOT yet verified**.

New READ-ONLY Odoo test DB inspection staged: `script/check_ro_surplus_odoo_registry_readonly_ya.py`; checks module version 19.0.8.1.3, registered preview field, views actually stored in DB, and runtime 15/10=>20 surplus prorata (stores 6/9 => 8/12). This does not test full Packing→MO→FG→DO.

**Deploy carefully per `doc/SKILL_ODOO19_ADDON_WORKFLOW.md`:** Feri must first take verified GUI backup of `erp-yussyakmal-mrp-test`. Then copy ONLY `addons/ya_store_ro/.` to `/opt/odoo19/custom-addons/ya_store_ro/`, change ownership to odoo19, run `-u ya_store_ro` ONLY with `-d erp-yussyakmal-mrp-test` and `--stop-after-init --no-http`. On zero exit, restart service during an appropriate window (service restart may affect other DBs) and run new Odoo registry read-only check. No deploy/install `ya_package_store_ro` yet. After that run controlled UI or rollback test of Confirmed RO→Packing Preview→Pre Produksi→MO release→FG transfer→DO allocations, then resume Paket integration. **Primary `erp-yussyakmal` must not be upgraded/touched for this test.**

## OWNER GOVERNANCE OF ERP CUSTOMIZATION — 20-YEAR BUSINESS PROCESS IS PRIMARY (2026-11-24)

Owner strongly emphasized that the operating business process has worked for approximately **20 years without Odoo**. Critical design principle: **Odoo must serve the established SOP and people, not replace every operational decision with a custom blocking rule.** Previous assistant's broad assumption that any unassigned kitchen production must block MO or Pre Produksi was too rigid and has been explicitly rejected.

Pragmatic implementation boundary:
- **Automate high-volume, repeatable work:** RO import, consolidation of many SKUs and warehouses, kitchen BoM batch round-up, priority buckets (NOW Paket > RO toko; FUTURE only when SO manufacturing is introduced: SO > Paket > RO toko), stable prorata, MO/DO, transfer quantities, traceability.
- **Hard-block only genuine structural/integrity hazards:** invalid data/BoM, duplicate releases, forbidden negative inventory, wrong company/route, inconsistent financial/stock transactions or other clearly established critical SOP violations. Do not invent new blockers merely because an edge case cannot be automatically solved.
- **Leave valid exceptions to people and standard Odoo transactions:** any finished kitchen MO output not automatically allocated through RO and package needs can be sent from Packing to a chosen store using normal internal transfer under established SOP. Preserve a visible quantity trail; do not auto-create fictitious RO or arbitrary destinations.
- **Do not over-customize:** no need to build system-driven resolution of every tiny exception. Prefer native Inventory, clear handoff points and operational judgement. Preserve existing working flow and speed for operators who handle hundreds of SKUs across many warehouses.
- Packing is a short-term consolidation/distribution point, not intended overnight finished-goods storage, but this is managed by SOP and internal transfers rather than an unconditional MO hard stop.

## FERI EVIDENCE — YA STORE RO TEST DB UPGRADE AND RUNTIME SMOKE PASS (2026-11-24)

Feri performed Git pull, staged `addons/ya_store_ro` into Odoo custom-addons, and upgraded `ya_store_ro` ONLY in `erp-yussyakmal-mrp-test`. Output `UPGRADE_EXIT_CODE=0`. Odoo emitted docutils formatting warnings/errors (`Unexpected indentation`, inline literal warnings) during upgrade, but completed successfully. Do NOT mistake formatting diagnostics for upgrade failure. If they recur or affect UI text, investigate nonblocking.

Feri then ran `script/check_ro_surplus_odoo_registry_readonly_ya.py` using Odoo shell on `erp-yussyakmal-mrp-test`; confirmed: `MODULE_STATE: installed`, `MODULE_INSTALLED_VERSION: 19.0.8.1.3`, `ODOO_RUNTIME_ALLOCATOR_SURPLUS_PASS`, `ODOO_REGISTERED_SURPLUS_FIELD_PASS`, `ODOO_DB_VIEW_SURPLUS_PASS`, `READ_ONLY_RO_SURPLUS_REGISTRY_PASS`.

Correct status: source tests + Odoo registry/views/runtime smoke **PASS** in test DB; no post-upgrade RO Preview→Pre Produksi→MO→FG to Packing→DO Store E2E acceptance yet. Do not ask for needless repetitive audit, reset of prior stable flow, or production upgrade. Do not install `ya_package_store_ro` until Paket integration is complete. Next development priority is joint Paket+ordinary RO demand snapshot with Paket first and BO M rounded surplus/transfer fallback, using existing stable workflow and only minimal essential extension.

## NEW STAGE — JOINT PACKING READ-ONLY PREVIEW: ORDINARY RO + PAKET (2026-11-24)

Owner requested to proceed after `ya_store_ro` test DB upgrade 19.0.8.1.3 and read-only runtime registry PASS. Business priority unchanged: 20-year SOP governs, **Paket first > RO Toko** (later only: SO > Paket > RO), kitchen BoM round UP to whole batches, shop prorata receives BoM extras, remaining finished units go by separate ordinary internal transfer to stores, no artificial blockers. **Never break the already tested ordinary flow.**

New source-only staged work inside **uninstalled `addons/ya_package_store_ro`** (version 19.0.1.1.0; no installed Odoo changes):
- Pure reusable `models/joint_slot_rules.py`: calculate ONE date-slot from *both* confirmed ordinary RO rows and confirmed Paket RO rows. Explode 1-output Paket assembly BoM, preserve per-RO source and BoM provenance, route manufactured finished components to existing Published Planning per SKU/date/slot, protect Paket component Qty first, then direct store RO, use `plan_kitchen_capacity_with_package_priority`, preserve positive per-store rounding extra, distinguish residual for native PCK→store internal transfer, and trace purchased/consignment/packaging stock needed at PCK. Do NOT generate kitchen or Paket MO, transfer, DO, stock reservation.
- Pure test `script/test_package_joint_slot_pure_ya.py`: 5 Paket X needs Y+Z, each direct store wants Y/Z 4 and 6, kitchen BoM output 10 ⇒ manufacture Y20+Z20, protect Y5+Z5 for assembly, ordinary stores get 6 and 9 each SKU after BoM surplus prorata; test no-Paket equivalence, only-Paket transfer fallback, two packages share component and single MO per kitchen/SKU, capacity-limited direct RO, one-kitchen master warning, invalid input refusal.
- `models/joint_slot_preview.py`: Odoo transient Packing-only **READ-ONLY ORM adapter** uses ACTUAL Confirmed `ya.store.ro`, `ya.package.store.ro`, real Paket `mrp.bom`, actual Published Planning routes for the requested date+slot, UoM conversions and kitchen BoM / Planning Max. Draws a joint per kitchen+SKU proposal with Paket needs, RO store allocations, surplus, planned MO output, fallback internal transfer Qty, 1-unit Paket assembly quantities by store and manual/PCK stock needs. **Never creates `ya.packing.batch`, MOs, WOs, pickings, or reservations**; this is a planning preview, not production release. Manual PCK sourcing is explicitly flagged for finished goods without exactly one Published Planning route instead of inventing a kitchen.
- `views/joint_slot_preview_views.xml` registered under the Paket menu, Packing Admin only. Added Packing ACL, registered model and new view in Paket manifest. Dedicated Paket RO creator/Packing separation hardened for Draft line edits and audit metadata. Existing ordinary RO model, existing confirmed→Pre Produksi flow, MO creation, FG transfer and DO addon are **UNCHANGED during this new stage**.
- `script/check_package_joint_preview_source_readonly_ya.py` static parse/manifest/ACL/routing preflight.
- Source-only tests **PENDING FERI RUN**; do NOT install or upgrade `ya_package_store_ro` yet, because the real JOINT immutable Pre Produksi snapshot + Paket assembly MO + DO Paket are NOT integrated. No new active Odoo module changes after last `ya_store_ro` test DB smoke.

Feri source-only commands from repo root:
`python3 script/test_package_joint_slot_pure_ya.py`
`python3 script/check_package_joint_preview_source_readonly_ya.py`
`python3 -m compileall -q addons/ya_package_store_ro`
`python3 script/test_package_capacity_priority_pure_ya.py`

**Next source milestone AFTER these checks pass:** persist one immutable joint Pre Produksi date-slot snapshot with both kinds of RO and protected component allocations. Then create kitchen MOs without WO; after standard finished transfer into PCK assemble Paket via native MO BoM output exactly 1 per package, then existing ordinary DO + Paket DO to stores. Never misclassify package BO M output as kitchen batch quantity. Respect SO future priority as documented, not implemented now.

## NEXT MILESTONE STAGED SOURCE — ONE JOINT PRE PRODUKSI + NATIVE KITCHEN MO RELEASE (2026-11-24)

**Evidence from Feri (before these new changes):** `script/test_package_joint_slot_pure_ya.py` ended `SOURCE_ONLY_NO_DB_CHANGES`, `script/check_package_joint_preview_source_readonly_ya.py` reported `ERROR_COUNT: 0` and `PACKAGE_JOINT_PREVIEW_SOURCE_OK`. These demonstrate source-only joint math/structure, NOT Odoo installation or operational Pre Produksi.

**New and NOT YET tested or installed** in `addons/ya_package_store_ro` version **19.0.1.2.0**:
- `models/joint_slot_snapshot.py` extends EXISTING `ya.packing.batch` and `ya.packing.batch.line`, NOT a parallel fake batch. Adds `ya_has_package`, `ya_package_ro_ids`, package demand and component records, and kitchen `ya_package_component_qty` plus frozen kitchen BoM output `ya_kitchen_bom_output`. New immutable child models `ya.packing.package.demand` and `ya.packing.package.component` preserve store/RO/BoM SKU Qty, PCK vs kitchen sourcing, UoM-converted BOM component quantities and kitchen MO line links. Write/unlink prohibited; creation only through Packing snapshot workflow. Pre Produksi continues unique date+slot.
- `models/joint_slot_preview.py`: existing preview calculation factored into `_build_joint_plan`; live digest prevents accepting Qty/Planning/BoM changes after Preview. New **Pindahkan ke Pre Produksi (RO + Paket)** stages exactly ONE immutable batch with original ordinary RO ids, Paket RO ids, normal store allocation rows, package demands, protected kitchen component quantities and explicit leftover for standard PCK→store internal transfer. Uses existing Packing advisory date-slot lock and ordinary RO packing_batch_id link. **No MO, transfer, DO or stock writes at staging.** If a shortage of ordinary RO allocation occurs, Packing confirms the displayed shortage; this is existing SOP. Paket BOM output remains exactly one package.
- `models/packing_preview_route.py`: if a Confirmed Paket RO shares an ordinary RO date/slot, ordinary Packing button redirects to joint Preview (same user flow); **no Paket → super() keeps tested ordinary RO flow unchanged**.
- `models/joint_release.py`: inheritance of existing `ya.packing.batch.line.action_generate_selected_mo`, only takes special path for `batch.ya_has_package`. Revalidates frozen source RO and assembly BoM content/qty, kitchen component protection, stores' allocation with surplus and shortage, and complete MOQ conservation, then generates native kitchen MOs (same one per kitchen+SKU, no new WO). Ordinary-only batch falls through to `super()` preserving existing tested behavior. BoM output and max rechecked against published snapshot; atomic Odoo transaction. This is **staged source, untested in Odoo runtime**.
- `views/joint_snapshot_views.xml` is inherited extension of existing original Packing Pre Produksi and batch form (read-only Paket qty/components), and joint preview view adds Stage button. Packing read/create ACL for immutable Paket snapshot models. Existing ordinary RO/Packing source files were **not changed by this stage**.
- New Feri static gate `script/check_package_joint_snapshot_source_readonly_ya.py` checks Python AST, XML, exact manifest version, model imports, added ACLs, ordinary-vs-joint entrypoint, source snapshot structure, release-time BoM checks. Existing preview static gate updated for version 19.0.1.2.0.
- **UNRESOLVED before installing this addon:** native Packing Paket assembly MO consuming kitchen FG & PCK stock, package DO/receipt, accurate physical transfer outcome reconciliation and a test DB end-to-end rollback/UAT. Do not ask Feri to install addon, run `-i`/`-u`, or run joint UI actions before these steps. Ordinary RO test DB version 19.0.8.1.3 stays installed and PASS. No primary database touched.
- **Operational edge cases for later QA:** duplicate SKU appearing in more than one published kitchen planning in a slot cannot yet be automatically assigned a unique package source; ordinary-only logic unaffected. Also ensure package-only rows with all components sourced manually from PCK are handled through existing SOP without a spurious kitchen MO. These are integration review items, not grounds to invent fake routes or block other normal work.

Next Feri source checks (no Odoo DB changes):
`python3 script/test_package_joint_slot_pure_ya.py`
`python3 script/check_package_joint_preview_source_readonly_ya.py`
`python3 script/check_package_joint_snapshot_source_readonly_ya.py`
`python3 -m compileall -q addons/ya_package_store_ro`

**Business invariants unchanged:** 20 years SOP primary; current Paket > ordinary RO; future SO > Paket > RO; 1 Paket assembly BoM outputs exactly 1 Paket, kitchen BoMs may output batches (ceil round-up); positive BoM extra after protecting Paket distributed prorata to ordering stores; anything no RO recipient remains tracked for native PCK→store internal transfer, not a hard-stop; no negative stock, duplicate MO or overnight PCK.

## PACKAGE PCK NATIVE ASSEMBLY + SAME STORE DO — NEW SOURCE STAGE (2026-11-24)

Feri confirmed source-only PASS on prior stage:
- `JOINT_SLOT_PURE_ALL_PASS`
- `PACKAGE_JOINT_PREVIEW_SOURCE_OK`
- `PACKAGE_JOINT_PREPRODUCTION_SOURCE_OK`
- `PACKAGE_JOINT_MO_RELEASE_SOURCE_OK`
- `SOURCE_ONLY_NO_DB_CHANGES`
Old source remains UNINSTALLED in Odoo test; no Paket real transaction UAT has occurred.

**Next GitHub SOURCE now staged, still NOT installed/UAT:** `ya_package_store_ro` **19.0.1.3.0**, with dependencies on existing `ya_store_ro`, `ya_finished_packing_transfer`, and `ya_packing_store_delivery`.
- `models/package_assembly.py` extends native `mrp.production` with unique `(ya_package_assembly_batch_id, product_id)`, and existing `ya.packing.batch` with `action_ya_create_package_assembly_mos`. Creates ONE normal Odoo MO per Paket final SKU across all stores for same date/slot; only for joint Produksi OK batch; after ALL kitchen component MOs Done and FG transfer to PCK Done. Uses ONE **existing PCK Manufacturing operation type** (does not create fake warehouse/routes) and explicitly requires both source/destination stock locations be `PCK/Stock`. Reads confirmed, frozen Paket BO M with output **exactly 1 Paket**, verifies frozen source/BoM via `_ya_check_joint_sources`. Does NOT auto-mark MO Done, auto-write stock, create WOs or auto-buy consignment. Detects unexpected WO generation so SOP stays no-WO. Uses natural Odoo component consumption and finished production movement at completion. Reclick is idempotent / opens existing MOs.
- `models/package_delivery.py` extends existing **`action_ya_generate_store_do`**, only when `batch.ya_has_package` is True. Ordinary-only dispatch uses `super()` unchanged. For joint batch, requires real Paket assembly MOs Done and verifies actual posted **move_finished_ids** quantities match frozen Paket RO. Calls original normal-store DO creation where original allocations exist; then appends Paket stock moves to the SAME store dispatch picking, creating native per-store picking only if a Paket-only store had none. Uses same PCK source, interwarehouse transit, and existing store reception engine. Does NOT validate dispatch or create fake ready stock; sets Done Qty only when untracked goods are physically available and unreserved, otherwise native operator can resolve as existing shortage SOP. Double-click opens existing DO without re-issuing.
- `models/package_finish_rules.py` consolidates frozen store demand in one source for assembly per SKU and store DO split. `script/test_package_assembly_dispatch_pure_ya.py` checks shared SKU across stores, totals, determinism and bad Qty.
- `views/joint_snapshot_views.xml` exposes Packing's **Siapkan MO Rakit Paket**, **Lihat MO Rakit Paket**, and MO list directly in the EXISTING `ya.packing.batch` UI; no extra production app for operators.
- `script/check_package_assembly_do_source_readonly_ya.py` checks AST/XML/dependencies/native-route semantics, no WO and no auto-validation. `script/audit_pck_package_manufacturing_route_readonly_ya.py` reports REAL PCK warehouse manufacture operation types, src/dest routes, package BoM operation counts/read-only without mutation.

**Source-only and read-only tests now PENDING FERI; do not claim installed, do not upgrade DB or put Paket into production**:
`python3 script/test_package_joint_slot_pure_ya.py`
`python3 script/test_package_assembly_dispatch_pure_ya.py`
`python3 script/check_package_joint_preview_source_readonly_ya.py`
`python3 script/check_package_joint_snapshot_source_readonly_ya.py`
`python3 script/check_package_assembly_do_source_readonly_ya.py`
`python3 -m compileall -q addons/ya_package_store_ro`
Then ONLY Odoo shell read-only (test database): `script/audit_pck_package_manufacturing_route_readonly_ya.py`. Do not install while PCK manufacturing route remains unverified.
Need follow-up: address any actual route/BoM operations finding; then write rollback E2E tests on `erp-yussyakmal-mrp-test` for joint Pre Produksi, kitchen MO, kitchen FG transfer, Paket MO consumption/produced Qty, combined DO/receipt and no-negative checks. GUI backups prior to any install/upgrade. No live database changes.

**Owner governing design:** operating SOP worked 20 years. Native Inventory/Manufacturing operations plus people's judgement are appropriate; do not invent blocking automation for every edge case. Existing ordinary RO→stock toko flow MUST not regress. Current priority Paket > ordinary RO; future SO > Paket > RO (not active). No fake SO/Planning, no duplicate component counts, no RO Qty overwrite. BoM kitchen batching ceil; Paket final BoM output exactly one.

## FERI ACTUAL RESULTS — PCK MANUFACTURING ROUTE AUDIT PASS (2026-11-24)

Feri ran four actual source/readonly checks after Git pull:
- `script/test_package_assembly_dispatch_pure_ya.py`: `PACKAGE_ONE_MO_PER_SKU_PASS`, `PACKAGE_DO_PER_STORE_QTY_PASS`, `PACKAGE_ASSEMBLY_DISPATCH_PURE_ALL_PASS`; no Odoo DB writes.
- `script/check_package_assembly_do_source_readonly_ya.py`: `ERROR_COUNT: 0`, `PACKAGE_ASSEMBLY_PCK_SOURCE_OK`, `PACKAGE_DO_MERGE_SOURCE_OK`; source only.
- `script/check_package_joint_snapshot_source_readonly_ya.py`: `ERROR_COUNT: 0`, `PACKAGE_JOINT_PREPRODUCTION_SOURCE_OK`, `PACKAGE_JOINT_MO_RELEASE_SOURCE_OK`; source only.
- `script/audit_pck_package_manufacturing_route_readonly_ya.py`: `READ_ONLY_PCK_PACKAGE_ROUTE_OK` on **`erp-yussyakmal-mrp-test`**. Feri's actual output confirms **ONE PCK warehouse**, warehouse id **3** company **1**, main stock location **20 (`PCK/Stock`)**, native Manufacturing Operation Type **279** (`mrp_operation`), with BOTH default raw-material source and finished-good destination exactly `PCK/Stock`. Do NOT create or modify any PCK manufacturing routes/locations: existing Odoo master is already correct. Precisely **207 Paket category SKUs**, **194** with valid single active normal BoM; **13** missing/multiple BoMs still require master housekeeping before those specific Paket may be confirmed. **All 194 valid Paket BoMs use operation type 279**, and **ZERO** have operations/WO; therefore standard MO without WO matches current SOP.

**New targeted post-audit source adjustments, not yet tested/installed:**
- `models/package_delivery.py`: removed overly rigid demand=actual-MO-finished Qty condition. Even when a Paket MO Done produces fewer than RO ordered, its normal DO remains created with confirmed demand, while operator enters actual dispatch Qty (or 0 with mandatory reason), same as proven ordinary RO SOP. No fictitious stock or premature MO completion. Excess finished Paket stock does not automatically inflate store DO and may go through standard internal transfer. DO remains unavailable until Paket MOs are Done; this protects against shipping nonexistent product, not operational discretion over short dispatch.
- `models/joint_slot_preview.py`: convert ordinary source RO integer Qty from confirmed Planning UoM to actual finished product base UoM BEFORE joining component quantities; prevent treating one pack/box as one piece. Recheck original RO & Published Planning UoM match as established in old flow. `models/joint_release.py`: compare frozen base-UoM Qty to original converted RO Qty at Produksi OK. This preserves genuine multi-UOM products without inventing new factory routing.
- Static check `script/check_package_assembly_do_source_readonly_ya.py` now verifies no false exact-finished-Qty blocking and both UoM conversions.
- New standalone **READ-ONLY candidate locator** `script/audit_joint_package_uat_candidates_readonly_ya.py`: for existing Published Planning date/slot, report candidate Paket SKUs with valid BoM and finished components routed through **2+ unique kitchens**, plus SKU/kitchen/Max details. It does NOT create a test Planning, RO, new BoM, MO, or stock; if no candidates, report that rather than fabricate sample routes.

**Next Feri commands, NO INSTALL YET:** from repo root run `python3 script/test_package_assembly_dispatch_pure_ya.py`, `python3 script/check_package_assembly_do_source_readonly_ya.py`, `python3 -m compileall -q addons/ya_package_store_ro`. Then Odoo shell read-only on test DB: `script/audit_joint_package_uat_candidates_readonly_ya.py` (stdin). Inspect real candidates before defining rollback UAT. No source or Odoo DB manipulation needed for audit. After viable candidates and code review, take GUI backup of test DB and only then consider controlled `-i ya_package_store_ro` in test DB, never production; verify Odoo registry, installed views/ACL, then rollback E2E. Existing ordinary RO→store flow remains untouched and owner-tested.

**Risk note:** uninstalled Paket source is NOT yet proof native end-to-end finished stock production, component consumption, DO actual qty or store receipt. Source tests only plus PCK master audit PASS. No BO M change or new warehouse permitted without explicit operational need.

## FERI ACTUAL CANDIDATE AUDIT PASS / READINESS FILTER NEXT (2026-11-24)

Feri ran `script/audit_joint_package_uat_candidates_readonly_ya.py` on `erp-yussyakmal-mrp-test`, output `READ_ONLY_MULTI_KITCHEN_PAKET_CANDIDATES_OK`: Published Planning date+slot count **6** (2026-11-27 S1, 2026-11-25 S3, 2026-11-24 S3/S1, 2026-11-23 S2, 2026-11-22 S1); **192** valid Paket BoMs with at least one manufactured finished component; **90** candidate Paket/date/slot combinations with 2+ unique kitchens; **939** combinations missing a published eligible kitchen route; **0** ambiguous routes. These 90 are NOT all test-ready because date-slot uniqueness may already be occupied by a Pre Produksi batch, and Published Planning Max/BoM output might not fit the Paket component Qty. Do not confuse 939 missing *combinations* with 939 invalid SKU masters.

Evidence sample Paket `12191 Paket Gorengan Mix`, assembly BoM `1418`, kitchens ASN + GRG, published both 2026-11-27 S1 and 2026-11-25 S3. Another 2026-11-24 S1 examples are Hampers PST+ROTI. Do NOT automatically select these as ready to stage; first confirm whether `ya.packing.batch` exists on that date+slot, then actual kitchen BoM outputs/Max and RO sources. **One immutable date+slot batch; never create a duplicate or overwrite an existing one.**

**New read-only audit staged in GitHub**, `script/audit_package_uat_slot_readiness_readonly_ya.py`:
- Enumerates each of 6 actual Published Planning slots; prints existing batch IDs and existing Confirmed ordinary RO counts.
- For each multi-kitchen Paket candidate, resolves REAL kitchen `_capacity_bom()`, converts BOM output and Published Max into product base UoM, computes production batch rounding for one Paket with existing ordinary RO, distinguishes Paket priority capacity feasibility, displays actual component product codes/kitchen/BoM output/Max/original RO Qty.
- Prints advisory PCK stock for consignment/packaging components (not a reservation), separates free from occupied slots, and recommends test-only SOP setup if no available slot exists. Does not touch or create any RO/Planning/BOM/MO/batch/stock master records. Feri test run PENDING.
- Corrected package-only DO creation in `addons/ya_package_store_ro/models/package_delivery.py`: if the store had no ordinary DO, call native `picking.action_confirm()` for newly created package-only picking. If appending to an existing confirmed ordinary DO, confirm only new Paket stock moves. It DOES NOT validate stock transfer, ship, or create store receipt at this stage. Static checker `script/check_package_assembly_do_source_readonly_ya.py` updated accordingly. Source tests for this new fix PENDING; no installed Paket Odoo change yet.

**Next Feri actions, no add-on installation yet**:
1. From `~/odoofromzero`: `git pull`, `python3 script/check_package_assembly_do_source_readonly_ya.py`, `python3 -m compileall -q addons/ya_package_store_ro`.
2. READ-ONLY Odoo shell, TEST DB ONLY: `script/audit_package_uat_slot_readiness_readonly_ya.py` and report `SLOT`, `FREE_SLOT_CANDIDATES`, `FREE_CANDIDATE`, `UAT_SLOT_ACTION`, `READ_ONLY_PACKAGE_UAT_SLOT_READINESS_OK`.
3. Only if unoccupied realistic slot and code complete, plan backup and guarded test DB installation + rollback E2E; if no unoccupied slot, use normal authorized creation of fresh test Published Planning and RO docs for a later test date/slot rather than altering existing historical batches or overriding company production data. Never upgrade `erp-yussyakmal`.

Reminder: owner's 20-year SOP is primary, use native internal transfer for the residual that RO automatic prorata cannot assign; no bogus quantity blocking. Ordinary RO-only flow remains unchanged. Current priority Paket > ordinary RO; future SO > Paket > RO only when SO Manufacturing scope starts.

## READINESS AUDIT PASSED — SELECT REAL UAT SKU 12114, SLOT 2026-11-24 S1 (2026-11-24)

Feri submitted the actual output of `script/audit_package_uat_slot_readiness_readonly_ya.py` from TEST database `erp-yussyakmal-mrp-test`: `READ_ONLY_PACKAGE_UAT_SLOT_READINESS_OK`, with **77 free candidate combinations** and **2 candidates on already-used slots**. Details:
- `2026-11-27 S1`: batch id 1 already exists; 3 Confirmed ordinary RO; 1 capacity-feasible Paket candidate. Do NOT overwrite or stage a second snapshot.
- `2026-11-25 S3`: batch id 2 already exists; 1 Confirmed ordinary RO; 1 capacity-feasible Paket candidate. Do NOT overwrite.
- `2026-11-24 S1`: **no batch, 0 Confirmed ordinary RO**, 77 capacity-feasible multi-kitchen Paket combinations, 11 capacity-limited combinations.
- `2026-11-24 S3`: no batch, 0 feasible candidates.
- `2026-11-23 S2`: batch id 3 already exists, 0 feasible.
- `2026-11-22 S1`: no batch, 0 feasible.

**FIRST rollback test candidate chosen:** real Paket SKU **12114 Hampers EID SET D**, real assembly BoM **1405**, date **2026-11-24 S1**, components from **PST + ROTI** with 1 each for real component SKUs `11999` (PST, whole kitchen BoM output7, Published Max7), `12014` (ROTI, output7, max7), `12019` (PST, output5, max5). **No PCK-only BoM components** on the audited 12114 assembly. Test Qty 1 Paket yields three kitchen MOs with output7+7+5 and protects exactly 1 each for assembly; remaining 6+6+4 (16 total) is explicitly for separate standard PCK→store internal transfer and NOT granted to a store without RO. This is a source-only interpreted calculation to be proved by rollback in Odoo, not a claim of actual completed stock. This is a past slot, chosen solely for isolated test transactions, not a live shipping schedule.

**New source-only tests staged:**
- `script/check_package_testdb_registry_readonly_ya.py`: after guarded TEST-only install, verifies Odoo loaded models, fields, installed XML views, PCK manufacturing operation type 279/PCK Stock, and chosen test date-slot still unoccupied. NO DB writes.
- `script/test_package_joint_stage_mo_rollback_ya.py`: only after install + verified GUI backup, creates real SKU12114 Qty1 Paket RO to a real active store; confirms, previews, snapshots one date-slot, creates native kitchen MOs from published Planning, validates 3 kitchen MOs with no Done, no package assembly/DO/stock. Everything happens inside savepoint with intentional exception AND explicit rollback; then checks absence of RO, batch, MOs. NOT a real stock Done or package delivery E2E yet. No fabricated BoM/Planning/master/stock. Uses sudo within rollback to test mechanical Odoo paths; distinct creator/Packing permissions still require GUI role test.

**Next instructions for Feri:** First `git pull`, `python3 -m compileall -q addons/ya_package_store_ro script/test_package_joint_stage_mo_rollback_ya.py script/check_package_testdb_registry_readonly_ya.py` and previous source tests; back up `erp-yussyakmal-mrp-test` using Odoo GUI and verify backup. Then copy ONLY `addons/ya_package_store_ro/.` into `/opt/odoo19/custom-addons/ya_package_store_ro/`, ensure owner `odoo19`, perform `-i ya_package_store_ro --stop-after-init --no-http` with **ONLY** `-d erp-yussyakmal-mrp-test`. Confirm exit status 0 and run registry check via Odoo shell on test DB BEFORE any UAT rollback. If install fails, stop and send exact traceback; no production install, no attempt to reset occupied batches. No need to restart shared web service for read-only Odoo shell smoke; coordinate restart separately for GUI testing. First rollback E2E may proceed only if registry check PASS and 2026-11-24 S1 remains free. Need later separate physical component stock/assembly/DO/receipt tests.

**Owner business principle:** 20-year SOP is authoritative, not everything must be automated, no block for legitimately unallocated BoM surplus; operator can send it via standard internal transfer. Paket highest now, RO next; SO>Paket>RO is future only. Ordinary RO already proven, preserve its super() code unchanged.

## FERI ACTUAL ROLLBACK UAT BLOCKED BY ROLE CHECK — TEST SCRIPT FIXED (2026-11-24)

Feri ran test-only `script/test_package_joint_stage_mo_rollback_ya.py` via Odoo shell on `erp-yussyakmal-mrp-test`. It printed `DATABASE`, mode, `UAT_REAL_PACKAGE: 12114 Hampers EID SET D`, `UAT_REAL_STORE: T_BAN Toko Bandara`, `UAT_REAL_SLOT: 2026-11-24 S1`. It then FAILED at the first nested `ya.package.store.ro.line.create` with `UserError: Only the Paket RO creator role may add Draft SKU lines.`. **This is not an MRP/BoM/Planning/stock defect**: Odoo shell sudo bypasses normal ACL but does NOT make `env.user` a member of the custom `ya_package_store_ro.group_ya_package_ro_creator` role; business guard deliberately refused it. No `PACKAGE_RO_CONFIRM_PASS` or later stage passed in this run. Shell exception aborts transaction; no production DB touched.

**Only the test script** updated in GitHub commit `70c3c72f43f8f747d28c05306e6a62090646596a`. Keeps real model security UNCHANGED. Inside mandatory rollback savepoint it creates two role-specific TEMPORARY res.users accounts (reserved invalid example logins, no password/reset email), granting existing creator and Packing Admin groups. Test creates/confirms RO as creator, previews/stages Pre Produksi as Packing Admin, generates MOs as Packing Admin. Impersonation uses `with_user(...).sudo()` for mechanical ORM smoke with proper current `env.user.has_group`; not proof of all real-world UI ACLs. Every temporary user, RO, batch and MO is rolled back, with post-rollback assertion that role users no longer exist. No permanent permission grants; do not modify original addon role checks, production users, company master, or Plan/BoM.

**Next Feri test: NO MODULE UPGRADE/RESTART.** Only `cd ~/odoofromzero && git pull && python3 -m py_compile script/test_package_joint_stage_mo_rollback_ya.py` then rerun the same Odoo shell stdin command on **`erp-yussyakmal-mrp-test`**. Since only the UAT script changed, no deployed addon modification is required. If it fails again, report COMPLETE traceback; do not claim package production successful until `PACKAGE_JOINT_STAGE_MO_ROLLBACK_PASS` and `ROLLBACK_NO_RO_BATCH_MO_PERSISTED_PASS`. The user-end flow ordinary RO remains unaffected.

## FERI ACTUAL UAT PASS — PAKET-ONLY JOINT PRE PRODUKSI + KITCHEN MO ROLLBACK (2026-11-24)

**First real Odoo transactional PASS:** Feri ran `script/test_package_joint_stage_mo_rollback_ya.py` on `erp-yussyakmal-mrp-test` after the test-user role fix. Final output:
- `ROLLBACK_TEST_ROLE_USERS_READY`
- `PACKAGE_RO_CONFIRM_PASS`
- `JOINT_PREVIEW_WITHOUT_FAKE_RO_PASS`
- `JOINT_PREPRODUCTION_FROZEN_PAKET_FIRST_PASS`
- `PCK_INTERNAL_TRANSFER_FALLBACK_QTY: 16`
- `JOINT_KITCHEN_MO_CONFIRM_PASS`; `KITCHEN_MO_COUNT: 3`
- `ROLLBACK_EXPECTED_OK`, `ROLLBACK_ROLE_USERS_NOT_PERSISTED_PASS`, `ROLLBACK_NO_RO_BATCH_MO_PERSISTED_PASS`
- `PACKAGE_JOINT_STAGE_MO_ROLLBACK_PASS`.

This confirms that Paket add-on **was installed on the TEST database** (script asserted state installed, version 19.0.1.3.0), actual SKU **12114 Hampers EID SET D**, real BoM **1405**, actual T_BAN store, Published Planning **2026-11-24 S1**, Paket quantity 1, 3 native kitchen MOs/PST+ROTI and 16 leftover kitchen units preserved for a real standard Packing→store internal transfer, NOT artificially assigned. **All created test RO, batch, MOs and temporary users rolled back**; no persistent stock change. Do NOT falsely say module still uninstalled. No production database change. No actual MO Done, PCK physical FG transfer, native Paket assembly MO Done, combined DO or store receipt has been tested yet.

**NEXT source-only stage prepared (not yet Feri-tested):** `script/test_package_joint_mixed_stage_mo_rollback_ya.py`. Same real free TEST slot and real Paket 12114, with two ordinary confirmed ROs in the **same date-slot** for component **SKU 11999** of the same kitchen PST: T_KD Qty2 and T_RAI Qty1 (real planning BoM batch output7, Published Max7). Paket source T_BAN requires protected component Qty1. Joint gross4 ⇒ kitchen MO7; store allocation 4 and2 (ordinary RO 2+2 surplus, and 1+1 surplus), package protected1; **zero unallocated 11999**. Other two Paket-only components output7 and5 reserve1 each, leave **10 units** for standard internal transfer. Three native kitchen MOs total. Creates three actual temporary role users (Paket creator, Manufacturing Manager, Packing Admin), two ordinary RO and one Paket RO, one immutable joint batch and native kitchen MOs entirely within explicit savepoint+rollback. Asserts no records/users survived. Does NOT touch normal operator/master data or stock, and is NOT physical goods E2E. No addon source changed since installed test version, thus **NO re-install/upgrade or shared service restart needed** for this new standalone test.

Next Feri commands:
`cd ~/odoofromzero && git pull && python3 -m py_compile script/test_package_joint_mixed_stage_mo_rollback_ya.py`, then Odoo shell TEST DB `< script/test_package_joint_mixed_stage_mo_rollback_ya.py`. Expected markers:
`MIXED_ORDINARY_RO_CONFIRMED_PASS`,
`MIXED_JOINT_PREVIEW_PASS`,
`MIXED_PACKAGE_FIRST_STORE_PRORATA_PASS`,
`MIXED_NATIVE_KITCHEN_MO_CONFIRM_PASS`,
`MIXED_ROLLBACK_NO_RO_BATCH_MO_USERS_PERSISTED_PASS`,
`PACKAGE_JOINT_MIXED_STAGE_MO_ROLLBACK_PASS`.
If actual master/Planning changed, investigate rather than override it. If an error occurs, send full traceback; avoid additional local fixes outside GitHub without review.

Prioritization remains: current Paket > RO toko; later Sales Order > Paket > RO only when SO Manufacturing introduced. Preserve original store RO Qty and existing RO-only flow. Internal transfer fallback is a valid SOP exception; do not hard-stop the whole workflow because the system cannot automatically distribute some finished output.

## FERI ACTUAL UAT PASS — MIXED PAKET + ORDINARY RO SAME SLOT (2026-11-24)

Feri ran the actual Odoo shell rollback test `script/test_package_joint_mixed_stage_mo_rollback_ya.py` on `erp-yussyakmal-mrp-test`; output:
`MIXED_ROLLBACK_TEST_ROLE_USERS_READY`,
`MIXED_PAKET_RO_CONFIRMED_PASS`,
`MIXED_ORDINARY_RO_CONFIRMED_PASS`,
`MIXED_JOINT_PREVIEW_PASS`,
`MIXED_PACKAGE_FIRST_STORE_PRORATA_PASS`,
`MIXED_NATIVE_KITCHEN_MO_CONFIRM_PASS`,
`ROLLBACK_EXPECTED_OK`,
`MIXED_ROLLBACK_NO_RO_BATCH_MO_USERS_PERSISTED_PASS`, and
`PACKAGE_JOINT_MIXED_STAGE_MO_ROLLBACK_PASS`.

REAL source: Paket SKU **12114** Hampers EID SET D from store T_BAN, assembly BOM 1405, mixed with same-slot ordinary RO for component **11999** (PST, real kitchen BOM **1330**, output7, Published Max7). T_KD store originally ordered2 and T_RAI originally1; Paket protects1; 7 MO output: T_KD final4 (original2+BoM extra2), T_RAI final2 (original1+extra1), Paket1, leftover0 for SKU 11999. Other two package-only kitchen components have **10 pieces combined** unallocated which remain reserved for ordinary SOP **PCK->store internal transfer** (not phantom RO). **3 kitchen MOs Confirmed**. All RO, Pre Produksi batch, MOs and temporary role users **rolled back**, nothing remained in DB. This is decisive transactional evidence for Paket-first and Hamilton extra allocation in a mixed batch. Original ordinary-only path unchanged.

**Pending physical scope:** kitchen MO Done with native raw moves, real FG transfer into PCK, one native Paket assembly MO per SKU, true component consumption and finished Paket move, append SKU to existing store DO, dispatch→transit→store receipt; do NOT claim any physical stock/DO UAT PASS yet. No new Odoo module code or upgrade/restart required as of this checkpoint.

**Next new READ-ONLY stock audit**: `script/audit_package_12114_mo_materials_readonly_ya.py` uses real Published Planning 2026-11-24 S1 and original BoM output sizes for component SKUs 11999 (7), 12014 (7), 12019 (5), reads raw BoM line quantities, kitchen source location stock quants (physical, reserved, free), and reports shortages/tracking. It never creates MO, stock move, transfer, product, fake inventory or BoM; results are *advisory*, exact native reservation/lot checks still needed. Execute using Odoo shell only on `erp-yussyakmal-mrp-test`. If insufficient, follow existing actual CDC→kitchen stock SOP, not synthetic stock; choose a viable physical-stock test case later.

Commands for Feri:
`cd ~/odoofromzero && git pull && python3 -m py_compile script/audit_package_12114_mo_materials_readonly_ya.py`.
Then `sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test --no-http < script/audit_package_12114_mo_materials_readonly_ya.py`.
Expected `READ_ONLY_PAKET_12114_MATERIALS_OK` and material readiness summary; NO installation/restart needed. Next physical rollback script must depend on confirmed native materials read-out. Owner SOP is authoritative, only critical stock integrity checks block. Do not use source-only tests as evidence of physical MO/stock state.

## REUSE EXISTING CDC 10X INVENTORY ADJUSTMENT, DO NOT REBUILD (OWNER REMINDER 2026-11-24)

Owner reminded us an existing script already seeds 10x missing raw materials using Odoo inventory adjustments. **Confirmed existing repo scripts:** `script/dev_seed_cdc_material_10x_ya.py` and `script/check_dev_seed_cdc_material_10x_source_readonly_ya.py`. This was overlooked when discussing shortage of 22 material-by-kitchen combinations for Paket SKU 12114. Do not create a duplicate inventory adjustment tool or assume such capability is absent.

The original seed script has **FIXED** `TARGET_DATE='2026-11-27'`, `TARGET_SLOT='S1'`, `MULTIPLIER=10`; it requires exactly one **persisted** `ya.packing.batch` in `production_ok` with linked native **Confirmed MOs**, calculates raw shortages by kitchen, and applies **standard inventory adjustment at CDC/Stock only** after strict token `YA_DEV_CDC_STOCK_APPLY=YES_I_CONFIRM_TEST_DB`; otherwise dry-run and rollback. It explicitly commits in APPLY mode. It **does not** transfer CDC stock into kitchen buffers. Do not invoke APPLY to serve Paket UAT `2026-11-24 S1`: it would affect the unrelated existing Nov27 batch. Paket RO 12114's Nov24 date-slot batch/MOs were rolled back and do not persist, so changing just the date literal will not work.

Reuse its proven method, source guard and standard inventory modes in a controlled TEST-only rollback scenario: establish real MO raw requirements for target trial inside savepoint; stage any needed test stock at CDC by reusing (not duplicating) the trusted inventory-adjustment logic, then standard CDC→kitchen internal transfers and native MO Done, FG→PCK, assembly/DO. Make clear that real physical stock isn't established by test seed and that no product/Planning/BoM/PCK master should change. No stock seed changes were actually made by this reminder or handover update.

## NEW: REUSE ORIGINAL CDC 10X STOCK OPNAME IN ROLLBACK PAKET UAT (2026-11-24)

Feri ran `script/audit_package_12114_mo_materials_readonly_ya.py` on test DB; result `READ_ONLY_PAKET_12114_MATERIALS_OK`: MO 11999 PST 6 raw lines, MO 12014 ROTI 10 raw lines, MO 12019 PST 6 raw lines; **ALL 22 kitchen/raw combinations had test physical/reserved/free quants 0**. Not proof physical stock outside test DB is absent. No MO Done/UAT production stock passes yet.

Owner reminded us existing real stock-opname seed script `script/dev_seed_cdc_material_10x_ya.py` already uses native Odoo inventory adjustment 10x shortage. We inspected it and preserved it UNCHANGED, including Nov 27 S1 persisted batch, native `stock.quant.inventory_quantity`/`action_apply_inventory()`, and intentional commit only on explicit APPLY token. Its original preflight remains `script/check_dev_seed_cdc_material_10x_source_readonly_ya.py`. **NEVER APPLY original Nov27 seed for Nov24 Paket**; creates stock for wrong batch.

**New isolated rollback-only UAT**, not yet run by Feri:
- `script/test_package_12114_stock_10x_transfer_rollback_ya.py`: starts from previously **PASS** isolated Paket RO 12114 Qty1 / T_BAN / Nov24 S1. Creates temporary real creator/Packing users, confirms RO and Pre Produksi/MO, then reads actual native kitchen MO raw moves, grouped per material per actual kitchen PST and ROTI. Computes shortages, uses exact CDC seed formula `target=max(current, 10*max(gross_short-current,0))` rounded up, with same strict no-reservation/nonnegative/raw-UoM/storable/untracked/unique-CDC-root-quant safeguards and Odoo native `inventory_quantity` + `action_apply_inventory()` — no direct quant SQL, no permanent seed. Next, issues and validates standard native CDC→PST and CDC→ROTI **internal transfers only for each MO's actual raw-material needs, not the full 10x CDC buffer**, and verifies each kitchen then has enough free stock. Runs inside savepoint and explicit unconditional rollback; checks users/RO/batch/MO and original per-SKU CDC/kitchen physical and reserved balances restored. **Does not mark kitchen MOs Done, manufacture Paket, transfer FG, create DO or store receipts.** No change to existing addon or to original seed script; no deploy/restart/upgrade required.
- `script/check_package_12114_stock_10x_transfer_source_ya.py`: source preflight verifies test DB guard, real slot, original seed signature intact, no `commit` or `_update_available_quantity`, native opname and transfers/rollback. Not yet run Feri.
- Feri next: `cd ~/odoofromzero && git pull && python3 script/check_package_12114_stock_10x_transfer_source_ya.py && python3 -m py_compile script/test_package_12114_stock_10x_transfer_rollback_ya.py`. **Only if source PASS**, with existing verified GUI backup, run `sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test --no-http < script/test_package_12114_stock_10x_transfer_rollback_ya.py`.
- Target real results `CDC_10X_OPNAME_NATIVE_APPLY_ROLLBACK_PASS`, `NATIVE_CDC_KITCHEN_TRANSFER_ROLLBACK_PASS`, `ROLLBACK_STOCK_OPNAME_AND_PICKINGS_VERIFIED_PASS`, `PACKAGE_12114_10X_OPNAME_TRANSFER_ROLLBACK_PASS`. This is first native stock-adjustment UAT for Paket, *NOT YET PASS until Feri log*. If Odoo inventory adjustment refuses a product or a stock transfer, stop at traceback; do not alter master or force quants. Potential native Odoo account valuation side-effects are included in transaction rollback; no persistent side effects claimed until verified.
- Once actual seed+transfer rollback passes, next build native kitchen MO Done + FG→PCK + native assembly MO and combined DO/receipt rollback tests, without duplicating seed or letting any test stock escape.

## FERI FIRST PAKET CDC 10X ROLLBACK: OPNAME PASS; POST-TRANSFER CHECK FAILED (2026-11-24)

Feri ran `script/test_package_12114_stock_10x_transfer_rollback_ya.py` on `erp-yussyakmal-mrp-test`. All previous Paket RO 12114 Confirmed / joint snapshot / 3 kitchen MO Confirmed stages passed. `CDC_10X_OPNAME_PRODUCT_COUNT: 10` and `CDC_10X_OPNAME_NATIVE_APPLY_ROLLBACK_PASS` were printed, proving standard native CDC inventory adjustments in the **uncommitted rollback test transaction** for 10 unique raw-material SKUs. **NEXT stage DID NOT PASS**: `AssertionError: Native transfer did not supply actual MO raw materials` at the old test's single free-stock check. No `NATIVE_CDC_KITCHEN_TRANSFER_ROLLBACK_PASS` or post-check passed. `finally: env.cr.rollback()` executes on exception; Feri did not report any commit and no production database operation occurred. Need verify rollback with subsequent invariant checks if desired. Do not claim that stock consumption/MO Done/FG/Paket assembly/DO passed.

**Working hypothesis, NOT yet established by evidence**: after a native CDC→kitchen picking is validated, Odoo may reserve some incoming material stock to the confirmed kitchen MOs. Then `physical - reserved < full raw demand` would be an *incorrect readiness check* if that reservation belongs to the very MO being tested. Equally possible are real short delivery, wrong location/UoM or floating rounding. Do NOT solve by seeding extra inventory or ignoring stock integrity.

**GitHub test-source-only diagnostic patch:** `script/test_package_12114_stock_10x_transfer_rollback_ya.py` now captures each native internal stock.move Done Qty in the product base UoM, flushes/invalidates ORM cache after validation, checks actual physical/reserved/free and outputs `STOCK_DIAGNOSTIC:` with kitchen, product, MO raw move state and line count on mismatches; outputs `POST_TRANSFER_DIAGNOSTIC_COUNT` and individual reasons. `script/check_package_12114_stock_10x_transfer_source_ya.py` extends static guards to require this diagnostic reporting. The data stage, 10x formula, standard opname and standard transfers remain unchanged, with no commit and unconditional rollback. **Not yet rerun by Feri.** Do not treat diagnostic run as a new stock PASS until reported.

Next Feri commands:
`cd ~/odoofromzero && git pull && python3 script/check_package_12114_stock_10x_transfer_source_ya.py && python3 -m py_compile script/test_package_12114_stock_10x_transfer_rollback_ya.py`
Then same Odoo shell TEST-ONLY `sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test --no-http < script/test_package_12114_stock_10x_transfer_rollback_ya.py`.
Send `STOCK_DIAGNOSTIC:`, `POST_TRANSFER_DIAGNOSTIC_COUNT`, the final exception and any PASS markers; decide exact fix from measured values. Existing Paket addon, MRP and original CDC seed script **not changed**; no reinstall or service restart.

## FERI VERIFIED CDC→KITCHEN TRANSFER SUCCESS; OLD CHECK FALSE NEGATIVE (2026-11-24)

Feri reran rollback-only `script/test_package_12114_stock_10x_transfer_rollback_ya.py` with diagnostics. Confirmed test DB `erp-yussyakmal-mrp-test`, SKU12114/T_BAN/2026-11-24 S1; RO Confirm, joint snapshot, 3 MO Confirm PASS; **CDC 10x inventory adjustment completed successfully for 10 unique material SKUs** (`CDC_10X_OPNAME_PRODUCT_COUNT:10`, `CDC_10X_OPNAME_NATIVE_APPLY_ROLLBACK_PASS`), inside uncommitted transaction. For all **17 unique kitchen+material combinations** (7 PST, 10 ROTI), `TRANSFER_DONE == TRANSFER_PLANNED == NEED`, physical kitchen stock == MO raw need; Odoo automatically reserved **all materials for the same three Confirmed MOs**: `RESERVED == PHYSICAL == NEED`, `FREE = 0`, raw moves `assigned` with native move lines. Thus 17 `RECEIPT_OK=True`, `PHYSICAL_OK=True`, `FREE_OK=False`. The old assert `free >= need` is **mathematically false for fully reserved MOs**, NOT a failed transfer. `POST_TRANSFER_DIAGNOSTIC_COUNT=17` reflected wrong free-stock criteria, not 17 missing goods. Native Odoo auto reservation is expected/desirable. Previous exception did NOT mean CDC transfer or Odoo stock validation failed. The script always ran `finally: env.cr.rollback()`; no commit, no production DB changes. The final after-success rollback verification was not reached in that diagnostic run.

**Exact GitHub test-only fix now staged, still not re-run by Feri:**
- `script/test_package_12114_stock_10x_transfer_rollback_ya.py`: verifies native Done Qty per CDC→kitchen picking, physical stock no smaller than need, and **ownership of auto reservation** via `move.move_line_ids` of assigned raw stock moves that belong ONLY to this rollback's MO records, and source location under matching real kitchen warehouse. `effective_for_mo = physical - all_reserved + reserved_by_this_test_MOs` must cover MO raw need. Never count another MO's reservations. Also verifies `own_reserved <= quant reserved <= physical`, no negative free-stock. Logs `POST_TRANSFER_DIAGNOSTIC_COUNT:0` and `AUTO_RESERVED_FOR_TEST_MO_COMBINATIONS:17` if unchanged source behavior. No new inventory, release, picking or module changes; still stock opname 10x+native internal transfers, no MO Done yet. All temporary test RO/batch/MOs/users plus inventory quants/pickings are rollback-only. Existing original 27Nov CDC seed unchanged.
- `script/check_package_12114_stock_10x_transfer_source_ya.py` now static-checks own-MO reservation accounting and guard against untracked foreign reservations. No addon deployment/reinstall/restart needed.
- Target source first: `PAKET_CDC_10X_ROLLBACK_SOURCE_OK`, then Odoo shell rollback: `POST_TRANSFER_DIAGNOSTIC_COUNT:0`, `NATIVE_CDC_KITCHEN_RESERVED_TO_TEST_MO_PASS`, `NATIVE_CDC_KITCHEN_TRANSFER_ROLLBACK_PASS`, `ROLLBACK_STOCK_OPNAME_AND_PICKINGS_VERIFIED_PASS`, `PACKAGE_12114_10X_OPNAME_TRANSFER_ROLLBACK_PASS`. Feri should send traceback if any new error; do not overclaim test PASS before actual execution.

Next if PASS: only then build/verify test rollback for native **MO Done** consumption, kitchen FG→PCK, one PCK Paket MO, and existing store DO/receipt. Keep 20-year bakery SOP and no-negative-stock; no phantom store RO or artificial master routes.

## 2026-11-24 — FERI ACTUAL NATIVE 10X OPNAME+CDC→KITCHEN UAT: FULL PASS

Feri executed `script/test_package_12114_stock_10x_transfer_rollback_ya.py` on `erp-yussyakmal-mrp-test`. Full real output: Paket SKU12114, T_BAN, slot 2026-11-24 S1; `ROLLBACK_TEST_ROLE_USERS_READY`, `PACKAGE_RO_CONFIRM_PASS`, `JOINT_PREVIEW_WITHOUT_FAKE_RO_PASS`, `JOINT_PREPRODUCTION_FROZEN_PAKET_FIRST_PASS`, `PCK_INTERNAL_TRANSFER_FALLBACK_QTY:16`, `JOINT_KITCHEN_MO_CONFIRM_PASS`, `KITCHEN_MO_COUNT:3`, `CDC_10X_OPNAME_PRODUCT_COUNT:10`, `CDC_10X_OPNAME_NATIVE_APPLY_ROLLBACK_PASS`, `POST_TRANSFER_DIAGNOSTIC_COUNT:0`, `AUTO_RESERVED_FOR_TEST_MO_COMBINATIONS:17`, `NATIVE_CDC_KITCHEN_RESERVED_TO_TEST_MO_PASS`, `CDC_TO_KITCHEN_PICKING_COUNT:2`, `PST_AND_ROTI_MATERIAL_READY_ROLLBACK_PASS`, `NATIVE_CDC_KITCHEN_TRANSFER_ROLLBACK_PASS`, `ROLLBACK_EXPECTED_OK`, `ROLLBACK_ROLE_USERS_NOT_PERSISTED_PASS`, `ROLLBACK_STOCK_OPNAME_AND_PICKINGS_VERIFIED_PASS`, `ROLLBACK_NO_RO_BATCH_MO_PERSISTED_PASS`, **`PACKAGE_12114_10X_OPNAME_TRANSFER_ROLLBACK_PASS`**.

**Meaning:** Standard stock.quant Inventory Adjustment at CDC for 10 distinct storable products posted inside a test rollback, followed by TWO real native internal pickings CDC→PST/ROTI; Odoo correctly auto-reserved materials for all 17 source-kitchen/raw product combinations to the 3 Confirmed kitchen MOs. The exact finished target package remains one SKU12114, protected 1 each of its 3 components; the 16 other kitchen finished units are separately tracked for normal internal transfer, NOT a dummy store order. No shortage after including only reservations belonging to test MOs. All test RO/users/batch/MOs/pickings and original material physical+reserved quants were verified restored after rollback. **No kitchen MO Done or finished stock production was tested in this PASS**. Do not conflate physical transfer of raw materials with finished kitchen stock.

**Next staged source ONLY, Feri not run yet:** `script/test_package_12114_mo_done_fg_assembly_rollback_ya.py`, followed by `script/check_package_12114_mo_done_fg_assembly_source_ya.py`. The new standalone Python Odoo-shell test reuses same already-passed 12114 RO→joint MOs→10x native CDC Stock Opname→2 real CDC kitchen transfers, then calls **native Odoo 19 `mrp.production.button_mark_done()`** on the 3 MOs with actual reserved material (untracked products, no WOs), checks native raw stock consumption deltas, no negative material quantities, actual finished kitchen stock, then calls existing `ya.packing.batch.action_ya_fg_move_to_packing()` to move true finished stock into PCK by 2 native Done pickings and verifies double-click idempotence and PCK quantities. Finally calls `action_ya_create_package_assembly_mos()` to create exactly one **native PCK assembly MO Confirmed** with exact frozen BoM1405 components and no WOs, no component consumption. Entire process is in one explicit savepoint+rollback, with test-user, SKU finished kitchen/PCK and material CDC/kitchen stock balances re-verified restored. No `commit`, no addon change/install/upgrade/restart, no alterations to the original DEV CDC seed.

**NOT YET TESTED**: Native Paket assembly MO Done (PCK consumption/finished Paket), combined per-store DO Dispatch→Transit→Store Receipt, or extra manual/internal transfer surplus. Run next stage ONLY on `erp-yussyakmal-mrp-test` with GUI backup and an unoccupied date-slot; if any Odoo wizard/error occurs, stop and send exact traceback rather than force MO state/stock or tamper with old successful RO-only methods.

Feri commands:
`cd ~/odoofromzero && git pull && python3 script/check_package_12114_mo_done_fg_assembly_source_ya.py && python3 -m py_compile script/test_package_12114_mo_done_fg_assembly_rollback_ya.py`
Then ONLY if source checker exits 0:
`sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test --no-http < script/test_package_12114_mo_done_fg_assembly_rollback_ya.py`.
Expected final `PACKAGE_12114_MO_DONE_FG_ASSEMBLY_ROLLBACK_PASS`; intermediate markers `NATIVE_KITCHEN_MO_DONE_3_PASS`, `NATIVE_MO_RAW_CONSUMPTION_DELTAS_PASS`, `NATIVE_KITCHEN_TO_PCK_FG_TRANSFER_ROLLBACK_PASS`, `PCK_PACKAGE_ASSEMBLY_MO_CONFIRMED_ROLLBACK_PASS`, `ROLLBACK_FINISHED_STOCK_VERIFIED_PASS`. No persisted inventory or production changes if test succeeds; errors must be inspected, and current script has finally rollback.

## FERI UAT REAL MO Done/FG PASS; PCK assembly failed combined test assertion (2026-11-24)

Feri ran `script/test_package_12114_mo_done_fg_assembly_rollback_ya.py` in dedicated TEST `erp-yussyakmal-mrp-test`. Real output PASS through `NATIVE_KITCHEN_MO_DONE_3_PASS` for:
- `11999` PST, FG finished Qty 7, 6 raw moves; `12019` PST FG Qty 5, 6 raw moves; `12014` ROTI FG Qty 7, 10 raw moves.
- `NATIVE_MO_RAW_CONSUMPTION_DELTAS_PASS`, `NATIVE_MO_FINISHED_KITCHEN_STOCK_DELTAS_PASS` confirm proper native Odoo19 consumption, no negative raw stock, real FG.
- `NATIVE_KITCHEN_TO_PCK_FG_PICKINGS:2`, `NATIVE_KITCHEN_TO_PCK_FG_TRANSFER_ROLLBACK_PASS`, `NATIVE_FG_DOUBLE_CLICK_IDEMPOTENCE_PASS` confirm real Done FG stock pickings from PST+ROTI into PCK.

**Test then failed** at Python line 641 with generic `AssertionError`, specifically after `assembly_result = batch_as_packing.action_ya_create_package_assembly_mos()` and `len(assemblies)==1`; old line was combined `assert assembly.product_id == product and assembly.product_qty == 1`. This implies **one native PCK Paket assembly MO was created** but one/both combined test conditions failed. DO NOT declare PCK assembly MO PASS, even if correct stock prior. No confirmation of which field wrong in the old log. Error unwound savepoint and `finally env.cr.rollback()` so no intentional persistence; post-success rollback markers were not reached. Dedicated test DB only, no productive stock changes.

**GitHub TEST SCRIPT ONLY diagnostic patch**: `script/test_package_12114_mo_done_fg_assembly_rollback_ya.py` now prints `PCK_ASSEMBLY_ACTUAL` and `PCK_ASSEMBLY_EXPECTED` with native product SKU/ID, MO Qty, UoM, converted base UoM Qty, BoM ID, operation type, source/dest PCK Stock IDs, state, frozen demand Qty. Then separate explicit assertions report if product, Qty, BoM, operation type or locations differ; never silently correct/override a wrong MO. The original addon `addons/ya_package_store_ro/models/package_assembly.py` and other modules remain UNCHANGED. Run source preflight and re-run the same rollback test on the same test slot only after `git pull`; if it fails, send exact `PCK_ASSEMBLY_ACTUAL`, `PCK_ASSEMBLY_EXPECTED` and traceback. Do not edit BoM, override Qty, add fake stock, upgrade/restart addon yet.

Next Feri:
`cd ~/odoofromzero && git pull && python3 script/check_package_12114_mo_done_fg_assembly_source_ya.py && python3 -m py_compile script/test_package_12114_mo_done_fg_assembly_rollback_ya.py`.
Then `sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test --no-http < script/test_package_12114_mo_done_fg_assembly_rollback_ya.py`.
All previously proved ordinary RO, Paket+RO, kitchen MO, CDC stock and FG-to-PCK remains valid. Pending actual Paket assembly MO Done, combined DO and store receipt UAT. Keep one immutable slot, no negative stock, no overnight Packing inventory.

## FERI REAL PCK ASSEMBLY DIAGNOSTIC: MODULE CORRECT, TEST VARIABLE SHADOWED (2026-11-24)

Feri reran actual Odoo-shell `script/test_package_12114_mo_done_fg_assembly_rollback_ya.py` on TEST DB. 3 kitchen MO Done PASS, BoM raw consumption PASS, real FG qty PASS, two native FG transfer Done into PCK PASS, double-click transfer PASS. Then `batch_as_packing.action_ya_create_package_assembly_mos()` **succeeded in creating one native PCK assembly MO**. New diagnostic revealed:

- `PCK_ASSEMBLY_ACTUAL: MO_ID:65 PRODUCT_ID:712 SKU:12114 PRODUCT_QTY:1.0 MO_UOM:Pcs QTY_IN_BASE_UOM:1.0 BOM_ID:1405 TYPE_ID:279 SRC_LOCATION_ID:20 DEST_LOCATION_ID:20 STATE:confirmed`. This is **exactly the correct real Paket SKU, qty, BoM, manufacturing route and PCK/Stock**.
- `PCK_ASSEMBLY_EXPECTED: PRODUCT_ID:2524 SKU:11520 FROZEN_PRODUCT_IDS:[712] FROZEN_QTY:0`. This was an **INVALID TEST EXPECTATION**, not a functional/module defect. The test's initial `product` variable held final Paket SKU12114 (ID712) but was later overwritten in the raw-material inventory loop `product = products[pid]`; last raw product was SKU11520 (ID2524). Thus test compared correctly created assembly MO to the last raw component, and its frozen Qty filter also wrongly returned 0. Error `AssertionError: PCK assembly WRONG PRODUCT: actual 712 expected 2524` proves the test only.

**Fix staged in GitHub, Feri not yet rerun:**
- `script/test_package_12114_mo_done_fg_assembly_rollback_ya.py`: immediately after querying final Paket SKU, binds immutable lexical reference `package_product = product`; PCK expected product ID, SKU, base UoM, frozen demand Qty query and native assembly MO assertions now use only `package_product`, not loop-shadowed `product`; adds check against frozen demand SKU and current requested SKU. No stock or Odoo addon edits.
- `script/check_package_12114_mo_done_fg_assembly_source_ya.py`: static guard requires stable Paket product and refuses shadowed expected product comparisons, keeping rollback source safeguards.
- Expected on rerun: `PCK_ASSEMBLY_ACTUAL` and `PCK_ASSEMBLY_EXPECTED` both show SKU12114, ID712, Qty1, BoM1405, PickingType279 and PCK location20; `PCK_PACKAGE_ASSEMBLY_MO_CONFIRMED_ROLLBACK_PASS`, `PCK_PACKAGE_ASSEMBLY_DOUBLE_CLICK_IDEMPOTENCE_PASS`, `ROLLBACK_FINISHED_STOCK_VERIFIED_PASS`, and final `PACKAGE_12114_MO_DONE_FG_ASSEMBLY_ROLLBACK_PASS` after explicit rollback. **Do not claim full assembly PASS until Feri's runtime output.**

Feri commands: `cd ~/odoofromzero && git pull && python3 script/check_package_12114_mo_done_fg_assembly_source_ya.py && python3 -m py_compile script/test_package_12114_mo_done_fg_assembly_rollback_ya.py`; then Odoo-shell `-d erp-yussyakmal-mrp-test` with `< script/test_package_12114_mo_done_fg_assembly_rollback_ya.py`. Same prior backup and free date-slot restrictions; no module install/upgrade/restart. Original RO/Paket ordering, 10x CDC seed, kitchen MO logic, FG route and assembly model remain untouched. Remaining stages after that: **PCK Paket assembly MO Done** with actual component stock consumption; one native store DO mixing ordinary/Paket; dispatch→transit→store receipt; surplus standard transfers and edge scenarios.


## 2026-11-24 NIGHT — FERI REAL PCK PAKET ASSEMBLY CONFIRMED PASS; FINAL STORE RECEIPT ROLLBACK NEXT

**Feri actual runtime** of `script/test_package_12114_mo_done_fg_assembly_rollback_ya.py` on `erp-yussyakmal-mrp-test` achieved **`PACKAGE_12114_MO_DONE_FG_ASSEMBLY_ROLLBACK_PASS`** with all explicit successful markers:
- Paket SKU 12114 **Hampers EID SET D**, T_BAN store, 2026-11-24 S1; real Paket BoM 1405, final product ID 712.
- 10 raw material SKUs inventoried in CDC only within rollback; 2 native CDC→PST/ROTI pickings Done; 17 native MO-owned reservations; 3 real kitchen MOs Done (11999 PST7, 12019 PST5, 12014 ROTI7), all raw BoM consumption and FG quantities validated.
- 2 actual native FG pickings Done into PCK; double click blocked duplicates.
- 1 correct **native PCK assembly MO CONFIRMED**: actual and expected product ID712, SKU12114, Qty1, UoM Pcs, BoM1405, PCK manufacturing type ID279, source/destination PCK/Stock ID20; 3 assembly BoM raw components frozen exactly; double-click idempotent.
- `ROLLBACK_EXPECTED_OK`, `ROLLBACK_FINISHED_STOCK_VERIFIED_PASS`, `ROLLBACK_ROLE_USERS_NOT_PERSISTED_PASS`, `ROLLBACK_STOCK_OPNAME_AND_PICKINGS_VERIFIED_PASS`, `ROLLBACK_NO_RO_BATCH_MO_PERSISTED_PASS`. All changes reverted. No test stock persists.
- This **DOES NOT** yet prove assembly MO Done, native Paket DO transit and store receipt.

**Next prepared GitHub-only files (not yet executed by Feri):**
`script/test_package_12114_package_done_store_receipt_rollback_ya.py` extends exactly the already-PASS full stage from RO→CDC 10×→native kitchen MOs Done→native FG→PCK→PCK assembly MO Confirmed. It then (1) checks all 3 native PCK raw components available and untracked, `assembly.action_assign()`, (2) invokes native `button_mark_done()` (no bypass of consumption/stock checks) and verifies consumes exactly ONE each, finishes **one** SKU12114 in PCK, leaves **16 units kitchen BoM surplus** in PCK for separate approved real transfer SOP, (3) calls inherited `action_ya_generate_store_do()` to make exactly ONE native outgoing DO for T_BAN, validates demand1, no stock effect at generate and no duplicate on repeat, (4) validates Dispatch with real Odoo `button_validate()`, checks PCK reduction1, transit+1, store unchanged, checks **ONE** actual native generated Receipt, (5) validates Receipt with `button_validate()`, checks transit returns prior amount and store stock+1, and (6) forcibly rolls back all and verifies no persisted RO/users/MOs/pickings or original PCK/transit/store/kitchen/raw stock deltas. Paket-only case: **do not invent ordinary store RO, extra destinations, WO, fake BOM or negative stock**. Other mixed Paket+ordinary RO in ONE DO was already source/transaction stage1 allocation tested, but its **physical DO/receipt combination** remains a separate outstanding test.

`script/check_package_12114_full_store_receipt_source_ya.py` is a separate static no-DB safety preflight, requiring guard DB, original seed unchanged, native critical flows/no commit, no synthetic allocations. No Odoo addon business changes, reinstall, upgrade or restart. Feri source preflight first, then one rollback Odoo shell on TEST DB with verified test backup. These are **NOT YET PASSED** until Feri provides actual output. If an actual wizard/error occurs, respect it and inspect specific source; no forced stock/manual zeroing.

Feri commands:
`cd ~/odoofromzero && git pull && python3 script/check_package_12114_full_store_receipt_source_ya.py && python3 -m py_compile script/test_package_12114_package_done_store_receipt_rollback_ya.py`.
On source PASS, test DB:
`sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test --no-http < script/test_package_12114_package_done_store_receipt_rollback_ya.py`.
Expected `PCK_NATIVE_ASSEMBLY_MO_DONE_PASS`, `PCK_NATIVE_ASSEMBLY_COMPONENT_CONSUMPTION_PASS`, `PCK_PAKET_STORE_DO_DEMAND_AND_IDEMPOTENCE_PASS`, `PCK_TO_TRANSIT_PAKET_DISPATCH_DONE_PASS`, `NATIVE_STORE_RECEIPT_T_BAN_DONE_PASS`, `ROLLBACK_PAKET_PCK_TRANSIT_STORE_VERIFIED_PASS`, and final `PACKAGE_12114_FULL_STORE_RECEIPT_ROLLBACK_PASS`.

**Maintain big picture**: normal store RO-only flow already PASS and must not regress; mixed package priority+ordinary prorata stage1 UAT PASS; future Sales Order higher priority and combined single DO/store when introduced. Do not declare whole YA business workflow deployed or ready for LIVE; tests remain on dedicated test database. Packing has no overnight stock by SOP; stage next also needs explicit standard surplus internal transfer and physical mixed DO/receipt validation before full rollout.

## 2026-11-24 — FERI COMPLETE REAL PAKET-ONLY DO→TRANSIT→STORE RECEIPT PASS

**Real Feri Odoo-shell output:** `script/test_package_12114_package_done_store_receipt_rollback_ya.py` on **erp-yussyakmal-mrp-test** returned `PACKAGE_12114_FULL_STORE_RECEIPT_ROLLBACK_PASS`. It reverified all prior stages and proved:
- 10 raw input SKUs corrected using **standard Odoo 10x CDC stock opname within rollback**, 2 real CDC→kitchen transfers and auto-reservation in 17 material×kitchen combinations.
- 3 native kitchen MO Done and exact 22 raw line consumptions (11999 PST7, 12019 PST5, 12014 ROTI7), two native kitchen→PCK FG transfers Done.
- 1 actual native PCK Paket assembly MO for final SKU12114 Qty1 BoM1405, exactly 3 raw components Done, one final Paket produced and stocked in PCK.
- 1 native outgoing DO for T_BAN; double-click did not duplicate; physical Dispatch Done removed Paket from PCK and put it into Transit, generated 1 native receipt; receipt Done put exactly one Paket into T_BAN/Stock and cleared Transit. Store stock did NOT rise before receipt.
- All rollback markers PASS, including `ROLLBACK_PAKET_PCK_TRANSIT_STORE_VERIFIED_PASS`, `ROLLBACK_FINISHED_STOCK_VERIFIED_PASS`, `ROLLBACK_STOCK_OPNAME_AND_PICKINGS_VERIFIED_PASS`, `ROLLBACK_NO_RO_BATCH_MO_PERSISTED_PASS`. There is no persisted test stock, user, MO or DO.
- `PCK_KITCHEN_SURPLUS_REQUIRES_SEPARATE_TRANSFER:16.0` — **real residuals in PCK just before test rollback**, 6+6+4 of kitchen components (3 SKUs); NOT automatically placed into any RO/DO; no Packing overnight policy requires an actual separate native internal transfer, with store destination selected by authorized operator.
- **THIS IS PAKET-ONLY CASE**, not evidence of physical Paket+ordinary mixed DO in the same store. Prior mixed Paket+ordinary *preproduction allocation and kitchen MO Confirmed* UAT was PASS, not full physical mixed DO/receipt. This plus separate surplus transfer remain outstanding before full YA workflow sign-off, along with SO integration, operational volume and roles.

**Next newly staged rollback-only UAT (Feri has NOT run):**
- `script/test_package_12114_surplus_internal_transfer_rollback_ya.py`: extends exact already-PASS full Paket receipt test, then explicitly selects **T_BAN as UAT surplus destination**, creates one separate **standard Odoo internal picking** from PCK/Stock to selected real T_BAN/Stock, with exactly the **actual residual 6+6+4 (16 pcs)** of component SKUs. Uses PCK's existing internal operation type, confirms and validates with native stock methods, verifies all 16 physical Qty leave PCK (no additional surplus from these MOs remains there) and add to chosen store. Does not create RO, SO, duplicate outgoing DO or assign surplus to Paket. The fact that destination is T_BAN is **a TEST choice only**, not any product business-routing default or automated store assignment. Reuses no fake BoM, never crosses out of TEST DB; explicit `env.cr.rollback()` and postrollback checks store component stock and picking removed. Does not change addons or original Nov27 CDC 10× seed.
- `script/check_package_12114_surplus_internal_transfer_source_ya.py`: static no-database source preflight; checks original seed, real goods native standard internal move and no commit. No module installation/upgrade/restart.

Feri commands:
`cd ~/odoofromzero && git pull && python3 script/check_package_12114_surplus_internal_transfer_source_ya.py && python3 -m py_compile script/test_package_12114_surplus_internal_transfer_rollback_ya.py`
then ONLY if source PASS and GUI test backup:
`sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test --no-http < script/test_package_12114_surplus_internal_transfer_rollback_ya.py`.

Target `NATIVE_PCK_SURPLUS_INTERNAL_TRANSFER_DONE_PASS`, `NATIVE_SURPLUS_QTY_16_AND_PCK_ZERO_LEFTOVERS_PASS`, `ROLLBACK_SURPLUS_PICKING_AND_STORE_STOCK_VERIFIED_PASS`, final `PACKAGE_12114_SURPLUS_INTERNAL_TRANSFER_ROLLBACK_PASS`. Never claim success until Feri actual Odoo runtime output.

## 2026-11-24 — FERI ACTUAL PAKET-ONLY SURPLUS INTERNAL TRANSFER UAT PASS; NEXT JOINT PHYSICAL DO

Feri ran `script/test_package_12114_surplus_internal_transfer_rollback_ya.py` on test DB; actual output `PACKAGE_12114_SURPLUS_INTERNAL_TRANSFER_ROLLBACK_PASS`. All upstream Paket-only UAT still PASS (RO Paket→joint snapshot→10× CDC native opname→2 CDC kitchen transfers→3 native kitchen MO Done→2 FG pickings PCK→1 PCK assembly MO Done→native DO dispatch→transit→T_BAN store receipt). Next one **separate native internal picking from PCK/Stock to explicitly selected T_BAN** in TEST consumed **surplus SKU11999 6, SKU12014 6, SKU12019 4**. Output `UAT_EXPLICIT_SURPLUS_DESTINATION:T_BAN`, `SURPLUS_BY_SKU: {'11999':6.0,'12014':6.0,'12019':4.0}`, `NATIVE_PCK_SURPLUS_INTERNAL_TRANSFER_DONE_PASS`, `NATIVE_SURPLUS_QTY_16_AND_PCK_ZERO_LEFTOVERS_PASS`, `NO_FAKE_SURPLUS_RO_OR_EXTRA_DO_PASS`. All stored UAT data/saldo rolled back: `ROLLBACK_SURPLUS_PICKING_AND_STORE_STOCK_VERIFIED_PASS`, `ROLLBACK_PAKET_PCK_TRANSIT_STORE_VERIFIED_PASS`, `ROLLBACK_FINISHED_STOCK_VERIFIED_PASS`, `ROLLBACK_STOCK_OPNAME_AND_PICKINGS_VERIFIED_PASS`, etc. Explicit T_BAN as surplus destination is a UAT choice, **not** a business rule or default allocation; real operator selects store. No RO or DO invented for surplus. Never retest this just to rebuild evidence.

**Next physical joint UAT prepared in GitHub; Feri has NOT run:**
- `script/test_package_joint_mixed_physical_do_receipt_rollback_ya.py` copies already-passed physical Paket-only native Odoo path, but creates real **Paket RO SKU12114 Qty1 for T_BAN** AND two **ordinary RO SKU11999 on same 2026-11-24 S1**: T_BAN originally Qty2, T_KD originally Qty1. Published Planning for 11999 PST BoM output7 Max7. 3 native kitchen MOs total output 19, Paket priority consumes 1 of 11999, original ordinary RO Qty total3, Hamilton sends remaining 6 of 11999 as **T_BAN Qty4 (original2 + extra2)** and **T_KD Qty2 (original1 + extra1)**. Other two Paket-only components 12014 and 12019 leave **6+4=10 separate internal transfer stock**. Preproduction immutable and original store RO Qty not overwritten. Uses same native CDC10× stock adjustment, CDC→PST/ROTI, MO Done, FG→PCK, PCK final Paket MO Done as previous proven path. Calls inherited `action_ya_generate_store_do()` to make **exactly TWO native outgoing DO, ONE for each store**, with **T_BAN DO containing both final Paket12114 Qty1 AND ordinary11999 Qty4 ON ONE DO**; T_KD DO contains ordinary11999 Qty2. Verifies no duplicate DO on re-click, no physical stock changes merely generating documents, each native dispatch Done→transit→auto receipt created→receipt Done, exact PCK/transit/store quantities; only **10 unallocated parts 12014×6 and 12019×4** left in Packing for standard, separately approved internal transfer (mechanism already proven by preceding test). Then forces rollback and verifies original RO/users/MOs/pickings/raw/FG/PCK/transit/T_BAN/T_KD stock restored. No business addon edits, no fake BoM/Planning or arbitrary surplus store assignment, no direct stock quant mutation except existing native stock opname 10×, no commits or DB upgrade.
- `script/check_joint_paket_ordinary_physical_receipt_source_ya.py` static no-DB gate verifies native actions, exact test DB/slot, real SKU/store, no commit, original Nov27 CDC seed and previously PASS Paket-only script unchanged. Source token alignment checked via GitHub read. Source gate does not prove runtime. **This joint physical test is NOT PASS until Feri sends output**. If UAT fails, patch only test unless true business flaw; never undo accepted Paket-only/ordinary-only functionality.
- Feri: `cd ~/odoofromzero && git pull && python3 script/check_joint_paket_ordinary_physical_receipt_source_ya.py && python3 -m py_compile script/test_package_joint_mixed_physical_do_receipt_rollback_ya.py`; only if source PASS and backup present run `sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test --no-http < script/test_package_joint_mixed_physical_do_receipt_rollback_ya.py`. Expected `JOINT_ONE_NATIVE_DO_PER_STORE_PASS`, `JOINT_SAME_STORE_PAKET_PLUS_ORDINARY_ON_ONE_DO_PASS`, `JOINT_NATIVE_DISPATCH_TRANSIT_RECEIPTS_PASS`, `JOINT_PCK_ONLY_UNALLOCATED_SURPLUS_10_REMAIN_PASS`, `JOINT_DISPATCH_RECEIPT_STOCK_ROLLBACK_PASS`, `JOINT_PAKET_AND_ORDINARY_PHYSICAL_STORE_RECEIPT_ROLLBACK_PASS`.

**Big-picture after potential joint physical PASS**: Still need join SO priority and full multi-brand business rollout, capacity + high-volume operations ~500 SKUs × 10 kitchens, exception UAT, operator usability/role and actual non-rollback operational test. Do not claim live ready based solely on test DB rollback. Working rule Packing no overnight stock requires separate transfer of residual 10 if following joint full-day workflow.

## 2026-11-24 NIGHT — FERI REAL MIXED RO PAKET+ORDINARY THROUGH TWO STORES/DOs AND RECEIPTS: FULL PASS

Feri executed **`script/test_package_joint_mixed_physical_do_receipt_rollback_ya.py`** on **`erp-yussyakmal-mrp-test`**. Actual end marker **`JOINT_PAKET_AND_ORDINARY_PHYSICAL_STORE_RECEIPT_ROLLBACK_PASS`**. Do NOT rerun just for evidence. Details from actual Feri output:

- Published real Planning slot 2026-11-24 S1, final Paket SKU **12114 Hampers EID SET D** Qty1 for T_BAN, two real ordinary RO for kitchen SKU11999: T_BAN originally requests2 and T_KD originally requests1. Preproduction freezes a **single joint batch**, `JOINT_PACKAGE_FIRST_AND_ORDINARY_PRORATA_PASS`, allocation: T_BAN `(requested2, surplus2, shortage0, allocated4)`, T_KD `(requested1, surplus1, shortage0, allocated2)`. One SKU11999 is *protected for Paket*. Ordinary RO original quantities unchanged.
- 10 unique CDC raw SKUs stocked with existing Odoo native 10× inventory-adjustment pattern **only inside rollback**; 2 CDC→kitchen Done pickings; 17 own-MO reservations. Native 3 kitchen MOs Done: 11999 PST7 (6 raw moves), 12019 PST5 (6 raw moves), 12014 ROTI7 (10 raw moves). All raw consumption/FG stock correct. 2 native FG kitchen→PCK Done pickings and double-click idempotence PASS.
- ONE native PCK Paket assembly MO for SKU12114 Qty1 BoM1405, PCK type279 stock location20; components3, Confirmed→Done, actual 1 final Paket produced. `PCK_COMPONENT_OUTPUT_AFTER_ASSEMBLY:16.0` includes 6 ordinary-RO-allocated SKU11999 units and 10 unallocated SKU12014/SKU12019 units.
- **Exactly ONE native dispatch DO PER STORE**; `JOINT_ONE_NATIVE_DO_PER_STORE_PASS`, `JOINT_SAME_STORE_PAKET_PLUS_ORDINARY_ON_ONE_DO_PASS`, `JOINT_DO_QTY_PAKET_PRIORITY_AND_PRORATA_PASS`, `JOINT_DO_DOUBLE_CLICK_NO_DUPLICATES_PASS`.
- **T_BAN single DO and native physical transit receipt Done: `{'12114':1.0,'11999':4.0}`**; **T_KD separate native DO and receipt Done: `{'11999':2.0}`**. Exact stocked store increments and transit clearing PASS, no 11999 in PCK except other preexisting baseline (6 consumed by ordinary DO), `JOINT_PCK_ONLY_UNALLOCATED_SURPLUS_10_REMAIN_PASS`. No fake RO and frozen source Qty unchanged.
- `ROLLBACK_EXPECTED_OK`, `JOINT_DISPATCH_RECEIPT_STOCK_ROLLBACK_PASS`, `ROLLBACK_FINISHED_STOCK_VERIFIED_PASS`, `ROLLBACK_ROLE_USERS_NOT_PERSISTED_PASS`, `ROLLBACK_STOCK_OPNAME_AND_PICKINGS_VERIFIED_PASS`, `ROLLBACK_NO_RO_BATCH_MO_PERSISTED_PASS`. No temporary source RO, MOs, DO, receipts, users, or inventory committed. **DO not say LIVE approved**; this was a rollback-only test DB trial.

**Remaining logistics from THIS joint slot:** 10 units unallocated at Packing: SKU12014=6, SKU12019=4. The native separate internal picking method already passed for the Paket-only case 16 units. Next close this exact joint case with separate native transfer of 10, without inventing store RO or silently appending to either DO.

**New GitHub test-only UAT prepared but NOT run by Feri:**
- `script/test_package_joint_mixed_surplus_final_rollback_ya.py` copies the just-PASS mixed real full physical RO+Paket→two store DO/receipts rollback case and appends ONE separate native **PCK/Stock→T_KD/Stock** internal picking for only actually recorded 6+4 residual finished component units. The T_KD destination is an **explicit UAT-only selection** (to prove independent selection from Paket destination T_BAN), NOT business default or inferred from store ordinary RO. It verifies raw physical and reservations before transfer, native action_confirm/button_validate moves Done, store increments, zero incremental residual PCK stock for these two SKUs, no additional RO/DO, and full rollback of picking and T_KD product quants and all earlier stock flows. Uses only actual master, no add-on changes and never commits.
- `script/check_joint_paket_ordinary_surplus_final_source_ya.py` static Python ast/required marker guard; aligned to new script via GitHub source check; **does NOT prove actual Odoo test PASS**. No module upgrade/install/restart.
- Feri next: `cd ~/odoofromzero && git pull && python3 script/check_joint_paket_ordinary_surplus_final_source_ya.py && python3 -m py_compile script/test_package_joint_mixed_surplus_final_rollback_ya.py`. If source PASS and existing test backup verified: `sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test --no-http < script/test_package_joint_mixed_surplus_final_rollback_ya.py`. Target `JOINT_SURPLUS_NATIVE_INTERNAL_TRANSFER_DONE_PASS`, `JOINT_PCK_NO_SURPLUS_FROM_THIS_BATCH_PASS`, `JOINT_SURPLUS_PICKING_AND_STORE_ROLLBACK_PASS`, and **`JOINT_PAKET_ORDINARY_FULL_SURPLUS_CLEARED_ROLLBACK_PASS`**. Send any traceback, do not change real master to make UAT pass.

**Big picture:** RO ordinary only native handoff already separately PASS; Paket-only E2E and 16 surplus internal transfer PASS; joint Paket+ordinary physical 2 store DO/receipts PASS. Critical yet untested: priority of **SO over store RO** when added, 500×10 high-volume/operator readiness, exceptional shortages/zero-dispatch, roles/security and adoption in durable operational environment. Avoid overstating system-wide readiness. Product SOP Packing **no overnight stock** remains, and residual joint 10 transfer is the pending proof.

## 2026-11-24 — FERI FINAL JOINT SURPLUS ROLLBACK ACTUAL PASS (ALL CORE RO→STORE PATH COMPLETE ON TEST)

Feri's actual Odoo shell output for `script/test_package_joint_mixed_surplus_final_rollback_ya.py` in ONLY `erp-yussyakmal-mrp-test` ended **`JOINT_PAKET_ORDINARY_FULL_SURPLUS_CLEARED_ROLLBACK_PASS`**. This completes the previously remaining joint-slot 10-unit PCK surplus trial, with no further rerun of the same happy path needed.

**Preserve the full flow, not just this last checkpoint:** One real 2026-11-24/S1 combined Pre Produksi from confirmed **Paket RO12114 Qty1 → T_BAN** and **ordinary RO11999 original Qty2 → T_BAN and Qty1 → T_KD**, using native real Published Planning/BoMs, first protecting 1 of kitchen SKU11999 for Paket, then assigning BoM-rounded 6 other pieces to ordinary RO through original Hamilton prorata `{23:(2,2,0,4),24:(1,1,0,2)}` while retaining original RO demand. Actual 3 kitchen MOs Done (11999 PST7, 12019 PST5, 12014 ROTI7), same original guarded standard CDC 10× stock adjustment for 10 raw SKUs, 2 CDC→kitchen transfers (17 native reservations), 2 kitchen→PCK finished pickings Done, native PCK Paket BoM1405 assembly MO Confirmed→Done, consuming 3 real produced pieces to create SKU12114 Qty1. One native DO/Transit/Receipt **per store**: **T_BAN one DO containing SKU12114 Qty1 + ordinary SKU11999 Qty4; T_KD one DO containing SKU11999 Qty2**. 2 native dispatches and 2 native store receipts Done, no duplicate DO, no fake RO. Before surplus transfer `JOINT_PCK_ONLY_UNALLOCATED_SURPLUS_10_REMAIN_PASS`.

**NEW successful final stock closure:** `JOINT_UAT_EXPLICIT_SURPLUS_DESTINATION: T_KD`; `JOINT_SURPLUS_BY_SKU: {'12014':6.0,'12019':4.0}`; `JOINT_SURPLUS_NATIVE_INTERNAL_TRANSFER_DONE_PASS`; `JOINT_PCK_NO_SURPLUS_FROM_THIS_BATCH_PASS`; `JOINT_NO_FAKE_SURPLUS_RO_OR_EXTRA_DO_PASS`. These 10 finished units were transferred with a **separate native internal PCK/Stock→T_KD/Stock picking** after the 2 DO/receipts. **T_KD is an explicit TEST selection, not a default, auto-allocation, or instruction to send real surplus there.** The test proved zero *incremental* PCK residual from this batch, NOT zero absolute stock if the test DB already contained preexisting inventory.

**Postflight rollback was verified by actual stdout:** `ROLLBACK_EXPECTED_OK`, `JOINT_SURPLUS_PICKING_AND_STORE_ROLLBACK_PASS`, `JOINT_DISPATCH_RECEIPT_STOCK_ROLLBACK_PASS`, `ROLLBACK_FINISHED_STOCK_VERIFIED_PASS`, `ROLLBACK_ROLE_USERS_NOT_PERSISTED_PASS`, `ROLLBACK_STOCK_OPNAME_AND_PICKINGS_VERIFIED_PASS`, `ROLLBACK_NO_RO_BATCH_MO_PERSISTED_PASS`. Test DB transaction was rolled back including all stocks, documents, temporary users and native pickings. No system/module code upgrade, no production DB writes.

**Checkpoint decision:** **RO biasa only, Paket-only through store receipt and 16 surplus, mixed Paket+ordinary through 2 DO/receipts and 10 surplus are separately PASS** on dedicated TEST with rollback. Do not treat this as a live go-live signoff, scalability proof or proof that any shop destination should be chosen automatically.

**Next priorities, not yet PASS or implemented as part of this test:**
1. **Exception/fail-closed UAT** using actual Odoo guards: missing raw material, shortage and native MO Done prevention, negative/over-shipped DO Qty, Qty0 requires operator reason, insufficient PCK/transit stock, out-of-order receipt, duplicate-click/race and incorrect user roles. `script/test_negative_stock_move_rollback_ya.py` already exists, but it is explicitly **a raw stock.move probe, not native MO Done**; don't claim it proves MO or DO negative-stock enforcement. Audit the full native MO/DO context and keep all UAT rollback-only on TEST. `script/audit_package_exceptions_and_slot_readonly_ya.py` exists for read-only BoM/slot coverage.
2. **Scale / operator UX** with realistic 500 SKU × 10 kitchen throughput and only necessary operator actions, latency/locks and concurrency, especially RO upload button and bulk transfers, before live.
3. **SO integration into frozen planning**: preserve owner SOP priority **SO → Paket protected components → ordinary store RO → surplus**, exact business decision rights for exceptions; SO is NOT yet covered by proven joint E2E.
4. **Deployment governance**: functional permissions, visible UI, backups and recovery, no stock overnight in PCK, rollback vs durable test transactions, immutable RO snapshot, production sign-off and never touch `erp-yussyakmal` without an explicitly authorized change plan.

**No re-creation of legacy 10x inventory-adjustment tool**; use proven stock.quant inventory adjustment methods strictly in rollback-only UAT, original `script/dev_seed_cdc_material_10x_ya.py` has a separate Nov27 S1 target and applies stock permanently if explicitly invoked in APPLY mode. The checkpoint log is cumulative; always read prior sections before planning new tests. New scripts should be narrowly scoped to an *unproven* risk rather than repeating already-passed happy path.

## 2026-11-24 — OWNER CHALLENGE: NO REBUILDING STANDARD MRP; SCOPE NEGATIVE STOCK GUARD

User correctly challenged the temptation to re-test already-proven native manufacturing MO for every corner case. All original+Paket RO, manufacturing and routing E2E on TEST are still PASS, including the latest joint 10-surplus cleanout. The next smallest useful check is **whether Community already has an effective negative-stock guard**, NOT new custom MO state logic. Key Odoo 19 core inspection: `mrp.production.action_confirm()` does NOT require all raw inventory reserved; it confirms planned native stock moves and advances MO to `confirmed`. `components_availability` indicates available/not available. `pre_button_mark_done()` validates consumed-vs-required and may show a wizard, but Odoo core `stock.move.line._action_done()` calls `stock.quant._update_available_quantity()` and does not universally reject physically negative quantities. User's Enterprise screenshot showed confirmed MO `CKS/MO/00003` with `Component Status: Not Available` and **Produce All** raising `You need 1.0 more Premik Chiffon Spesial(s) to complete this Transfer!`. The EXACT phrasing is also shown as an example of custom negative-quantity prevention in public Odoo forum thread `https://www.odoo.com/forum/help-1/how-to-prevent-negative-stock-in-odoo18-272531`; screenshot alone cannot establish Enterprise core functionality vs installed addon/Studio/custom server action. Do not conflate Enterprise edition with guaranteed no-negative stock.

Current OCA 19.0 `stock_no_negative` from `https://github.com/OCA/stock-logistics-workflow/tree/19.0/stock_no_negative` is v **19.0.1.0.1** (as checked from real source) and depends only on `stock`; it disallows negative internal/transit stock quants for storable products unless explicit allow-negative flag set on product/category/location. OCA code raises a ValidationError on negative stock quant; it covers native MRP actual consumption without rewriting `mrp.production` or blocking MO Confirm. Module mature label Beta and AGPL-3; evaluate addon deployment/metadata/exception policies on TEST before installing. Odoo 19 official docs confirm standard stock negative behavior is possible.

**NEW SOURCE-ONLY GitHub change, Feri has not run audit or approved install:** `script/audit_negative_stock_guard_readonly_ya.py` does exactly one **TEST DB, read-only** Odoo shell audit, records `ir.module.module` state/version for stock_no_negative and other named negative-stock addons, `stock.quant.check_negative_qty` method, existence and read-only values of `allow_negative_stock` product/category/location field for real CDC/PST/ROTI/PCK and example SKUs 11999,12014,12019,12114, any existing negative storable quant count in internal/transit and up to 15 examples, and returns `READ_ONLY_NEGATIVE_STOCK_GUARD_AUDIT_OK`. NO create/write/stock adjustment/MO/DO/commit. This audit does NOT prove all custom server action guards or that missing stock_no_negative means absolutely no guard; it is a first targeted OCA readiness check. Do not install, upgrade or restart anything yet.

Feri:
`cd ~/odoofromzero && git pull && python3 -m py_compile script/audit_negative_stock_guard_readonly_ya.py`
`sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test --no-http < script/audit_negative_stock_guard_readonly_ya.py`
Request output sections: OCA_STOCK_NO_NEGATIVE_REGISTRY, INSTALLED_VERSION, REGISTRY_FLAGS, WAREHOUSE_NEGATIVE_POLICY, SKU_NEGATIVE_POLICY, EXISTING_NEGATIVE_INTERNAL_TRANSIT_QUANT_COUNT, GUARD_READINESS, final marker. Use output to decide whether existing guard already meets owner rule `stok tidak boleh minus` or install OCA on TEST with a deliberate backup/approval. Avoid a big new native MO UAT; focus next on volume/operator 500SKU×10 kitchens and SO priorities after this gate.

## 2026-11-24 — FERI READ-ONLY NEGATIVE STOCK AUDIT ACTUAL OUTPUT; DON'T INSTALL OCA YET

Feri ran `script/audit_negative_stock_guard_readonly_ya.py` on `erp-yussyakmal-mrp-test`; received final `READ_ONLY_NEGATIVE_STOCK_GUARD_AUDIT_OK`. **Actual** registry: `OCA_STOCK_NO_NEGATIVE_REGISTRY:NOT_IN_MODULE_REGISTRY`, `NEGATIVE_STOCK_CANDIDATE_MODULES:[]`, `NEGATIVE_STOCK_REGISTRY_FLAGS: product False category False location False quant_validator False`. This demonstrates the named OCA `stock_no_negative` isn't installed and its model extensions/checks are absent; **does not prove there are no unrelated server-level custom protections**. Four checked warehouses CDC/PST/ROTI/PCK have normal internal locations and lack OCA allow-negative field. Four example product master SKUs11999,12014,12019,12114 are `type:consu` in Odoo19 but `is_storable:True`; OCA code keys on `is_storable`, hence the tracked finished goods would be protected, not excluded as old-style consumables.

**IMPORTANT actual data quality finding**: `EXISTING_NEGATIVE_INTERNAL_TRANSIT_QUANT_COUNT:17` distinct negative stock.quant entries on TEST. The first 15 **displayed** examples are all `SUL/Stock`, e.g. SKU10357 -1000, 10833 -100, 10835 -150, 10837 -50, 10262 -20, 10424 -100, 10840 -40, 10235 -5, 10237 -2, 10164 -800, 10252 -5, 10853 -600, 10364 -200, 11292 -1, 10626 -40. The first audit capped examples at **15**, so do NOT assert ALL 17 are at SUL until verified! No evidence that these originate in currently run rollback tests; these are preexisting *current TEST DB* records of unknown origin. Don't auto-set them to 0, import fake inventory, or adjust product masters to clear an alert.

**New small GitHub read-only next check `script/audit_existing_negative_quants_by_location_readonly_ya.py`**: enumerates **all** negative internal/transit storable quants with exact location, SKU/UoM/category/Qty/reservation and latest up-to-3 actual Done stock move lines touching each exact location; includes SUL warehouse metadata and count-by-location. No writes/MO actions/stock transfers, should be run only on TEST. This is not an inventory recount, not a determination of true physical stock, and recent moves do not prove the reason for the discrepancy. Audit before deciding how to correct legitimate historical negatives and deploy OCA module. If findings are legacy test debris and store is not used, still require owner/stock-control review—do NOT hide with `allow_negative_stock`.

**OCA 19 source verified directly from GitHub 19.0:** `OCA/stock-logistics-workflow/stock_no_negative` manifest version `19.0.1.0.1`, depends on `stock`, installable True, license AGPL-3; stock.quant `@api.constrains('product_id','quantity')` raises ValidationError if negative storable quant in internal/transit and product/category/location flags do not allow it. Existing negative quants might not be rejected merely by installing because the constraint triggers on writes; however later changes to existing negatives can fail. Reconcile physical counts and evaluate/test install separately after audit. This is not a request/approval to install or upgrade any addon and nothing should touch PROD.

Feri run once:
`cd ~/odoofromzero && git pull && python3 -m py_compile script/audit_existing_negative_quants_by_location_readonly_ya.py`
then:
`sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test --no-http < script/audit_existing_negative_quants_by_location_readonly_ya.py`
Expected `READ_ONLY_NEGATIVE_QUANTS_LOCATIONS_DETAIL_OK`. Reuse original Odoo happy-path native MOs; do not undertake repetitive MO test suite just because stock guard is absent.

## 2026-11-24 — OWNER IDENTIFIES SUL/Stock NEGATIVE QUANT ORIGIN: MANUAL CONFIRM/PRODUCE ALL TEST

**New user clarification:** The **15 displayed negative SUL/Stock stock.quant examples** from `audit_negative_stock_guard_readonly_ya.py` resulted from the user's **manual Confirm and Produce All test**; do not present them as mystery operational discrepancies or presume a warehouse handling incident. This information comes directly from the owner. The audit actually reported **17 negative quant records total**, but displayed only the FIRST 15; do not extrapolate the provenance of the two not displayed without evidence. The user has highlighted that Odoo Enterprise UI on an earlier MO had blocked Produce All on missing BB with a specific Invalid Operation error, but the Community test had no registered OCA `stock_no_negative` guard and user tests generated persistent negative SUL stock. These results reinforce the choice to use a known stock-negative protection addon in test rather than rewriting native manufacturing workflows.

**Operational decision:** Avoid forcing the detailed move-history audit as a prerequisite merely to rediscover the origin of the 15 acknowledged test-created SUL negatives. No need to rerun native MO happy paths. Prior to enabling OCA guard in TEST, note existing negatives can remain and may make some subsequent validations fail; restore a known-clean dedicated test DB snapshot (if available and authorized), or reconcile specific test-generated quants with approved standard Odoo inventory adjustment after recording original quantities. Never automatically zero all 17, fake stock, hide them with `allow_negative_stock=True`, or touch PROD. OCA installation remains NOT authorized by the user in this clarification; explain proposed TEST-only steps and get explicit approval before making installation / persistent stock changes. Priority after guard: 500 SKU × 10 dapur throughput and ergonomics, rather than broad retesting.

## 2026-11-24 22:27 WIB — OWNER AUTHORIZED NATIVE TEST-DB OPNAME EXACTLY 15 SUL TEST QUANTS

User explicitly: **"15 itu kamu opname aja"** referring to the 15 NEGATIVE SUL/Stock SKU examples they acknowledged came from manual test Confirm/Produce All. Authorized desired count **0** for just those 15 test balances; NOT permission to adjust all other two negatives, any real stock warehouse, or PROD. We cannot directly reach Feri's Odoo host, so authored ready-to-run Github `script/opname_15_sul_test_produce_all_ya.py`.

Script frozen map from actual earlier Odoo audit: 10357:-1000, 10833:-100, 10835:-150, 10837:-50, 10262:-20, 10424:-100, 10840:-40, 10235:-5, 10237:-2, 10164:-800, 10252:-5, 10853:-600, 10364:-200, 11292:-1, 10626:-40 (15). Only existing unique untracked/storable `stock.quant` in unique `SUL/Stock` and matching company, no lot/package/owner/reservation, each current Qty must equal the *exact observed old negative qty*, with preflight outside DB updates. For each uses **native inventory adjustment** `with_context(inventory_mode=True).write({'inventory_quantity':0.0}); quant.action_apply_inventory()`, then actual stock at root verified zero. Verifies all other preexisting internal/transit negative quant IDs/snapshot are unchanged and no new ones arise; **atomic commit ONLY** when exact env `YA_SUL_15_OPNAME_APPLY=YES_TEST_ONLY_15_ZERO` provided. Default mode is DRY-RUN and rolls back; APPLY rollback on any mismatch, no partial intended changes. Never direct `stock.quant.quantity` edits or fake transfers; standard adjustment posts legitimate inventory stock moves and may alter valuation in TEST, so Feri must verify fresh TEST backup before APPLY.

Feri commands, no repeat follow-up investigation:
`cd ~/odoofromzero && git pull && python3 -m py_compile script/opname_15_sul_test_produce_all_ya.py`
`sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test --no-http < script/opname_15_sul_test_produce_all_ya.py`
Expected dry `PREVIEW_ONLY_15_SUL_OPNAME_OK`; review 15 plans; backup; then:
`sudo -u odoo19 env YA_SUL_15_OPNAME_APPLY=YES_TEST_ONLY_15_ZERO /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test --no-http < script/opname_15_sul_test_produce_all_ya.py`
Expected `OPNAME_15_ALL_VERIFIED_BEFORE_COMMIT`, `OPNAME_15_SUL_TEST_COMMITTED_PASS`. **NOT RUN by Feri yet.** If mismatched quantities or remaining 2 negative changed, stop; never broaden target automatically. Afterwards reassess remaining 2 and decide OCA `stock_no_negative` installation in TEST, no MO custom.

## 2026-11-24 ~22:27 WIB — FERI EXECUTED OWNER-APPROVED SUL 15 NEGATIVE TEST QUANT NATIVE OPNAME, COMMITTED PASS

**Actual Feri Odoo-shell output** of `script/opname_15_sul_test_produce_all_ya.py` in `erp-yussyakmal-mrp-test`:
`MODE:NATIVE_OPNAME_APPLY_15_TEST_ONLY`, `WAREHOUSE:SUL SUL/Stock`, `SKU_COUNT:15`, `NEGATIVE_QUANTS_BEFORE:17`, `EXACT_MATCHED_SUL_NEGATIVE_SKUS:15`, `OTHER_NEGATIVE_QUANTS_UNTOUCHED:2`. Every one of the 15 owner-identified historical manual Confirm/Produce All test-created negative SKU balances exactly matched original quantities, including units of Gram, Pcs, Lembar, Ikat. All 15 `OPNAME_POSTED` messages showed BEFORE negative -> AFTER 0.0. `OPNAME_15_ALL_VERIFIED_BEFORE_COMMIT`, `UNRELATED_NEGATIVE_QUANTS_UNCHANGED:2`, **`OPNAME_15_SUL_TEST_COMMITTED_PASS`**. Native Odoo Inventory Adjustment posted **permanently in test DB** (unlike earlier rollback UAT), not to PROD. Do not rerun APPLY, because the script deliberately refuses quantities not equal to the original negatives.

**Precisely two negative quants remain unmodified** in TEST, outside the approved 15; their location/SKUs were not exposed in the original 15-example audit nor the APPLY output. Do not claim zero negatives globally. Source-only read-only `script/audit_existing_negative_quants_by_location_readonly_ya.py` exists to identify them if desired; do not auto-zero them or assume their provenance. OCA `stock_no_negative` still **NOT INSTALLED** per last audit before the opname; no new module installation is shown in this output. Owner agreed to native stock protections, but the user instruction for this turn specifically authorized these 15 opname adjustments, not installation of arbitrary addons. Next substantive task: confirm the exact two remaining negative SKUs + evaluate test-only OCA installation plan/backup/compatibility and whether existing negatives need controlled reconciliation, then proceed only with deliberate scope, avoid all repeated MO happy-path testing. Continue to prioritize operational throughput ~500 SKUs×10 kitchens, and don't tamper with original MO native business flow.

## 2026-11-24 FOLLOW-UP — FIRST CHECK REMAINING TWO NEGATIVE QUANTS + OCA ADDON PATH, NO INSTALL YET

The 15 user-authorized SUL negative test quants have already been atomically inventory-adjusted to 0 and committed in TEST by Feri (`OPNAME_15_SUL_TEST_COMMITTED_PASS`). **DO NOT rerun the 15 APPLY.** Exactly 2 other internal/transit storable negative `stock.quant` entries remained unchanged at that point, without grounded SKU/location; never assume their cause or zero them without new evidence/authorization.

Instead of creating redundant diagnostics, updated the **already existing** `script/audit_existing_negative_quants_by_location_readonly_ya.py` (GitHub commit `74e6451767c19893100670222c6c995b484fa611`). It still enumerates every remaining negative with location, SKU/UoM/qty and latest 3 Done stock move lines and NO writes; it now additionally inspects Odoo configured `addons_path`, checks whether `stock_no_negative/__manifest__.py` physically exists under a configured addons directory, checks `ir.module.module` registry status, and reports whether remaining negatives still count 2. Expected `READ_ONLY_NEGATIVE_QUANTS_LOCATIONS_DETAIL_OK`. This is READ-ONLY, for TEST DB only, not module installation, not inventory correction.

Feri command:
`cd ~/odoofromzero && git pull && python3 -m py_compile script/audit_existing_negative_quants_by_location_readonly_ya.py`
`sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test --no-http < script/audit_existing_negative_quants_by_location_readonly_ya.py`

After inspecting output, choose a configured custom addons path for OCA 19.0 `stock_no_negative` source (`OCA/stock-logistics-workflow`), backup TEST, and stage installation **ONLY in TEST** with explicit approval and a measured impact plan (existing negative quants and data reconciliation, exclusions defaults OFF, backup/restore, regression smoke test). Do not touch PROD or rewrite MO core. Avoid repeated deep happy-path manufacturing UAT.

## 2026-11-24 EVENING — REMAINING 2 SUL NEGATIVES IDENTIFIED AS SAME TEST MO, OWNER EXPLAINS ORIGIN

Feri ran latest `script/audit_existing_negative_quants_by_location_readonly_ya.py` (commit `74e6451767c19893100670222c6c995b484fa611`) on dedicated TEST. Actual `READ_ONLY_NEGATIVE_QUANTS_LOCATIONS_DETAIL_OK`, exactly 2 stockable negative internal quants remain in **SUL/Stock**:
- **Quant 1020, SKU10662, `[10662] Premik Arem Sayur`, category `All / Premix`, -1 Bungkus, reserved 0**, native posted `SUL/MO/00001`, 2026-11-24 14:40:50, from SUL/Stock → Production, 1 Bungkus.
- **Quant 1019, SKU11436, `[11436] Plastik Sheet Bening YussyAkmal2 22x30`, category `All / Packaging`, -10 Pcs, reserved 0**, native posted `SUL/MO/00001`, 2026-11-24 14:40:50, from SUL/Stock → Production, 10 Pcs.

**User explicitly clarified both are from the same manual Confirm / Produce All TEST transaction** as the 15 earlier corrected SUL negative quants; no need to investigate these as unexplained warehouse problems. One is premix, the other a **packaging item** (not both premix). No other negatives in TEST per this audit.

Odoo `addons_path` from Feri's real server: `/opt/odoo19/odoo/addons`, `/opt/odoo19/oca-addons/account-financial-tools`, `/opt/odoo19/oca-addons/account-financial-reporting`, `/opt/odoo19/oca-addons/account-reconcile`, `/opt/odoo19/oca-addons/account-invoicing`, `/opt/odoo19/oca-addons/reporting-engine`, `/opt/odoo19/oca-addons/server-ux`, `/opt/odoo19/custom-addons`. `OCA_STOCK_NO_NEGATIVE_FILESYSTEM_PATHS: []`, `OCA_STOCK_NO_NEGATIVE_REGISTRY_STATE:NOT_IN_REGISTRY`. No OCA negative stock guard installed; stock negative enforcement remains needed, without rewriting native Odoo MO.

**Next new script GitHub `script/opname_2_sul_same_mo_produce_all_ya.py`** created commit `b4b57487236233bbf9d41353263af32e732de5f6`, reused already genuinely PASS original 15-SKU native adjustment pattern. Targets exactly root SUL/Stock SKU10662 old -1 Bungkus and SKU11436 old -10 Pcs, final target 0 each. Same dedicated TEST db guard; checks exact location/company/lot/package/owner/no reserved/master/UoM and old Qty, readonly preview by default (rollback), explicit env token `YA_SUL_2_OPNAME_APPLY=YES_TEST_ONLY_2_ZERO` for permanently committing only after backup. Compares all other existing negatives before/after to prevent unauthorized changes. No edits to MO, BoM, production planning, packages, other stock or PROD. **NOT YET RUN BY FERI.**

Feri:
`cd ~/odoofromzero && git pull && python3 -m py_compile script/opname_2_sul_same_mo_produce_all_ya.py`
Preview:
`sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test --no-http < script/opname_2_sul_same_mo_produce_all_ya.py`
Target `PREVIEW_ONLY_2_SUL_OPNAME_OK`. If exact balances match and current TEST backup is confirmed, APPLY:
`sudo -u odoo19 env YA_SUL_2_OPNAME_APPLY=YES_TEST_ONLY_2_ZERO /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test --no-http < script/opname_2_sul_same_mo_produce_all_ya.py`
Target `OPNAME_2_SUL_TEST_COMMITTED_PASS`. After successful application, recheck OCA guard; stage OCA 19.0 from verified GitHub `OCA/stock-logistics-workflow/19.0/stock_no_negative` in existing `/opt/odoo19/custom-addons` (not an arbitrary new addons_path) and install **TEST ONLY** with backed-up DB and service-impact caution (running shared Odoo service restart must NOT be done absent prod safety plan). Do not claim OCA installed until Feri demonstrates. Don't rerun 15-SKU APPLY.

## 2026-11-24 — FERI CONFIRMED LAST 2 SUL TEST NEGATIVES OPNAMED TO ZERO, FULL 17 CLEARED; PREPARE OCA GUARD

**Latest ACTUAL Feri Odoo-shell output** on `erp-yussyakmal-mrp-test` using `script/opname_2_sul_same_mo_produce_all_ya.py` **APPLY**:
`MODE:NATIVE_OPNAME_APPLY_2_TEST_ONLY`, `NEGATIVE_QUANTS_BEFORE:2`, `EXACT_MATCHED_SUL_NEGATIVE_SKUS:2`, `OTHER_NEGATIVE_QUANTS_UNTOUCHED:0`. SKU10662 **Premik Arem Sayur** corrected -1 Bungkus→0; SKU11436 **Plastik Sheet Bening YussyAkmal2 22x30** corrected -10 Pcs→0, from manual SUL/MO/00001 test. Both native Odoo inventory adjustments were posted and **permanently committed to TEST**. End markers `OPNAME_2_ALL_VERIFIED_BEFORE_COMMIT`, `UNRELATED_NEGATIVE_QUANTS_UNCHANGED:0`, **`OPNAME_2_SUL_TEST_COMMITTED_PASS`**. The 15 other originally identified SUL test negatives were already separately committed to zero. Thus total 17 negative internal/transit storable quant entries from these tests now cleared as of the verified commit time (unless newer unrelated transactions). NO further opname of these 17 should be rerun or attempted. No production DB changes.

**Upstream source verified:** OCA 19.0 stock_no_negative addon `19.0.1.0.1` has only `stock` dependency, live upstream commit `e7f9ad50bf698fc7c4c06d2500e3d8c4f124c4a1` (branch 19.0 as of 2026-11-24). OCA stock.quant check blocks negative internal/transit storable quant unless allow-negative exception on product/category/location; doesn't rewrite core MO. Not yet installed in any DB according to last Feri audit.

**NEW GITHUB STAGED CODE / NO FERI EXECUTION YET:**
- `script/check_oca_stock_no_negative_install_ready_readonly_ya.py`: TEST-only, read-only, confirms SUL corrected SKU10662/11436 zero, all internal/transit storable negative quants zero, exactly ONE OCA addon folder under configured addons_path, expected 19.0.1.0.1 manifest and required package files/source, module registry not in installed/transitional state. Expected `OCA_STOCK_NO_NEGATIVE_TEST_INSTALL_READINESS_PASS`.
- `script/test_oca_stock_no_negative_guard_rollback_ya.py`: after TEST installation, minimal ONE standard untracked SKU10662 native stock.move from zero SUL to virtual Production, demand 1 Bungkus, expects OCA ValidationError and all transactions explicit rollback. Expected `OCA_STOCK_NO_NEGATIVE_GUARD_ROLLBACK_PASS`. DOES NOT claim MO new behavior beyond native quant-level enforcement, does NOT touch PROD.
- **`doc/INSTALL_OCA_STOCK_NO_NEGATIVE_19_TEST_ONLY_2026-11-24.md`**: exact safe Stage A OCA source-only pinned checkout (commit `e7f9ad50...` clone in unconfigured `/opt/odoo19/oca-addons/stock-logistics-workflow`, symlink only the addon to ALREADY CONFIGURED `/opt/odoo19/custom-addons/stock_no_negative`), Stage B read-only gate, Stage C one-off `odoo-bin -d erp-yussyakmal-mrp-test -i stock_no_negative --stop-after-init --no-http --workers=0` ONLY when test DB/filestore backup verified and safe impact assessment, Stage D minimal rollback guard verification. DO NOT blindly restart shared Odoo service; it may serve PROD `erp-yussyakmal`. No alterations to `/etc/odoo19.conf` required. Source staging and one-off TEST module installation are different phases; no installed module until proven by Feri.

**Next to Feri:** `cd ~/odoofromzero && git pull`, perform Stage A source staging from the above runbook, Stage B read-only source+clean-stock preflight, then send outputs before install if there is any exception. Staged source is not an Odoo addon installation. If all staged PASS and backup/service impact reviewed, progress to deliberate TEST-only installation; never touch PROD modules or shared service restart blindly. This guard is a small final stock safety requirement; then shift to volume 500 SKUs ×10 kitchens, operator efficiency, and SO integration without redoing already native PASS flows.

## 2026-11-25 03:37 WIB — FERI ACTUAL OCA STOCK_NO_NEGATIVE READ-ONLY INSTALL GATE PASS

Feri executed `script/check_oca_stock_no_negative_install_ready_readonly_ya.py` on **`erp-yussyakmal-mrp-test`** after source-only OCA 19.0 staging. Exact actual terminal results:
- `MODE:READ_ONLY_OCA_NEGATIVE_GUARD_INSTALL_GATE`;
- `PREVIOUS_TEST_NEGATIVE_SKU_NOW_ZERO:10662 stock 0 Bungkus`, `11436 stock 0 Pcs`;
- `PRESENT_NEGATIVE_INTERNAL_TRANSIT_QUANT_SAMPLE_COUNT:0` (gate asserts no negative stockable internal/transit quants in the scanned query);
- 8 configured addons directories, with configured `/opt/odoo19/custom-addons`;
- `OCA_MANIFEST_SOURCE:/opt/odoo19/custom-addons/stock_no_negative/__manifest__.py`, `OCA_MODULE_VERSION:19.0.1.0.1`, `OCA_LICENSE:AGPL-3`;
- `OCA_REGISTRY_STATE:NOT_DISCOVERED_BEFORE_APPS_UPDATE`;
- `OCA_STOCK_NO_NEGATIVE_TEST_INSTALL_READINESS_PASS`, `NO_DB_WRITES_NO_INSTALL_NO_RESTART`.

**IMPORTANT: source staging is DONE, but OCA is NOT INSTALLED yet.** Do not ask Feri to clone/symlink again. Also do not rerun any of the 17 SUL inventory adjustment APPLY scripts: both were already permanently committed in TEST. The immediate next step is verifying a recent restorable TEST DB + filestore backup and low-impact execution strategy, and then (with operator's verified backup) ONE one-off Odoo install command targeting only `erp-yussyakmal-mrp-test`:
`sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test -i stock_no_negative --stop-after-init --no-http --workers=0`.
No shared systemctl restart or -u all; no PROD install/upgrade, no MO custom code. The Odoo CLI may load a TEST registry independently of already-running service; if production and test share a server, consider concurrent resource/lock load and don't blindly restart live service.

After actual `stock_no_negative` install is confirmed in TEST, use `script/test_oca_stock_no_negative_guard_rollback_ya.py` (already committed) as ONE narrow smoke check: expect `OCA_STOCK_NO_NEGATIVE_GUARD_ROLLBACK_PASS` and full rollback with physical 0 SUL premix. If error, collect full output and fix safely without modifying native MO business rules. Avoid unnecessary retesting already completed multi-stage manufacturing.
