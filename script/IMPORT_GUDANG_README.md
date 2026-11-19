# Impor master gudang YA ke Odoo 19

Sumber: `MASTER CONFIG/Master_Gudang_Import.csv` dengan 30 baris gudang. Skrip `import_master_gudang_ya.py` dijalankan dari root repository melalui Odoo shell.

- Baris pertama `Gudang Central / CDC` menggunakan ulang warehouse bawaan Odoo (`WH`), bukan membuat gudang ganda.
- 29 baris lain membuat warehouse baru.
- Semua kode pendek maksimal 5 karakter dan harus unik.
- Jika ada transaksi stock.move, database tidak hanya punya satu warehouse `WH`, atau impor sudah dilakukan sebagian, skrip berhenti.
- Perubahan satu transaksi: hasil valid disimpan, kesalahan menyebabkan rollback.

## Preview

```bash
cd ~/odoofromzero
git pull
sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell -c /etc/odoo19.conf -d erp-yussyakmal --no-http < script/import_master_gudang_ya.py > gudang_preview.txt 2>&1
tail -n 30 gudang_preview.txt
```

Keluaran yang diharapkan: `GUDANG_PREVIEW_OK`. **Lakukan konfirmasi jumlah dan arsitektur gudang terlebih dahulu** sebelum menjalankan impor: dalam desain ini dapur, toko dan Titipan semuanya diwakili oleh warehouse, bukan hanya sublokasi.

## Impor setelah preview diperiksa

```bash
cd ~/odoofromzero
sudo -u odoo19 env GUDANG_APPLY=YES /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell -c /etc/odoo19.conf -d erp-yussyakmal --no-http < script/import_master_gudang_ya.py > gudang_import_result.txt 2>&1
tail -n 30 gudang_import_result.txt
```

Keluaran sukses: `GUDANG_IMPORT_SUCCESS`.

**Catatan penting:** Pembuatan warehouse dalam Odoo otomatis menyiapkan lokasi, rute dan beberapa tipe operasi standar. Tahap Operation Types selanjutnya harus lebih dulu mengaudit hasil yang sudah otomatis terbentuk agar tidak membuat duplikasi. Rute CDC -> Dapur -> Packing -> Toko belum diaktifkan oleh skrip ini. Pengaturan FEFO, WIP, buffer dan konsinyasi dilakukan secara terpisah setelah struktur gudang terverifikasi.
