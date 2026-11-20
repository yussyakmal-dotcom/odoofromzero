# YA Partner Phone 2 — Odoo 19

Menambahkan `res.partner.ya_phone2` di samping `phone` pada form kontak.

- Berlaku untuk semua mitra (supplier, customer, konsinyasi).
- Tidak mengubah transaksi pembelian, penjualan, atau akuntansi.
- Diuji dan dipasang di `erp-yussyakmal-integer-test` terlebih dahulu.
- Importer `script/import_master_mitra_ya.py` mewajibkan modul ini terpasang.

Pemasangan: salin folder modul ke `/opt/odoo19/custom-addons/`, pastikan
terbaca user `odoo19`, lalu jalankan instalasi modul melalui `odoo-bin -i`.
