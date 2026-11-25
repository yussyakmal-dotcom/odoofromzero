# CHECKPOINT KEPUTUSAN — FASE 2: TIGA KONSOLIDASI & SO-FIRST

**Tanggal:** 2026-Nov-25 (WIB)  
**Project:** ODOO FROM ZERO / YA Bakery / Odoo 19 Community  
**Repo:** [yussyakmal-dotcom/odoofromzero](https://github.com/yussyakmal-dotcom/odoofromzero) — branch `main`  
**Satu-satunya DB Fase 2 untuk kerja selanjutnya:** `erp-yussyakmal-mrp-test-RO_SO`  
**Status:** **FREEZE dokumentasi; perhitungan PURE PASS; dua audit data clone READ-ONLY PASS; integrasi native tiga tahap dan alokasi final SO belum UAT.**

> **START HERE:** [Handover aktif](HANDOVER_2026-11-25_FASE2_TIGA_KONSOLIDASI_SO_FIRST.md). Riwayat lengkap tersimpan pada [checkpoint kumulatif](CHECKPOINT_2026-11-25_FASE2_RO_SO_CLONE.md). Dokumen historis Fase 1 tidak boleh dijadikan alasan mengaktifkan prorata surplus untuk alokasi FINAL Fase 2.

## 1. Keputusan owner yang mengikat

1. **Ada TIGA konsolidasi, jangan digabung:**
   - **Pre Produksi 1 (PP1):** konsolidasi **RO asli toko + RO Paket**, pembulatan BoM / Published Planning, snapshot immutable, MO1.
   - **Pre Produksi 2 (PP2):** konsolidasi **SO pelanggan** termasuk komponen Paket pelanggan; setelah memperhitungkan MO1/MO2 yang sudah ada, tambahan MO2 **hanya untuk kekurangan kebutuhan SO**, **bukan** untuk mengembalikan kekurangan jatah RO.
   - **Konsolidasi Final di Packing (PP3):** alokasi penerima dari **stok fisik tersedia yang sah**, prioritas **SO langsung & kebutuhan lengkap Paket SO** → **RO Paket** → **RO toko biasa**. RO toko **boleh kurang dari pesanan atau 0**. Kekurangan harus terlihat per SKU/penerima.
2. **Tidak semua SO menghasilkan MO2.** SO boleh dipenuhi dari output MO1/MO2 yang sudah benar-benar tersedia dan bisa dialokasikan, **setelah memperhitungkan reservasi, DO assigned/done, sumber asal, dan hak pemesanan**. Planned MO bukan free stock.
3. **Sales Admin melihat simulasi sebelum Confirm**: BoM output 100/200 vs pesanan kecil, SO baru, SO sebelumnya, RO asli, alokasi sementara PP1, MOQ/BoM Max, MO1/MO2, tambahan produksi jika perlu, surplus sebelum/sesudah SO dan perubahan kekurangan toko. Draft/Sent Quotation **boleh tanpa tanggal/slot**; tanggal/slot wajib saat Confirm. Recheck atomic saat Confirm, jangan percaya preview yang sudah basi.
4. **RO asli ≠ alokasi sementara PP1.** Contoh RO 190, PP1 allocated 195 karena surplus 5; **195 bukan pesanan sah toko**. Snapshot historis immutable. Final ledger baru tidak boleh otomatis mengirim 195 bila RO asli 190.
5. **Surplus pembulatan tidak otomatis dibagi/prorata/dikirim ke toko, pelanggan, atau internal transfer alternatif.** Tetap terlihat sebagai unallocated sampai ada keputusan disposisi tersendiri yang disetujui. Aturan ini **menggantikan kebijakan surplus otomatis pada desain Fase 1 / dokumen Fase 2 awal UNTUK alokasi final Fase 2**, tidak menghapus histori atau mengubah Fase 1.
6. **SO harus dilindungi pertama.** SO yang tidak tertutup secara fisik menuntut exception/stop; kekurangan RO toko **tidak** menjadi alasan membuat MO2 tambahan. Untuk Paket SO wajib uji kelengkapan komponen & native MO perakitan PCK, tidak cukup hitung SKU agregat.
7. Published Planning Max, kelipatan BoM native, rute dapur, ownership/lot, cutoff S1, lock date-slot, satu tambahan MO2 per SKU/slot dan native stock conservation tetap wajib. **Tidak ada WO baru, fake stock, fake RO, atau diam-diam mengubah jatah/DO yang sudah Done.**

## 2. Bukti PASS (jangan melebihkan klaim)

| Kategori | Bukti yang diberikan Feri | Kesimpulan yang sah |
|---|---|---|
| Logika surplus 300 vs 4.000 | `FASE2_PURE_SURPLUS_ENTITLEMENT_GUARD_PASS` | Algoritme contoh menahan surplus, **bukan** addon aktif |
| Logika tiga konsolidasi | `FASE2_OWNER_THREE_CONSOLIDATIONS_PURE_PASS` | Urutan PP1→PP2→Packing dan RO 0/partial valid di pure Python |
| Frozen RO/DO DB clone | `READ_ONLY_FASE2_FROZEN_SURPLUS_RISK_AUDIT_PASS`, exit 0 | 3 batch, tidak ditemukan `allocated > RO requested` pada snapshot yang diperiksa |
| Native MO/PCK DB clone | `READ_ONLY_FASE2_THREE_STAGE_NATIVE_EVIDENCE_PASS`, exit 0 | MO/status/stock terbaca, **bukan** UAT operator SO→MO2→final DO |
| Pre-Confirm SO impact test | `FASE2_SALES_ADMIN_PRECONFIRM_IMPACT_PURE_PASS` dan 14 case PASS dari Feri | SO kecil / Paket / RO asli190 vs frozen195 / double claim5 / per-store / Published Max, **PURE only, belum terpasang UI** |
| Native E2E SO/PP2/final packing | Belum ada SO Confirmed dan belum ada MO2 release pada audit | **BELUM PASS; belum boleh diklaim siap operasional** |

## 3. Snapshot asli database clone — 25 Nov 2026

| Batch | RO asli | Frozen allocated | RO shortage | Planned surplus |
|---|---:|---:|---:|---:|
| 2026-Nov-27 S1, batch 1, 20 SKU | 2.512 | 1.799 | 713 | 2.501 |
| 2026-Nov-25 S3, batch 2, 14 SKU | 432 | 432 | 0 | 3.302 |
| 2026-Nov-23 S2, batch 3, 1 SKU | 10 | 10 | 0 | 30 |
| **TOTAL** | **2.954** | **2.241** | **713** | **5.833** |

- 49 frozen allocations; frozen over-entitlement 0; tidak ada Paket pada ketiga batch (`has_package=False`). Kekurangan RO **713 ini sudah ada saat belum ada SO Confirmed**; jangan klaim kekurangan itu disebabkan prioritas SO.
- **MO1 planned 8.074**, MO1 finished **Done 7.874**; selisih 200 berasal dari dua MO SKU **10031** masing-masing 100 dengan state **cancel**. Cancel tidak boleh dijadikan stok.
- **SKU 11076** (WIP, dikecualikan dari normal finished-goods handoff) menyumbang **3.410** dari 5.833 planned surplus, tetapi exact PCK free 0. **90** lainnya dari surplus planned SKU 10031 yang MO-nya Cancel. Sisa aritmetika **2.333** hanya *planned* surplus lain, bukan stok bebas.
- Distinct current PCK root physical minus native reserved = **831 pcs dalam 10 SKU** dari audit, tidak boleh dijumlah berulang lintas tiga batch. Detail: `12373=201; 10042=200; 10025=160; 10026=61; 10039=61; 10040=60; 10008=26; 10035=21; 10009=11; 12379=30`. Ini persediaan lokasi **global pada saat audit** (company1, exact root PCK, untracked/unowned/unpackaged), **bukan** inventori yang otomatis eligible untuk SO tanggal/slot tertentu.
- SO YA Confirmed = **0**; capacity ledger = **0**; MO2 native release = **0**. Dua dispatch **assigned** dengan 1.799 qty pending; satu dispatch **done 10**, serta receipt Done 1. Status ini tidak boleh direset/ditimpa.
- Modul terpasang di clone: `ya_store_ro 19.0.8.1.3`, `ya_package_store_ro 19.0.1.3.0`, `ya_sale_production_capacity 19.0.1.1.3`.

## 4. Mismatch sumber yang masih berbahaya

- File **imported/existing** `addons/ya_sale_production_capacity/models/mo2_priority_rules.py::calculate_mo2_release` menghitung target output berdasarkan **SO + RO Paket + RO toko**. Ini dapat memicu MO2 semata-mata untuk RO; **bertentangan dengan keputusan owner terbaru**. `mo2_release.py` mengimpor fungsi tersebut; **jangan jalankan release native** sebelum diubah dan diuji rollback pada clone.
- `addons/ya_store_ro/models/package_priority_rules.py` punya aturan lama **surplus BoM prorata ke toko**. `addons/ya_package_store_ro/models/joint_slot_preview.py` dapat membekukan nilai tersebut sebagai `allocation.qty_allocated`. **Tidak boleh dipercaya sebagai final SO-first entitlement.**
- `addons/ya_finished_packing_transfer/models/finished_packing.py` dan `addons/ya_packing_store_delivery/models/store_delivery.py` memakai DB gate Fase 1 `erp-yussyakmal-mrp-test`; **jangan bypass untuk clone RO_SO**.
- Helper `mo2_owner_so_first_rules.py`, `three_stage_consolidation_rules.py`, `so_draft_production_impact_rules.py`, `packing_surplus_guard_rules.py` **belum di-import oleh addon / belum dipasang pada transaksi**. PASS pure Python ≠ UI atau native transaction PASS.
- Konsolidasi final butuh final entitlement per source-id/store-id/SKU & native stock; mesin pure saat ini masih agregat dan belum menentukan adilnya distribusi antar toko jika stok kurang. **Jangan mengarang kebijakan prorata antar toko tanpa persetujuan owner.**

## 5. STOP RULE untuk sesi/kolaborator berikutnya

- **JANGAN** menyentuh `erp-yussyakmal` produksi, meng-upgrade `erp-yussyakmal-mrp-test` Fase 1, instal/`-u`, restart service, membuat SO/MO/transfer/DO/stock adjustment, atau mengubah historic PP1 hanya demi dokumentasi.
- **JANGAN** menyebut `5833` sebagai stok bisa dijual atau `831` sebagai stok teralokasi; gunakan per-SKU, exact PCK root, tanggal/slot, reservations, assigned/done DO dan asal stok.
- **JANGAN** menghapus batas produksi dari cutoff atau Published Max; S1 cutoff SO H-1 15.00 WIB, MO2 earliest H-1 15.30 WIB; S2/S3 belum diputuskan.
- **JANGAN** mengklaim native tiga konsolidasi siap sebelum rollback UAT yang membuktikan SO Draft preview→Confirm atomic→optional MO2→CDC→kitchen MO Done→PCK→SO-first final ledger→Paket assembly→customer/store DO, dan menjaga Fase 1.

## 6. Resume next session (bukan perintah menjalankan sekarang)

1. Buka handover dan checkpoint kumulatif, pahami versi terpasang serta semua pengecualian PP1/PP2/PCK.
2. Pure `script/test_fase2_ya_sales_admin_preconfirm_so_impact_pure.py` **sudah PASS Feri**. Lanjut review integrasi secara read-only: SKU/stock eligibility, SO/RO source/slot dan native reservation; jangan langsung deploy.
3. Implementasi **adapter baca-saja** untuk Sales Admin: RO asli, provisional PP1, SO confirmed, Paket component, MO1 Done/cancel, MO2 nyata, stock/reserved/DO PCK; buat preview sebelum Confirm. Sekaligus revalidate dengan date-slot mutex saat confirm.
4. Setelah bukti terverifikasi, perbaiki perhitungan MO2 imported menjadi SO-only, lalu ledger final recipient native SO-first dengan store partial/zero; rollback UAT di clone dan freeze audit, **bukan** deploy langsung.
5. Keputusan belum lengkap: kebijakan distribusi kekurangan antar toko, persetujuan risiko surplus SO kecil, disposisi stok lebih, S2/S3 cutoff, dan aturan pembatalan SO Confirmed.

**Handover terperinci:** [HANDOVER_2026-11-25_FASE2_TIGA_KONSOLIDASI_SO_FIRST.md](HANDOVER_2026-11-25_FASE2_TIGA_KONSOLIDASI_SO_FIRST.md).  
**Referensi lama yang tetap wajib dibaca untuk flow Fase 1:** [HANDOVER_ODOO_FROM_ZERO_2026-11-23_RO_TO_STORE_PASS.md](HANDOVER_ODOO_FROM_ZERO_2026-11-23_RO_TO_STORE_PASS.md).

*Status akhir: dokumentasi selesai. Tidak ada test atau database mutation yang dilakukan dalam pembuatan checkpoint ini.*


## 7. Final update dokumentasi / PASS setelah checkpoint awal

- Feri menjalankan `python3 script/test_fase2_ya_sales_admin_preconfirm_so_impact_pure.py` dan seluruh asersi berhasil, termasuk `DRAFT_SO5_BOM200_BEFORE_CONFIRM_SHOWS_PLUS195_PASS`, `DRAFT_SO8_BOM100_BEFORE_CONFIRM_SHOWS_PLUS92_PASS`, `RO_ORIGINAL_190_NOT_MISTAKEN_FOR_FROZEN_ALLOCATED_195_PASS`, `SO10_WITH_FROZEN_RO195_EXPOSES_DOUBLE_CLAIM_5_PASS`, `PER_STORE_SURPLUS_NOT_HIDDEN_BY_OTHER_STORE_SHORTAGE_PASS`, `HARD_PUBLISHED_MAX_AND_BOM_GATES_UNCHANGED_PASS`, dan final `FASE2_SALES_ADMIN_PRECONFIRM_IMPACT_PURE_PASS`.
- Hasil PURE PASS **bukan** bukti Sales Admin UI live atau native SO Confirm / final PCK DO. Tidak ada addon yang ditambahkan ke `models/__init__.py` dalam sesi dokumentasi.
- **Dokumen handover sekarang tersedia dan sudah lengkap:** [HANDOVER_2026-11-25_FASE2_TIGA_KONSOLIDASI_SO_FIRST.md](HANDOVER_2026-11-25_FASE2_TIGA_KONSOLIDASI_SO_FIRST.md). Mulai kelanjutan pekerjaan dengan membaca handover tersebut, checkpoint ini dan riwayat kumulatif; jangan ulangi perintah pure yang sudah PASS kecuali ada perubahan kode relevan.
- **Status akhir:** DOCUMENTATION/HANDOVER FREEZE. Belum ada perubahan DB ataupun uji native dari pekerjaan dokumentasi ini.

## Owner decision 2026-11-26 — native MO Source label

- New PP1 MO: `MO1 / YYYY-Mon-DD / Sx` (delivery date, not creation date).
- New PP2 MO: `MO2 / YYYY-Mon-DD / Sx`.
- Normal SO and manual MO retain native Odoo origin. No new field or list view required for this change.
- Existing MO origin and historical snapshots are not rewritten; relational MO1/MO2 links remain authoritative, not the display string.
- Source change only; no deployment, database mutation or native UAT performed. PP1 inclusion of early SO and timer/operator policy remain open; no production calculation changes in this patch.
