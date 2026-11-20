# YA Multi-UoM Receiving — Operations bawaan Odoo 19

**STATUS: revisi UI menunggu upgrade dan uji ulang pada `erp-yussyakmal-integer-test`. JANGAN install pada `erp-yussyakmal` utama.**

## Alur UX yang disepakati Feri

- Satu daftar barang: tab **Operations** stock.picking bawaan Odoo.
- Baris PO/produk muncul otomatis; petugas **tidak memilih ulang SKU atau move**.
- **Demand** menampilkan kuantitas beserta satuan asli PO, misalnya **25 Kg** (bukan 25.000 tanpa label).\n- Setiap baris mempunyai input **Quantity** fisik (integer) dan **Unit** dari master konversi SKU.
- Saat **Validate**, quantity fisik dikali faktor dan disimpan sebagai `stock.move.quantity` satuan dasar.
- Unit fisik dan jumlah asli disalin ke `stock.move.ya_received_unit_label` dan `ya_received_unit_qty` untuk keperluan laporan.
- Tidak ada tab penerimaan tambahan atau tombol Apply.
- Dua unit berbeda untuk SKU sama dapat digunakan lewat dua baris PO/move yang berbeda. Contoh: 20 Kg + 500 Gram.
- Qty diterima boleh kurang dari atau sama dengan Demand; pembatasan dibandingkan setelah semua satuan dikonversi ke satuan dasar. Penerimaan melebihi demand per baris ditolak; kekurangan diterima sebagai final tanpa backorder jika operation type Incoming CDC memakai `create_backorder=never`.
- Jangan mengaktifkan kebijakan no-backorder permanen tanpa pengujian dan persetujuan; modul menolak Validate pada receipt PO jika setting masih bukan `never`.

**Perhatian:** kolom `Unit` fisik YA bukan `product_uom` stok. UoM stok tetap Gram/Pcs/dll sesuai master. Qty awal input fisik diset 0 agar petugas memasukkan qty yang benar-benar datang, bukan otomatis menganggap seluruh pesanan sudah diterima.

Model `ya.receipt.unit.line` lama tetap disertakan sementara untuk kompatibilitas data, tetapi tab input lamanya tidak lagi ditampilkan dan tidak digunakan pada validasi versi ini.

## Tes khusus database duplikat

1. Pull repository, salin addon ke `/opt/odoo19/custom-addons/ya_multi_uom_receiving` dengan izin baca user `odoo19`.
2. Compile dan jalankan unit test lokal.
3. Upgrade hanya pada `erp-yussyakmal-integer-test`; periksa `UPGRADE_EXIT_CODE=0` **dan log Odoo**.
4. Jalankan `script/test_multi_uom_receiving_operations_ya.py` melalui Odoo shell pada test DB; harus `OPERATIONS_RECEIVING_VALIDATE_OK` dan `ROLLBACK_COMPLETE`.
5. Uji UI Operations dalam browser pada test DB; pastikan Unit aktif, data SKU otomatis, hitungan, dan tidak ada kolom duplikat.
6. Baru uji vendor bill dan laporan unit fisik. Tidak ada perubahan pada main DB dalam tahap ini.

Tes `test_multi_uom_receiving_validate_ya.py` adalah regresi **alur tab lama**, bukan tes valid untuk antarmuka Operations yang baru.
