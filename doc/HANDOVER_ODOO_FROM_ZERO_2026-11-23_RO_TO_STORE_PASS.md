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
