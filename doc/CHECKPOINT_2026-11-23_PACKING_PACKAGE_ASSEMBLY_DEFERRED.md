> **STATUS UPDATE 23 NOV: DIBUKA KEMBALI.** Tahap penerimaan toko dilaporkan lulus uji oleh owner (“RO TOKO → STOCK TOKO good”). Milestone berikutnya adalah **Rakit Paket di Packing**; audit SKU Paket, BoM dan stok dulu sebelum implementasi. Baca [HANDOVER TERBARU](HANDOVER_ODOO_FROM_ZERO_2026-11-23_RO_TO_STORE_PASS.md). Judul “DITUNDA” di bawah merupakan keputusan historis yang kini telah mencapai syarat untuk dilanjutkan.

# CHECKPOINT — 2026-Nov-23 — Rakit Paket di Packing (DITUNDA, TIDAK DIHAPUS)

## Keputusan owner — wajib dibaca saat melanjutkan ODOO FROM ZERO

Sesudah MO Done, barang jadi dipindahkan dari gudang dapur ke PCK/Stock melalui native Internal Transfer satu langkah (tanpa serah-terima fisik terpisah karena satu lokasi).

**Prioritas pengerjaan saat ini:**
1. Selesaikan pembuktian GUI Produk Jadi → Packing di database test `erp-yussyakmal-mrp-test`.
2. Gunakan alokasi RO toko yang SUDAH dihitung sebelum produksi untuk menyiapkan Delivery Order / Internal Transfer Packing → Toko (hindari input ulang).
3. Selesaikan flow toko menerima barang, stok toko bertambah sesuai transaksi Odoo.
4. **SETELAH FLOW PENERIMAAN TOKO SELESAI, KEMBALI KERJAKAN FLOW \"RAKIT PAKET DI PACKING\".** Ini adalah pekerjaan tertunda yang harus diingat, bukan dibatalkan.

## Batas scope sekarang
- **JANGAN** memasukkan implementasi perakitan paket sebagai penghalang alokasi RO → DO Toko → penerimaan toko.
- **JANGAN** menganggap SKU paket sudah memiliki stok atau otomatis dapat didistribusikan hanya karena terdaftar dalam RO; perlakuan sementara terhadap item paket perlu dipastikan sebelum DO, jangan mengarang stok.
- Ketika tiba gilirannya, rancang aturan SKU komponen, SKU paket hasil rakitan, konsumsi komponen, pembentukan stok barang paket, traceability dan hubungan dengan alokasi RO. Keputusan rinci belum dibuat owner.
- Untuk sementara, hanya distribusikan SKU yang stoknya memang tersedia di Packing dan memenuhi alur yang disetujui.
- Jangan mengganti sistem dengan alur rumit; optimalkan jumlah klik operator dan gunakan native stock transaction + SOP.

## Status pembuktian
- E2E rollback `script/test_finished_packing_transfer_rollback_ya.py` untuk `Packing 2026-Nov-25 S3`: 12 SKU dipindahkan, 1 picking, WIP 11076 dikecualikan, stock deltas PASS, double-click PASS, rollback PASS berdasarkan log Feri.
- Pengujian klik GUI / transfer permanen **belum dikonfirmasi**.
- DO dan penerimaan toko **belum diimplementasikan atau diuji pada checkpoint ini**.

## Update hasil user test — 2026-Nov-23
Owner melaporkan: **"sudah di test RO TOKO ---- > STOCK TOKO good"**.
Status: alur RO Toko sampai stok toko dinyatakan **lulus uji operasional oleh owner**. Ini adalah laporan uji pengguna, bukan audit otomatis tambahan; catatan tidak memuat bukti nomor dokumen/detail kuantitas tiap tahap.

**Tindak lanjut:** Buka kembali pekerjaan yang sebelumnya sengaja ditunda, **Rakit Paket di Packing**. Sebelum membuat kode, petakan SKU paket, komponen per paket, trigger perakitan, lokasi stok input-output, pencatatan qty aktual dan kaitan dengan RO/DO. Jangan mengubah workflow RO→stok toko yang sudah lolos tanpa alasan dan pengujian regresi. Gunakan addon terpisah dan DB test `erp-yussyakmal-mrp-test`.

## Definisi final Produk Paket — dikonfirmasi owner 23 Nov 2026
**Produk Paket adalah SKU produk jadi yang diproduksi berdasarkan BoM, tetapi komponen BoM-nya adalah produk JADI dari satu atau lebih dapur.** Perakitan berlangsung di Packing setelah hasil produksi dapur dipindahkan ke `PCK/Stock`. Saat rakit paket, stok SKU komponen produk jadi dikonsumsi dan stok SKU Paket hasil rakitan bertambah di Packing. Tidak boleh ada stok ganda atau memindahkan komponen sebagai barang dikirim bila sudah dikonsumsi menjadi paket.

**Belum ditetapkan:** jadwal/trigger perakitan, Qty batch, operasi MO per SKU paket, alokasi paket ke toko, pengecualian dan catatan shortage. Semua harus mengikuti audit BoM dan keputusan owner, jangan berasumsi implementasi sudah berjalan.

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
