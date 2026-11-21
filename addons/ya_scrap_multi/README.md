# YA Multi-SKU Scrap — Odoo 19 Community

## Tujuan

Satu dokumen Scrap berisi **banyak SKU**, dengan **satu lokasi asal,
satu lokasi virtual Scrap tujuan, satu alasan, dan satu Source Document**.
Khusus proyek ODOO FROM ZERO: tidak menambahkan approval, pelarangan
stok negatif, atau policy lain di luar keputusan dalam proyek.

## Cara kerja

- Menu: **Inventory → Multi-SKU Scrap**.
- Buat dokumen Draft; pilih Source Location (gudang Central, dapur atau toko),
  Destination (satu virtual Scrap bersama), Reason dan Source Document.
- Tambahkan banyak baris SKU secara manual atau dari Excel.
- Klik **Validate All Scrap**. Setiap baris menciptakan record native
  `stock.scrap` menggunakan API `action_validate()` Odoo 19.
- Semua transaksi mendapatkan alasan dan dokumen asal yang sama serta
  tautan `ya_batch_id` ke dokumen induk.
- Kegagalan satu baris menggagalkan seluruh validasi, bukan commit parsial.
- Hasil stok, traceability, dan valuasi mengikuti `stock.scrap` standar.

## Excel

Gunakan tombol **Download Excel Template**. Tiga kolom:
`SKU | Quantity | UoM`.
UoM boleh kosong: otomatis menggunakan satuan dasar produk.
Impor menambahkan baris Draft; **belum mengurangi stok**.
Maksimal 1.000 baris per impor; validasi SKU unik, jumlah positif dan
kesesuaian kategori UoM. File privat tidak disimpan di GitHub.

## Prasyarat

- Odoo 19 Community dengan addons `stock`.
- Python `openpyxl` terpasang pada virtual environment Odoo.
- Satu `stock.location` dengan usage `inventory` untuk Scrap.
- Scrap Reason Tags tersedia (model `stock.scrap.reason.tag`).
- Akses grup Inventory User/Manager untuk penggunaan.

## Instalasi: test database dahulu

1. `cd ~/odoofromzero && git pull`.
2. Validasi addon di repository; deploy folder addon **hanya** ke addons
   directory aktif `/opt/odoo19/custom-addons/ya_scrap_multi`.
   Git pull saja **tidak memasang addon**.
3. Pastikan `/opt/odoo19/custom-addons` ada pada `addons_path`.
4. Instal dengan Odoo CLI hanya pada database
   `erp-yussyakmal-mrp-test`, lalu periksa traceback/exit code.
5. Jalankan `script/test_multi_scrap_xlsx_rollback_ya.py`.
6. Tes transaksi native Scrap dengan saldo stok simulasi dan rollback,
   cek stock move, native Scrap record, alasan, source document, dan
   valuasi sebelum mengaktifkan operasional.

**Status 22 November 2026:** Modul **installed** pada `erp-yussyakmal-mrp-test` dan form sudah muncul (konfirmasi pengguna). Satu virtual lokasi Scrap dan alasan Rusak/Expired sudah APPLY committed. Uji end-to-end 3 SKU -> 3 native Scrap -> 3 Stock Move dalam 1 dokumen **PASS**, rollback juga PASS (lihat `script/test_multi_scrap_3sku_e2e_rollback_ya.py`). Belum ada uji impor Excel terpisah, GUI operasional penuh, atau deployment ke DB utama.

## Keputusan belum dibuat

- Perlu tidaknya alasan lain di luar Rusak dan Expired.
- Apakah Source Document dikaitkan ke MO, POS, Delivery Order dan sebagainya.
- Kebijakan penerimaan dan penolakan selisih stok.
- Role approval atau tahapan audit.

## Handover terbaru

- [Handover ODOO FROM ZERO](../../doc/HANDOVER_ODOO_FROM_ZERO.md)
- [Status Pengembangan Manufacturing](../../doc/STATUS_PENGEMBANGAN_MRP.md)
