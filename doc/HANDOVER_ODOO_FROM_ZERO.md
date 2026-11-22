# ODOO FROM ZERO — Handover Operasional

**Tanggal:** 22 November 2026  
**Prioritas saat ini:** Dokumentasi/desain **RO toko per dapur + impor Excel + konsolidasi MO**, lalu integrasi SO; **belum implementasi**. Pengujian Excel `ya_scrap_multi` tetap tercatat sebagai pekerjaan modul terpisah yang belum selesai.

> **BACA DAHULU:** Dokumen ini merangkum checkpoint terbaru. Riwayat lengkap master Manufacturing, Purchasing, dan UoM di [STATUS_PENGEMBANGAN_MRP.md](STATUS_PENGEMBANGAN_MRP.md). Jangan memakai status checkpoint lama sebagai keadaan terkini.

## 1. Prinsip dan batas proyek

**Pahami Odoo terlebih dahulu, tetapkan policy setelah dipelajari.** Jangan menyalin policy, data historis atau asumsi dari proyek/bisnis lain. Bedakan keputusan user, standar Odoo, hasil tes aktual, dan usulan. Tidak ada policy larangan stok minus atau approval Scrap yang telah diputuskan di proyek ini.

**Database:**
- **Aktif untuk pengembangan & pengujian:** `erp-yussyakmal-mrp-test`
- **JANGAN DISENTUH:** `erp-yussyakmal` (utama)
- **JANGAN DISENTUH:** `erp-yussyakmal-integer-test` (checkpoint Purchasing)

**Lingkungan:** Ubuntu + Odoo 19 Community, Odoo Python `/opt/odoo19/venv/bin/python3`, binary `/opt/odoo19/odoo/odoo-bin`, config `/etc/odoo19.conf`; custom addons aktif di `/opt/odoo19/custom-addons`; repository `~/odoofromzero`, GitHub `yussyakmal-dotcom/odoofromzero`. Jangan menganggap `git pull` saja sudah memperbarui addon aktif. Jangan commit data master privat ke repo publik.


## 2. Fokus arsitektur saat ini — RO toko dahulu (BELUM IMPLEMENTASI)

**Sumber keputusan:** diskusi pengguna 22 November 2026. Detail lengkap dan daftar celah ada pada bagian **“22 November 2026 — Desain Replenishment Toko, Konsolidasi MO, dan Prioritas SO”** dalam [STATUS_PENGEMBANGAN_MRP.md](STATUS_PENGEMBANGAN_MRP.md). Desain dasar berasal dari PDF pengguna “Dokumentasi Alur Kerja Sistem ERP Odoo 19 Community”; jalur SO merupakan penambahan.

### Alur toko yang HARUS dikerjakan lebih dulu

- **Setiap SKU mempunyai dapur produksi tetap**; gudang **Packing** adalah tempat konsolidasi hasil produksi lintas dapur dan distribusi, bukan dapur penghasil SKU.
- **1 dokumen RO per toko per dapur** (dalam siklus/jadwal permintaan terkait), dapat berisi banyak SKU dapur itu. Contoh toko memerlukan barang dari **8 dapur → 8 dokumen RO**; jangan membuat satu RO gabungan semua dapur. Rincian kunci tanggal/jadwal per dokumen masih perlu difinalkan.
- **Entry melalui template Excel .xlsx per dapur**: Reference | Nama Produk | Qty Pesan. Daftar 50–200 SKU sudah terisi dari master produk; operator **hanya mengisi Qty Pesan**, lalu unggah. Reference menjadi kunci SKU; verifikasi kecocokan dapur. Untuk kosong/0, duplikat, invalid qty dan upload ulang, rancang validasi yang jelas sebelum coding.
- Konsolidasi **semua RO toko per dapur + jadwal produksi + SKU**, terapkan batas kapasitas PPIC dan kelipatan BoM, **prorata** kuantitas toko jika perlu, lalu hasilkan **satu MO per SKU/jadwal/dapur** sesuai hasil konsolidasi (bukan MO per RO).
- Pisahkan dan simpan **Qty Requested**, **Qty Allocated**, **Qty Delivered** untuk setiap toko/SKU. Permintaan asli tidak dihapus jika alokasi berkurang.
- Hasil fisik: **Dapur → Transit → Packing → Transit → Toko**, dengan validasi pengiriman/penerimaan sesuai tahapan yang nanti diuji.

### SO adalah tahap tambahan SETELAH alur RO matang

