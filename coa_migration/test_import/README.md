# COA YA - paket uji impor Odoo 19

Paket ini dihasilkan dari 391 akun COA YA dan dua audit read-only database `erp-yussyakmal` tanggal 19 November 2026. Audit menyatakan jumlah `account.move`, `account.move.line`, dan `stock.move` semuanya nol pada saat pemeriksaan.

**STATUS: SIAP UNTUK TEST IMPORT DI DATABASE UJI / SALINAN, BELUM DIIZINKAN UNTUK LANGSUNG IMPOR PRODUKSI.** Lakukan backup database terlebih dahulu; uji setiap tahap dan pastikan kode tetap unik.

1. `TEST_COA_00_Release_Code.csv`: ubah kode akun Outstanding Payments pada record Odoo asli dari `11120004` menjadi `11120005`. Satu record.
2. `TEST_COA_01_Update_Existing.csv`: pembaruan 21 akun Odoo berdasarkan External ID, termasuk memindahkan kode Outstanding Receipts menjadi `11120004`, rekening suspense, piutang, utang, dan jenis pinjaman jangka panjang.
3. `TEST_COA_02_Create_New.csv`: buat 368 akun YA yang belum ada, termasuk akun Stock Interim Received `2171091` dan Delivered `1130019`.
4. Akun laba tahun berjalan `99999900` dipertahankan tanpa pembaruan.

Sisa akun bawaan Odoo yang tidak termasuk master YA **tidak dihapus atau diarsipkan** pada paket ini. Akun bawaan `29000000` juga tidak disentuh; kategori produk/valuasi persediaan baru disesuaikan setelah COA terverifikasi.

Sebelum setiap tahap, gunakan menu Accounting > Configuration > Chart of Accounts > Import untuk **Test Import**, pilih pemetaan kolom dengan benar, lalu jalankan impor hanya jika hasil uji valid. Simpan hasil ekspor ulang akun Odoo setelah semua tahap. Untuk kolom `Type`, file berisi nilai teknis selection Odoo 19; bila pemetaan UI menolak nilai tersebut, hentikan dan kirim hasil error, jangan menebak atau mengubahnya manual.

**Catatan teknis:** Paket ini belum mengubah konfigurasi perusahaan `My Company`, jurnal bank, atau kategori default yang masih menggunakan valuation periodik. Langkah konfigurasi itu dilakukan dan diverifikasi secara terpisah.

Regenerasi: `python3 script/build_coa_test_files.py MASTER_CSV MASTER_AUDIT DEPENDENCY_AUDIT OUTPUT_DIR`.
