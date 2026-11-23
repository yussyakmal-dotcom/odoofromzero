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
