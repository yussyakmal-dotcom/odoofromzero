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
