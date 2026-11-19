# Impor COA YA dalam satu skrip Odoo 19

Skrip: `script/import_coa_ya.py`. Membaca `MASTER CONFIG/COA_Bersih_Import.csv` dari root repository.

Skrip hanya untuk database `erp-yussyakmal` dengan satu perusahaan, 118 akun awal, dan **nol transaksi** jurnal maupun pergerakan stok. Pemeriksaan awal tersebut wajib lolos. Jika database berbeda, sudah diimpor sebagian, atau sudah ada transaksi, skrip berhenti.

Urutan dalam satu transaksi:

1. Lepaskan benturan kode: Outstanding Payments `11120004` -> `11120005`.
2. Perbarui 21 akun existing dengan tetap memakai record Odoo, termasuk Outstanding Receipts, piutang/utang, suspense, dan pinjaman jangka panjang.
3. Buat 368 akun baru YA, termasuk dua akun Stock Interim.
4. Pertahankan akun laba tahun berjalan `99999900` dan akun bawaan yang tidak termasuk 391 kode YA.
5. Verifikasi jumlah, kode, nama, tipe, dan rekonsiliasi. Jika lulus, satu commit. Jika gagal, rollback seluruh perubahan.

## Jalankan mode pemeriksaan (wajib pertama)

```bash
cd ~/odoofromzero
git pull
sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell -c /etc/odoo19.conf -d erp-yussyakmal --no-http < script/import_coa_ya.py > coa_import_preview.txt 2>&1
tail -n 20 coa_import_preview.txt
```

Mode ini tidak menulis apa pun. Pastikan ada `PREVIEW_OK` dan kirim hasilnya untuk ditinjau sebelum menjalankan impor sebenarnya.

## Jalankan impor setelah mode pemeriksaan lolos

```bash
cd ~/odoofromzero
sudo -u odoo19 env COA_APPLY=YES /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell -c /etc/odoo19.conf -d erp-yussyakmal --no-http < script/import_coa_ya.py > coa_import_result.txt 2>&1
tail -n 30 coa_import_result.txt
```

Hasil yang diharapkan adalah `COA_IMPORT_SUCCESS`. Jika terjadi kesalahan, cari `COA_IMPORT_FAILED`, jangan mengulangi impor sebelum masalah dianalisis. Tidak perlu menghentikan layanan Odoo.

**Batasan:** Skrip belum mengubah akun bawaan lain yang tidak dipetakan, nama perusahaan, pengaturan akun kategori produk, metode valuasi, jurnal bank, maupun gudang. Setelah berhasil, jalankan ulang audit untuk memastikan hasil, lalu lakukan backup sesuai rencana sebelum impor kategori dan gudang.
