# HANDOVER AKTIF — ODOO FROM ZERO / FASE 2 RO + SO / TIGA KONSOLIDASI

**Tanggal:** 2026-Nov-25 (Asia/Jakarta)  
**Status saat serah terima:** **DOCUMENTATION FREEZE** — pure rules & Sales Admin impact tests PASS; read-only clone audits PASS; **operator E2E SO→MO2→Packing/DO NOT YET PASS**.  
**Repository:** `yussyakmal-dotcom/odoofromzero`, branch `main`.  
**DB satu-satunya yang boleh dipakai untuk UAT Fase 2:** `erp-yussyakmal-mrp-test-RO_SO`.  
**Checkpoint keputusan ringkas:** [CHECKPOINT_2026-11-25_FASE2_TIGA_KONSOLIDASI_SO_FIRST_FREEZE.md](CHECKPOINT_2026-11-25_FASE2_TIGA_KONSOLIDASI_SO_FIRST_FREEZE.md)  
**Checkpoint rinci:** [CHECKPOINT_2026-11-25_FASE2_RO_SO_CLONE.md](CHECKPOINT_2026-11-25_FASE2_RO_SO_CLONE.md), terutama Bagian 57–67.  
**Histori Fase 1:** [HANDOVER_ODOO_FROM_ZERO_2026-11-23_RO_TO_STORE_PASS.md](HANDOVER_ODOO_FROM_ZERO_2026-11-23_RO_TO_STORE_PASS.md).  
**Desain Fase 2 historis:** [FASE2_SO_CAPACITY_AND_PACKING_DESIGN_2026-11-25.md](FASE2_SO_CAPACITY_AND_PACKING_DESIGN_2026-11-25.md). **Aturan lama yang bentrok dikalahkan oleh keputusan owner pada dokumen ini.**

> **WAJIB:** Baca handover Fase 1 dan checkpoint kumulatif SEBELUM mengembangkan fitur. Jangan kehilangan alur CDC→kitchen buffer→MO native→PCK→Paket assembly→SO/RO DO→Store Receipt, jangan membuat solusi yang mempercepat satu tombol tetapi merusak prioritas stok/hak pesanan.

## 1. TIGA konsolidasi: tiga tujuan, tiga snapshot

```text
Published Planning / BOM / Max / date-slot / kitchen routes
   |
   +-- Confirmed RO toko biasa + confirmed RO Paket
   |     [1] PRE PRODUKSI 1
   |     -> aggregate kitchen SKU; frozen ORIGINAL RO & provisional allocation
   |     -> native kitchen MO1, CDC materials, DONE output, kitchen→PCK
   |     -> snapshot historis immutable (bukan jatah DO final)
   |
   +-- Draft/Sent customer quotation (SO direct & Paket)
         -> SALES ADMIN BEFORE-CONFIRM IMPACT PREVIEW
            (RO asli, PP1 allocated, available stock, BOM output,
             prior SO, proposed SO, incremental MO2, extra surplus,
             possible displaced store allocation, Max & cutoff)
         -> CONFIRM atomic date-slot; book validated capacity
         [2] PRE PRODUKSI 2
         -> consolidate confirmed SO+Paket kitchen components by SKU
         -> calculate ONE optional incremental MO2 ONLY when SO shortage
         -> NEVER new MO2 merely to eliminate store RO shortage
         -> CDC materials, MO2 DONE, kitchen→PCK
                     |
         [3] FINAL PACKING CONSOLIDATION
         -> authoritative actual native PCK physically available/free,
            legal source, owner/lot, reservations and prior DO checked
         -> confirmed SO direct & customer Paket needs FIRST
         -> RO Paket next, ordinary RO last
         -> RO partial / zero ACCEPTED, shortage recorded
         -> surplus NOT automatically to stores/customers/transfer
         -> native PCK Paket assembly requires FULL component set
         -> native customer DO / store DO -> transit -> store receipt
```

