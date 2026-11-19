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

## Instalasi di database DUPLIKAT saja

1. Pastikan path `~/odoofromzero/addons` tercantum pada `addons_path` server Odoo 19.
   Jangan menimpa path addon lain. Tinjau konfigurasi terlebih dahulu.
2. Perbarui daftar aplikasi dan install `ya_purchase_multi_uom` pada **database duplikat**
   lewat UI Odoo, bukan `erp-yussyakmal`.
3. Jalankan `script/test_multi_uom_rules_ya.py` terhadap database duplikat.
   Skrip menjalankan uji dengan savepoint dan rollback eksplisit; tidak perlu transaksi bisnis.
4. Tinjau hasil sebelum membuat integrasi PO/receipts dan importer data.

## Poin penting

Jangan menganggap relasi `product.uom` sebagai tempat faktor konversi per SKU:
model itu hanya berisi `product_id`, `uom_id`, dan barcode sesuai audit database.

Untuk modul produksi nanti, aturan perlu dilengkapi pemeriksaan perubahan satuan
dasar setelah transaksi, validasi pada PO, dan konversi penerimaan.
