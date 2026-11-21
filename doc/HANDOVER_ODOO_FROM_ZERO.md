# ODOO FROM ZERO — Handover Operasional

**Tanggal:** 22 November 2026  
**Prioritas saat ini:** Modul `ya_scrap_multi` — stabilisasi impor Excel dan pengujian GUI.

> **BACA DAHULU:** Dokumen ini merangkum checkpoint terbaru. Riwayat lengkap master Manufacturing, Purchasing, dan UoM di [STATUS_PENGEMBANGAN_MRP.md](STATUS_PENGEMBANGAN_MRP.md). Jangan memakai status checkpoint lama sebagai keadaan terkini.

## 1. Prinsip dan batas proyek

**Pahami Odoo terlebih dahulu, tetapkan policy setelah dipelajari.** Jangan menyalin policy, data historis atau asumsi dari proyek/bisnis lain. Bedakan keputusan user, standar Odoo, hasil tes aktual, dan usulan. Tidak ada policy larangan stok minus atau approval Scrap yang telah diputuskan di proyek ini.

**Database:**
- **Aktif untuk pengembangan & pengujian:** `erp-yussyakmal-mrp-test`
- **JANGAN DISENTUH:** `erp-yussyakmal` (utama)
- **JANGAN DISENTUH:** `erp-yussyakmal-integer-test` (checkpoint Purchasing)

**Lingkungan:** Ubuntu + Odoo 19 Community, Odoo Python `/opt/odoo19/venv/bin/python3`, binary `/opt/odoo19/odoo/odoo-bin`, config `/etc/odoo19.conf`; custom addons aktif di `/opt/odoo19/custom-addons`; repository `~/odoofromzero`, GitHub `yussyakmal-dotcom/odoofromzero`. Jangan menganggap `git pull` saja sudah memperbarui addon aktif. Jangan commit data master privat ke repo publik.

## 2. Yang sudah selesai

### Manufacturing master
- 16 Work Center; 955 BoM; 8.502 BoM component lines; 14 Manufacturing Operation Types; tidak ada Work Order Operations.
- Koreksi UoM 73 SKU telah selesai dan diaudit (lihat status teknis). Jangan impor ulang BoM maupun perubahan UoM tanpa kebutuhan baru.
- Uji MO persyaratan bahan pernah lulus rollback; test DB tidak mempunyai saldo stok awal. Belum ada bukti penuh MO selesai dengan valuasi/akuntansi produksi.

### Scrap setup
- Pengguna mengakhiri audit perbandingan Scrap versus Opname; fokus pada Multi-SKU Scrap.
- Keputusan: satu virtual lokasi tujuan **Scrap** untuk Central, semua dapur dan seluruh toko; **satu lokasi asal per dokumen**, satu Source Document, satu alasan, banyak SKU.
- Pembuatan lokasi dan alasan telah **APPLY COMMITTED** pada MRP test: lokasi Scrap ID 248, reason tag Rusak ID 3, Expired ID 4. Ini **ID pada MRP test saja**, bukan ID global.
- Master alasan menggunakan model bawaan `stock.scrap.reason.tag`; reason dalam `stock.scrap` adalah `scrap_reason_tag_ids`.
- Alasan hanya dapat **dipilih**, tidak dibuat baru dari form `Multi-SKU Scrap` (pengaturan no_create/no_create_edit/no_quick_create pada UI). Belum ada keputusan pembatasan admin global.

### Addon Multi-SKU Scrap
- Sumber: `addons/ya_scrap_multi` — installed pada MRP test menurut hasil SQL `state=installed`; menu dan form sudah muncul dan dinyatakan OK oleh pengguna.
- Model parent `ya.scrap.batch`, lines `ya.scrap.batch.line`, native `stock.scrap` terhubung melalui `ya_batch_id`.
- Tombol **Validate All Scrap** membuat 1 native Scrap per baris dan memanggil `stock.scrap.action_validate()`. Semua berhasil bersama atau rollback jika gagal.
- Excel (.xlsx): kolom `SKU, Quantity, UoM`; baris ditambahkan di Draft, UoM kosong mengikuti unit produk, tersedia template unduh, maksimum 1000 baris tiap impor. **Kode ada; workflow Excel belum lulus tes terpisah.**
- Bug versi awal `uom.uom.category_id` tidak tersedia di Odoo 19, diperbaiki menggunakan `_has_common_reference()` di commit `014fe71`.

