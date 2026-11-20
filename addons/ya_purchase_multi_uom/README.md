# YA Purchase Multi-UoM — integrasi PO tahap uji

Modul Odoo 19 ini menyimpan konversi **per SKU**, bukan konversi global.
Contoh: Dus untuk SKU A = 100 Pcs, Dus untuk SKU B = 120 Pcs.

## Lingkup saat ini

- Model `ya.purchase.uom.rule`: produk, label satuan pembelian, faktor bilangan bulat, satuan dasar (related), status.
- Validasi faktor positif dan duplikat pasangan SKU + label (abaikan kapital/spasi pinggir).
- Fungsi `to_base_quantity()` dan `price_per_base_unit()` untuk uji konversi.
- Master 608 aturan sudah diimpor melalui `script/import_konversi_purchase_ya.py`.
- Integrasi PO v19.0.1.1.0 (belum diuji): menambah kolom `Satuan Pembelian YA`,
  `Qty Pembelian YA`, dan `Harga/Satuan Pembelian YA` pada baris PO.
- Onchange mengonversi Qty dan harga pembelian ke field Odoo `product_qty` dan
  `price_unit` dalam **satuan dasar SKU**, misalnya 2 Dus = 200 Pcs.
- Validator menolak konversi yang tidak konsisten ketika PO disimpan. Tanpa
  aturan YA, perilaku PO standar tidak berubah.
- Master XLSX, nama produk, dan data konversi tetap di server privat.

## Uji pada database duplikat

1. Upgrade modul hanya pada `erp-yussyakmal-integer-test`.
2. Periksa bahwa kolom baru muncul di PO dan terfilter menurut SKU.
3. Uji perhitungan 2 Dus ke 200 Pcs dan harga per satuan dasar.
4. Uji PO confirmation, Receipt CDC, dan akuntansi dengan record uji.
5. Jangan aktifkan transaksi bisnis sampai seluruh alur lulus.

## Poin penting

Jangan menganggap relasi `product.uom` sebagai tempat faktor konversi per SKU:
model itu hanya berisi `product_id`, `uom_id`, dan barcode sesuai audit database.

**Penting:** integrasi UI dan penerimaan belum diuji. Modul ini tidak
boleh dianggap lengkap hanya karena upgrade CLI berhasil.
