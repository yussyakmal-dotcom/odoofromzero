# Pembaruan Kategori YA — Master C

Skrip: `script/update_kategori_ya_v2.py`

Sumber: `MASTER CONFIG/C_Kategori_Produk_Import.csv` (64 kategori).

Database: `erp-yussyakmal` — Odoo 19 Community.

Perbandingan dengan kategori yang sudah berhasil diimpor:

- 45 kategori baru: 29 subkategori `All / Bahan Baku`, 16 kategori lain.
- 19 kategori sama dengan master sebelumnya.
- Dua kategori lama (`Premix`, `Barang Trading`) mendapat strategi FEFO sesuai master revisi.
- Tiga kategori lama (`Cake Loyang Sudirman`, `Roti Sudirman`, `Dahlia 5`) tidak ditemukan lagi pada master baru; **tetap disimpan**, tidak dihapus otomatis.
- Stok Input Account dari CSV tidak diterapkan karena field lama tersebut tidak tersedia pada Odoo 19; akun variasi stok mengikuti kategori `All / Bahan Baku` yang sudah diimpor.

## Jalankan preview

```bash
cd ~/odoofromzero
git pull
sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell \
  -c /etc/odoo19.conf -d erp-yussyakmal --no-http \
  < script/update_kategori_ya_v2.py > kategori_v2_preview.txt 2>&1
tail -n 40 kategori_v2_preview.txt
```

Pastikan muncul `KATEGORI_V2_PREVIEW_OK` sebelum APPLY. Preview tidak menyimpan data.

Jika muncul pesan `Strategi ... belum tersedia`, aktifkan fitur `Lots & Serial Numbers` dan `Expiration Dates` pada pengaturan Inventory terlebih dahulu. **Jangan jalankan APPLY bila preview belum sukses.** FEFO memerlukan pelacakan lot dan tanggal kedaluwarsa pada masing-masing produk; strategi kategori saja tidak otomatis memberi tanggal kedaluwarsa.

## APPLY setelah preview sukses

```bash
cd ~/odoofromzero
sudo -u odoo19 env KATEGORI_V2_APPLY=YES \
  /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell \
  -c /etc/odoo19.conf -d erp-yussyakmal --no-http \
  < script/update_kategori_ya_v2.py > kategori_v2_result.txt 2>&1
tail -n 40 kategori_v2_result.txt
```

Harapkan `KATEGORI_V2_IMPORT_SUCCESS: 45 kategori ditambah, 2 strategi lama diperbarui; tidak ada penghapusan.`

Skrip menggunakan satu transaksi: jika gagal, seluruh perubahan tahap ini di-rollback. Skrip dapat di-preview ulang: kategori yang sudah ada dicocokkan berdasarkan jalur induk, bukan hanya nama.

## Bahan baku di setiap gudang

`Product Category` bersifat satu struktur bersama seluruh gudang. Bahan baku yang sama dapat punya stok di CDC, dapur, atau gudang lain, tetapi kategori produknya tidak perlu digandakan. Pengaturan per gudang dilakukan **sesudah master gudang** dengan lokasi stok, rute/operation type, putaway/removal, dan mapping produk–lokasi sesuai kebutuhan. Perhatikan strategi pada kategori mengalahkan strategi removal lokasi ketika keduanya disetel.