**Operator requirement:** High-volume workflows must avoid re-entering hundreds of SKUs; original RO/SO source IDs, base UoM and per-recipient demand retained. NO extra WO unless approved; no fake stocks, duplicate allocations, or silent rewriting DONE transactions.

## 2. Owner's LATEST governing decisions

- **Final Packing priority:** **SO customer first** (both direct and kitchen components of SO Paket, with Paket assembly completeness), then **RO Paket**, then **RO toko biasa**. A store may receive less than RO requested or **0 pcs**; shortage must remain visible per store/SKU. Confirmed SO shortage must halt/require explicit exception, not be marked fulfilled.
- **PP2 incremental MO2 is SO-only**: after valid existing MO1/MO2, create one native extra BoM batch per SKU only when necessary for confirmed SO. **No MO2 just because RO toko would be short**. PP1 provisional allocations are not final customer/store delivery rights.
- **SO can be fulfilled WITHOUT MO2**, subject to actual source availability and preserving already assigned or DONE movements; a planning MO or kitchen DONE does not automatically mean free PCK.
- **Before Confirm, Sales Admin must see production impact**, especially SO 5–8 pcs against BoM output100/200. Show original RO separately from PP1 frozen allocated (e.g. **RO190 vs allocated195**), SO confirmed already present, new SO, per-SKU additional MO2, incremental surplus before/after, SO priority impact on RO, booking/Max validity. Customer Paket expands to actual kitchen components, and PCK-sourced parts are separate. Recalculate with date-slot lock at Confirm; do not use a stale preview.
- **Draft/Sent Quotation is allowed without date/slot**; both required at Confirm. Native standard Sales Orders outside custom YA scope remain normal. Published Planning is only approved capacity source. S1 cutoff SO H-1 15:00 WIB; earliest final MO2 H-1 15:30. S2/S3 policy unapproved; fail closed where required rather than invent timings.
- **Surplus from recipe rounding is NOT automatically prorated/allocated/delivered to store**, customer, or fallback internal transfer at final Packing. Unallocated remains visible until separate approved decision. Historical Fase1 rules with automatic store prorata/internal transfer remain documented as history; **do not quietly run them as the Fase2 final allocator or alter stable Fase1**.
- **RO190 vs PP1 allocated195:** 195 includes 5 extras not original RO demand. With real PCK stock200, new SO5 -> SO5, store190, unallocated5; new SO20 -> SO20, store180 (short10); new SO200 -> SO200, store0 (short190). Snapshot PP1 195 remains for audit; new final ledger must reconcile rather than change history.
- **Prevent double allocation**: store A surplus20 cannot be netted away by shortage15 at store B. One SKU/date/slot may be present in many SO and RO, but PCK physical global stock cannot be multiplied by number of batches/slots. Existing native DO assigned or Done requires separate reconciliation; no stealing customer/store stock already physically transferred/received.
- Distinct previous Fase 1 business controls remain: CDC→kitchen buffer mandatory for internal transfer, stock negative forbidden except approved POS; packaging and consignment require actual source, Package assembly in PCK; Max and full kitchen BoM outputs protected.

## 3. Feri's verified evidence / exact trust level

| Source test or audit | Status | What it proves / does NOT prove |
|---|---|---|
| `test_fase2_ya_surplus_4000_no_auto_allocation_pure.py` | **PASS** | Source-only reproduction of dangerous 300 ordered→4300 prorated legacy, and proposed 4000 held unallocated; not deployed |
| `test_fase2_ya_owner_three_consolidations_pure.py` | **PASS** | Three-stage aggregate maths, SO-first, RO partial/zero, no MO2 just for RO, no phantom native PCK stock |
| `test_fase2_ya_sales_admin_preconfirm_so_impact_pure.py` | **PASS** — latest Feri log | SO5 BoM200→extra195, SO8 BoM100→extra92, second SO shares batch, valid Paket expansion, **RO190 ≠ frozen195**, SO10 reveals possible double-claim5, per-store surplus not netted, Max guard |
| `audit_fase2_ya_frozen_surplus_ro_allocation_readonly.py` | **PASS** / exit0 | Frozen 3 batch RO/allocation vs native DO header statuses; no existing frozen store over-entitlement found |
| `audit_fase2_ya_three_stage_native_evidence_readonly.py` | **PASS** / exit0 | Actual MO1/Cancelled status, 0 Confirmed SO ledger and 0 MO2 release, current PCK root quant/reservations |
| Native SO Confirm + MO2 + PCK final distribution + customer DO | **NOT YET UAT / NOT READY** | No evidence full operator workflow works; don't deploy to production |
| Pure small SO exposure helper `test_fase2_ya_small_so_large_bom_exposure_pure.py` | **No Feri log claimed in this handover** | Separate source-only test; do not invent PASS |