- SO lazimnya dibuat **2–3 hari sebelum tanggal pengiriman** dengan volume sekitar **10–50 order/hari**, bukan transaksi instan seperti POS.
- Satu SO dapat berisi SKU dari banyak dapur. **Confirm seluruh SO atau gagal seluruhnya**: semua baris harus lolos; jangan reservasi parsial.
- **Validasi PERTAMA pada Confirm SO:** status **Production Schedule** dan **Delivery Schedule** yang relevan harus **Open**. Jika salah satunya **Locked**, tolak konfirmasi tanpa perlu mengecek kapasitas lebih lanjut. Status MO sudah diterbitkan **tidak sama** dengan jadwal Locked.
- Jika Open, cek kapasitas masing-masing SKU/dapur/jadwal, termasuk kapasitas toko yang masih bisa dialihkan dan batas kelipatan BoM.
- **SO lebih prioritas dari RO toko.** Walau MO sudah terbit, SO baru bisa mengambil **seluruh alokasi toko yang belum dikirim** selama jadwal masih Open dan memang cukup kapasitas; **prorata toko dijalankan otomatis tanpa persetujuan PPIC**.
- **Barang yang sudah dikirim dari Packing ke Transit tidak boleh diambil melalui realokasi biasa.** Jika pengiriman/picking masih belum Done, desain harus menangani pelepasan reservasi dengan benar; kuantitas Delivered tidak berubah.
- Pastikan tidak ada **MO ganda** dari konfirmasi SO standar/MTO sekaligus engine konsolidasi khusus. Konfirmasi, pengecekan lock, reservasi kapasitas seluruh SKU dan prorata toko harus konsisten satu transaksi.

### Jangan memutuskan aturan yang belum disetujui pengguna

Belum diputuskan: siapa yang membuat/mengunci/membuka jadwal, apakah RO boleh direvisi setelah lock, hubungan beberapa jadwal produksi dalam satu RO, pilihan jadwal jika SKU dalam SO berbeda dapur, exception hasil MO kurang, detail kebijakan SO dibatalkan/diubah, dan alur shortage setelah sebagian barang dikirim. Jangan membuat keputusan diam-diam.

### Batas pelaksanaan

**Belum ada addon/skrip khusus RO/Allocation Engine yang dikerjakan, belum ada konfigurasi/rute/DB yang diubah oleh diskusi ini, dan belum ada tes implementasi.** Langkah terdekat adalah menyelesaikan detail RO Excel per dapur dan konsolidasi toko dahulu, kemudian **hanya bila diminta** buat implementasi di DB erp-yussyakmal-mrp-test dengan tes kecil/rollback. Tidak perlu audit besar ulang struktur Odoo default.

## 3. Yang sudah selesai

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

## 4. Bukti tes terbaru: 3 SKU → 3 Scrap → 1 Batch (PASS)

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

## 5. Masih harus diuji (jangan klaim PASS)

1. **Impor Excel Draft:** jalankan `script/test_multi_scrap_xlsx_rollback_ya.py` dan cek data SKU sampel script dahulu; lakukan juga tes impor tiga SKU melalui UI.
2. **Alur GUI:** dokumen Draft, tambah manual, template unduh, impor, validasi, buka 3 native scraps via smart button.
3. **Pembatasan alasan UI:** pastikan user biasa tidak bisa membuat alasan baru pada field header, dan tag master tetap bisa dipilih.
4. **Error handling:** SKU tidak ditemukan / duplikat, UoM tak kompatibel, Qty nol/negatif, satu baris gagal -> seluruh dokumen tidak posting parsial.
5. **Batasan yang belum diuji:** barang ber-lot/serial, multi-company, laporan akuntansi kerugian Scrap, penerapan pada gudang/toko lain, hak akses operasional.

**Bukan tugas sekarang:** mengulang audit Scrap versus Opname, mengulang impor BoM, atau merancang policy yang tidak diminta.

## 6. Langkah teknis aman

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

## 7. Pesan singkat untuk sesi berikut

> Lanjutkan ODOO FROM ZERO dari **desain Replenishment Toko (RO) dahulu**, bukan dari SO: **satu RO per toko per dapur, multi-SKU**, template Excel **Reference/Nama Produk/Qty Pesan** dengan operator hanya mengisi Qty, lalu **konsolidasi toko per dapur/SKU/jadwal → kapasitas PPIC + BoM → prorata toko → MO per SKU**. Gudang Packing menjadi titik konsolidasi hasil dan pengiriman. **SO adalah tambahan berikutnya**: multi-SKU lintas dapur, semua baris harus lolos, **cek Production/Delivery Schedule Open sebagai langkah pertama saat Confirm**, SO dapat mengambil alokasi toko yang belum dikirim walau MO sudah dibuat, dan **prorata otomatis tanpa approval PPIC**; SO biasa 10–50/hari dengan lead time 2–3 hari. **Semua ini baru desain, belum addon atau tes.** Modul `ya_scrap_multi` sebelumnya telah installed dan lulus E2E 3 native Scrap rollback; **Excel/GUI masih pending**. Baca bagian desain terbaru di `doc/STATUS_PENGEMBANGAN_MRP.md`; jangan ulangi audit default, jangan ubah policy tanpa keputusan pengguna, dan **jangan sentuh DB utama/Purchasing test**.
