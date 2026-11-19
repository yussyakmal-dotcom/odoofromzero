# Pembaruan Kategori YA — Master C

Skrip: `script/update_kategori_ya_v2.py`

Sumber: `MASTER CONFIG/C_Kategori_Produk_Import.csv` (64 kategori).

Database: `erp-yussyakmal` — Odoo 19 Community.

**Prasyarat baru (disetujui Feri):** tiga akun BOP 5121035, 5121036, 5121037 harus ditambah melalui `script/tambah_3_akun_bop.py` sebelum impor kategori. Referensi tambahan tersimpan di `coa_migration/COA_04_Tambahan_BOP.csv`. Total akun setelahnya: 489. Skrip kategori otomatis menolak APPLY jika syarat belum terpenuhi.

## Tahap awal — Tambah tiga akun BOP

Preview:

```bash
cd ~/odoofromzero
git pull
sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell \
  -c /etc/odoo19.conf -d erp-yussyakmal --no-http \
  < script/tambah_3_akun_bop.py > bop_preview.txt 2>&1
tail -n 30 bop_preview.txt
```

Setelah `BOP_PREVIEW_OK`, APPLY:

```bash
sudo -u odoo19 env BOP_APPLY=YES \
  /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell \
  -c /etc/odoo19.conf -d erp-yussyakmal --no-http \
  < script/tambah_3_akun_bop.py > bop_result.txt 2>&1
tail -n 30 bop_result.txt
```

Lanjutkan pembaruan kategori hanya setelah `BOP_IMPORT_SUCCESS`.

Perbandingan dengan kategori yang sudah berhasil diimpor:

- 45 kategori baru: 29 subkategori `All / Bahan Baku`, 16 kategori lain.
- 19 kategori sama dengan master sebelumnya.
- Seluruh pengaturan `Force Removal Strategy` (termasuk pada `Premix` dan `Barang Trading`) **dilewati** sesuai keputusan Feri. Tidak ada konfigurasi FIFO/FEFO yang diubah.
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

**Jangan jalankan APPLY bila preview belum sukses.** FIFO/FEFO ditunda; skrip tidak memerlukan model `stock.removal.strategy` dan tidak mengatur strategi pengambilan stok.

## APPLY setelah preview sukses

```bash
cd ~/odoofromzero
sudo -u odoo19 env KATEGORI_V2_APPLY=YES \
  /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell \
  -c /etc/odoo19.conf -d erp-yussyakmal --no-http \
  < script/update_kategori_ya_v2.py > kategori_v2_result.txt 2>&1
tail -n 40 kategori_v2_result.txt
```

Harapkan `KATEGORI_V2_IMPORT_SUCCESS: 45 kategori ditambah; FIFO/FEFO tidak diubah; tidak ada penghapusan.`

Skrip menggunakan satu transaksi: jika gagal, seluruh perubahan tahap ini di-rollback. Skrip dapat di-preview ulang: kategori yang sudah ada dicocokkan berdasarkan jalur induk, bukan hanya nama.

## Bahan baku di setiap gudang

`Product Category` bersifat satu struktur bersama seluruh gudang. Bahan baku yang sama dapat punya stok di CDC, dapur, atau gudang lain, tetapi kategori produknya tidak perlu digandakan. Pengaturan per gudang dilakukan **sesudah master gudang** dengan lokasi stok, rute/operation type, putaway/removal, dan mapping produk–lokasi sesuai kebutuhan. Perhatikan strategi pada kategori mengalahkan strategi removal lokasi ketika keduanya disetel.