**Last Feri pre-Confirm test exact PASS terminal markers:**

```text
DRAFT_SO5_BOM200_BEFORE_CONFIRM_SHOWS_PLUS195_PASS
DRAFT_SO8_BOM100_BEFORE_CONFIRM_SHOWS_PLUS92_PASS
SECOND_SMALL_SO_SHARES_PRIOR_SKU_BATCH_NO_DOUBLE_PRODUCTION_PASS
SO5_COMPLETES_PREVIOUS_SO195_TO_FULL_BATCH_PASS
SO5_ABSORBS_LEGITIMATE_RO_PAKET_MO1_ROUNDING_PASS
SO_DISPLACES_FROZEN_RO_CAPACITY_SHOWN_BEFORE_CONFIRM_PASS
SO_DISPLACES_PAKET_COMPONENT_REQUIRES_ASSEMBLY_REVIEW_PASS
DRAFT_SO_PAKET_COMPONENT_AND_DIRECT_DEDUP_PER_KITCHEN_SKU_PASS
RO_ORIGINAL_190_NOT_MISTAKEN_FOR_FROZEN_ALLOCATED_195_PASS
SO5_USES_MO1_CAPACITY_WITHOUT_MAKING_RO_ORDER_195_PASS
SO10_WITH_FROZEN_RO195_EXPOSES_DOUBLE_CLAIM_5_PASS
PER_STORE_SURPLUS_NOT_HIDDEN_BY_OTHER_STORE_SHORTAGE_PASS
FROZEN_RO_IDENTITY_AND_ORIGINAL_SOURCE_GUARDS_PASS
HARD_PUBLISHED_MAX_AND_BOM_GATES_UNCHANGED_PASS
FASE2_SALES_ADMIN_PRECONFIRM_IMPACT_PURE_PASS
SCOPE_SOURCE_ONLY_NO_OD00_UI_CONFIRM_MO2_OR_STOCK_MUTATION
```

## 4. Real clone quantitative baseline (from Feri 25 Nov 2026 audits)

| Batch | PP1 original RO | PP1 frozen allocated | Store short | PP1 planned surplus |
|---|---:|---:|---:|---:|
| `batch1 2026-Nov-27 S1` | 2,512 | 1,799 | 713 | 2,501 |
| `batch2 2026-Nov-25 S3` | 432 | 432 | 0 | 3,302 |
| `batch3 2026-Nov-23 S2` | 10 | 10 | 0 | 30 |
| **Total** | **2,954** | **2,241** | **713** | **5,833** |

- 3 batches, 49 frozen allocation rows, **0 over-entitled store allocations**, 0 Paket in these batches; shortage713 existed **with 0 SO confirmed**. Store DO: two dispatch **assigned** (1,799 open move qty) and one **dispatch Done** (10), one receipt Done. Do not treat dispatched/reserved stock as unclaimed.
- **MO1 planned8,074; native MO1 finished DONE7,874**, gap200 = SKU10031 **2 cancelled MO ×100**. No native MO2 releases; Confirmed YA SO count0; capacity ledger0. These CANCELLED outputs cannot be stock sources.
- **5,833 historical PP1 planned surplus ≠ physically free stock.** SKU11076 WIP contributes **3,410 planned extras**, excluded from finished→PCK handoff, exact PCK root free0. Cancelled SKU10031 adds90 planned surplus; arithmetic remainder **2,333** still only planned excess.
- **831 exact current PCK root free pcs, 10 unique SKU** as deduplicated from the Feri audit (shared globally across dates/slots): SKU `12373 201; 10042 200; 10025 160; 10026 61; 10039 61; 10040 60; 10008 26; 10035 21; 10009 11; 12379 30`. NOT automatically available for new SO due to age/expiry/source/other commitments; **do not sum the same SKU PCK quant once per batch**.
- Example cross-slot: `10025` batch2 had planned excess299 but native global free only160 due to other slot reserved allocations. There is no one-to-one per-batch ownership of free quant.

