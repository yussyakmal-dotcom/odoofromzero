# YA Purchase Multi-UoM — tahap 1

Modul Odoo 19 ini menyimpan konversi **per SKU**, bukan konversi global.
Contoh: Dus untuk SKU A = 100 Pcs, Dus untuk SKU B = 120 Pcs.

## Lingkup saat ini

- Model `ya.purchase.uom.rule`: produk, label satuan pembelian, faktor bilangan bulat, satuan dasar (related), status.
- Validasi faktor positif dan duplikat pasangan SKU + label (abaikan kapital/spasi pinggir).
- Fungsi `to_base_quantity()` dan `price_per_base_unit()` untuk uji konversi.
- **Belum mengubah perilaku PO, transfer, penerimaan, costing, atau status jual/beli.**
- **Belum ada importer APPLY** untuk 608 kandidat.
- Master XLSX, nama produk, dan data konversi tetap di server privat.

## Pemeriksaan pada database utama (setelah persetujuan pemilik)

1. Pastikan path `~/odoofromzero/addons` ditambahkan pada `addons_path` Odoo 19.
   Jangan menimpa path addon lain. Tinjau konfigurasi terlebih dahulu.
2. Setelah modul diperiksa, instal `ya_purchase_multi_uom` di database yang
   disetujui pemilik. Instalasi membuat **tabel kosong** untuk aturan per SKU.
3. Jalankan `script/test_multi_uom_rules_ya.py` pada `erp-yussyakmal`.
   Skrip memakai `Model.new()` tanpa menyimpan record dan tanpa COMMIT.
4. Pengujian constraint duplikat saat `CREATE` dan integrasi PO/receipts tetap
   memerlukan database uji sebelum transaksi bisnis diaktifkan.

## Poin penting

Jangan menganggap relasi `product.uom` sebagai tempat faktor konversi per SKU:
model itu hanya berisi `product_id`, `uom_id`, dan barcode sesuai audit database.

Untuk modul produksi nanti, aturan perlu dilengkapi pemeriksaan perubahan satuan
dasar setelah transaksi, validasi pada PO, dan konversi penerimaan.
