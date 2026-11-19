# Impor kategori YA - Odoo 19 Community

Skrip `import_kategori_ya.py` membaca `MASTER CONFIG/Kategori_Produk_Import.csv` dan mengimpor 22 kategori aktif; membuat satu induk `All`, sehingga ada 23 kategori baru. Tiga kategori bawaan Odoo tetap ada. Dua kategori standby `Cadangan 1` dan `Cadangan 2` pada Excel Rev2.0 tidak ikut impor karena memang tidak ada pada CSV aktif.

**Perubahan Odoo 19:** Kolom `Stock Input Account` dari file lama tidak dipakai secara otomatis. Kategori memakai AVCO (`average`), perpetual valuation (`real_time`), akun persediaan, HPP, dan pendapatan dari COA YA. Akun perubahan persediaan mengambil akun default Odoo yang dipakai kategori `Goods`; catat kode yang muncul saat preview, dan evaluasi penempatannya dalam laporan akuntansi sebelum transaksi sungguhan.

## Preview (tidak mengubah database)

```bash
cd ~/odoofromzero
git pull
sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell -c /etc/odoo19.conf -d erp-yussyakmal --no-http < script/import_kategori_ya.py > kategori_preview.txt 2>&1
tail -n 30 kategori_preview.txt
```

**Berhenti dulu di sini dan tinjau output.** Jika muncul `KATEGORI_PREVIEW_OK`, periksa bahwa nilai perhitungan biaya, valuasi, akun, dan jumlah kategori sesuai. Jika muncul error, jangan lanjut.

## Impor setelah preview disetujui

```bash
cd ~/odoofromzero
sudo -u odoo19 env KATEGORI_APPLY=YES /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell -c /etc/odoo19.conf -d erp-yussyakmal --no-http < script/import_kategori_ya.py > kategori_import_result.txt 2>&1
tail -n 30 kategori_import_result.txt
```

Jika berhasil, muncul `KATEGORI_IMPORT_SUCCESS`. Perubahan disimpan sekaligus setelah pemeriksaan jumlah kategori; kegagalan menyebabkan rollback.

**Belum mencakup:** rute Buy/Manufacture, tipe produk, flags pembelian/penjualan/POS, pelacakan lot, custom field `x_item_type`, akun selisih opname spesifik, dan aturan konsinyasi. Hal-hal tersebut ditangani pada master produk, rute, atau konfigurasi berikutnya. Kategori konsinyasi hanya aman setelah prinsip barang milik vendor dan nilai stok Rp 0 diterapkan pada produk dan alurnya.