**Installed versions in clone:** `ya_store_ro 19.0.8.1.3`; `ya_package_store_ro 19.0.1.3.0`; `ya_sale_production_capacity 19.0.1.1.3`. Feri ran read-only audits using `odoo-bin shell` `SET TRANSACTION READ ONLY`; results exit0.

## 5. SOURCE FILE MAP and dangerous gaps

**Read first (do not alter historical snapshot while checking):**

- `addons/ya_sale_production_capacity/models/three_stage_consolidation_rules.py` — **PURE NOT IMPORTED**, PP1/PP2/final PCK illustrative calculation.
- `addons/ya_sale_production_capacity/models/mo2_owner_so_first_rules.py` — **PURE NOT IMPORTED**, SO-only extra MO2 + RO partial/0.
- `addons/ya_sale_production_capacity/models/so_draft_production_impact_rules.py` — **PURE NOT IMPORTED**, before Confirm SO production/surplus/RO displacement and frozen RO diagnostics.
- `addons/ya_sale_production_capacity/models/mo2_small_so_batch_risk_rules.py` — **PURE NOT IMPORTED**, tiny SO vs giant BOM exposure.
- `addons/ya_sale_production_capacity/models/packing_surplus_guard_rules.py` — **PURE NOT IMPORTED**, no unrequested store/DO surplus.
- `addons/ya_sale_production_capacity/models/confirm_capacity_math.py`, `confirm_readiness.py`, `capacity_booking.py`, `capacity_reservation.py` — imported native SO routes, atomic Confirm ledger; must preserve date-slot lock and nonstandard native DO bypass restrictions.
- **INCOMPATIBLE ACTIVE SOURCE:** `addons/ya_sale_production_capacity/models/mo2_priority_rules.py` `calculate_mo2_release` rounds **SO+RO Paket+ordinary RO** and is imported by `mo2_release.py`. Latest owner says MO2 **SO shortage only**. Need isolate, fix and test on clone before any real release.
- **OLD preproduction surplus prorata:** `addons/ya_store_ro/models/package_priority_rules.py`; `addons/ya_package_store_ro/models/joint_slot_preview.py` may capture prorata extras into frozen store allocation. **Do NOT use frozen allocation as final entitlement.** Keep Fase 1 running.
- Fase1 native transfer/DO files `addons/ya_finished_packing_transfer/models/finished_packing.py`, `addons/ya_packing_store_delivery/models/store_delivery.py` gate on **other** DB `erp-yussyakmal-mrp-test`; do not defeat gate blindly on Fase2.
- WIP `11076`, consignment `11790`, PCK component source/packaging `12337 / 11298 / 11384`, hard Published Max exceptions remain real owner-fixture blockers from earlier checkpoint; do not invent routes or stock. Full SO & RO Paket finished assembly needs native components and real receipts.
- `addons/ya_sale_production_capacity/models/__init__.py` does **not** import these new PURE helpers; GitHub commits alone do not alter Odoo runtime.

## 6. Remaining business decisions and engineering gates