## 3. Bukti tes terbaru: 3 SKU → 3 Scrap → 1 Batch (PASS)

**Asal informasi:** output terminal pengujian yang user berikan.  
**Script:** `script/test_multi_scrap_3sku_e2e_rollback_ya.py`  
**Target DB:** `erp-yussyakmal-mrp-test`  
**Hasil:** `TEST_EXIT_CODE=0`, `E2E_3_SKU_3_NATIVE_SCRAPS_1_BATCH_OK`, `E2E_3_SKU_ROLLBACK_CONFIRMED`.

| SKU | Quantity | Native Scrap | Stock Move | Sisa stok sementara |
|---|---:|---|---:|---:|
| 10440 | 1 | SP/00001 | 46 | 9 |
| 10180 | 2 | SP/00002 | 47 | 8 |
| 10182 | 3 | SP/00003 | 48 | 7 |

Ketiganya memiliki alasan **Rusak**, Source Document `YA-E2E-3SKU-ROLLBACK`, sumber `TART/Stock`, tujuan `Scrap` dan parent batch `SCRB/2026/00003`. Tiga native Scrap dan tiga Stock Move berstatus Done; stok berkurang sesuai jumlah masing-masing.

**PENTING:** Output di atas **hanya terjadi dalam transaksi uji dan sudah di-rollback**. Nomor/id transaksi dan stok sementara **tidak menetap** di DB.

## 4. Masih harus diuji (jangan klaim PASS)

1. **Impor Excel Draft:** jalankan `script/test_multi_scrap_xlsx_rollback_ya.py` dan cek data SKU sampel script dahulu; lakukan juga tes impor tiga SKU melalui UI.
2. **Alur GUI:** dokumen Draft, tambah manual, template unduh, impor, validasi, buka 3 native scraps via smart button.
3. **Pembatasan alasan UI:** pastikan user biasa tidak bisa membuat alasan baru pada field header, dan tag master tetap bisa dipilih.
4. **Error handling:** SKU tidak ditemukan / duplikat, UoM tak kompatibel, Qty nol/negatif, satu baris gagal -> seluruh dokumen tidak posting parsial.
5. **Batasan yang belum diuji:** barang ber-lot/serial, multi-company, laporan akuntansi kerugian Scrap, penerapan pada gudang/toko lain, hak akses operasional.

**Bukan tugas sekarang:** mengulang audit Scrap versus Opname, mengulang impor BoM, atau merancang policy yang tidak diminta.

## 5. Langkah teknis aman

1. `cd ~/odoofromzero && git pull` untuk sinkronisasi Git.
2. Untuk perubahan addon, deploy folder `addons/ya_scrap_multi/` ke `/opt/odoo19/custom-addons/ya_scrap_multi/`, periksa hak akses dan perbedaan file; **jangan upgrade DB lain**.
3. Jika diperlukan, upgrade hanya `erp-yussyakmal-mrp-test`:
   ```bash
   sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin \
     -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test \
     -u ya_scrap_multi --stop-after-init --no-http
   ```
4. Uji dengan Odoo shell `--no-http` dan skrip rollback, baca exit code serta log; jangan tinggalkan saldo stok hasil simulasi.
5. Setelah hasil valid, perbarui status dan handover ini. Perlu persetujuan user sebelum promosi keluar DB test.

## 6. Pesan singkat untuk sesi berikut

> Lanjutkan ODOO FROM ZERO dari modul `ya_scrap_multi`. Sudah installed dan form OK di DB `erp-yussyakmal-mrp-test`; satu lokasi Scrap bersama serta tag Rusak/Expired sudah di-APPLY. End-to-end 1 batch + 3 SKU -> 3 native `stock.scrap` + 3 `stock.move` telah lulus, rollback berhasil. Berikutnya fokus pengujian Excel import dan GUI, jangan ulangi audit Scrap vs Opname, jangan mengimpor policy dari proyek lain, jangan menyentuh DB utama/Purchasing test. Catatan riwayat ada di `doc/STATUS_PENGEMBANGAN_MRP.md`.