1. **Sales Admin UI:** implement native Draft/Sent `Hitung Dampak Produksi` (read-only); new line/date/slot change invalidates preview. Simulate how many SOs aggregate per SKU, how much PP1 actual available PCK may absorb, gross batch exposure and displaced RO. On Confirm recalc with date-slot lock. If a large new batch is triggered, warning/approval rights and threshold **not yet owner-specified**.
2. **Source completeness:** original RO per recipient, RO Paket components, SO direct & customer Paket components, same date/slot/BoM, real MO1/2 done and stock move origin, exact PCK root free (age/lot/owner/package), reservations/assigned and done DO, other dates/slots, duplicate commitments. **One physical unit cannot be allocated twice.**
3. **Native PP2:** modify clone-only actual MO2 release logic from gross SO+RO target to SO shortage only; MO1 already planned might later be CANCEL, so stop before promise unless confirmed native status/feasibility. Preserve cutoff & Published Max, one MO2 per SKU/slot.
4. **Final Packing ledger:** create one immutable audited SO-first recipient allocation ledger based on native free PCK; customer Package *full component* availability/assembly; stores may get partial/0; **per-store distribution under shortage remains owner decision**; do not silently prorate leftovers. DO generated only from this ledger, not preprod frozen allocation.
5. **End-to-end rollback UAT clone:** use owner exact mixed fixtures from cumulative checkpoint; verify no SO at Confirm without ledger, no MO2 for store shortages, no PCK phantom/free reserved consumption, native DONE MO→kitchen→PCK, Package source, same slot, no duplicates, proper DO→transit→store receipt, cost/stock audit and full rollback.
6. **Open policy:** S2/S3 cutoff; tiny SO overproduction approval thresholds and who may approve; surplus disposition; distribution rule across multiple stores when partial; SO edit/cancel after Confirm/cutoff; how to handle already assigned/done RO delivery without violating native reservation.
7. **UI date standard for new/custom forms:** `YYYY-Mon-DD` (e.g. `2026-Nov-27`) display; keep native Odoo `fields.Date`, use YA computed label where appropriate. Do not convert Date to Char for display.

## 7. SAFE RESUME / STOP RULE

**During this handover request:** NO test, no Odoo shell, no addon upgrade, no database changes, no service restart. Only documentation commit in GitHub.

**On new session:** read checkpoint and handover first. If owner asks to continue, first perform source read-only gap review and reproduce baseline PURE PASS where needed; then design native draft-quotation impact adapter with full provenance. Feri runs commands explicitly; no automatic execution just because a script exists. Keep Fase 1 & production intact.

**Never** run `-u` / install against `erp-yussyakmal` or `erp-yussyakmal-mrp-test`; Fase2 clone is `erp-yussyakmal-mrp-test-RO_SO` only. Any native test requiring writes must be separately backed up, explicitly authorized, isolated and rolled back. Some old source files hard-code Fase 1 DB gate, so do not simply bypass or restart.

### Ready-to-paste instruction for next conversation

> **Lanjut ODOO FROM ZERO Fase 2. Baca dahulu `doc/HANDOVER_2026-11-25_FASE2_TIGA_KONSOLIDASI_SO_FIRST.md`, `doc/CHECKPOINT_2026-11-25_FASE2_TIGA_KONSOLIDASI_SO_FIRST_FREEZE.md`, lalu seluruh `doc/CHECKPOINT_2026-11-25_FASE2_RO_SO_CLONE.md` dan referensi Fase1. Sudah PURE PASS tiga konsolidasi & Sales Admin pre-Confirm, READ-ONLY DB PASS; native E2E belum. Kebijakan terbaru: PP1=RO/MO1, PP2=SO-only tambahan MO2, Packing=SO first lalu RO Paket/toko boleh kurang/0; surplus tidak auto dikirim. DB clone hanya `erp-yussyakmal-mrp-test-RO_SO`. Jangan menganggap 5.833 planned surplus sebagai stok; current exact PCK free global 831 pada 10 SKU dan 0 SO/MO2. JANGAN install/upgrade/test DB sebelum review handover. Periksa mismatch `mo2_priority_rules` yang masih hitung SO+RO; mulai dari desain integrasi Sales Admin sebelum Confirm dan real final PCK ledger, tanpa mengubah Fase 1.**

**Handover complete.**
