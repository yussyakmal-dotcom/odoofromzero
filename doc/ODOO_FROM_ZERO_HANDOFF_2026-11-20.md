# ODOO FROM ZERO — Handoff Proyek
**Tanggal:** 20 November 2026 WIB  
**Pemilik pekerjaan teknis/server:** Feri  
**Repository:** https://github.com/yussyakmal-dotcom/odoofromzero

> Sumber: keputusan dan hasil log yang dibagikan Feri selama percakapan panjang. Ini bukan audit live server. Sebelum mengubah database, cek keadaan aktual dan lakukan PREVIEW. Feri telah **secara eksplisit mengizinkan** publikasi metadata teknis server/database pada repository publik. Jangan masukkan password, secret, token, isi daftar vendor, atau file sumber privat ke GitHub.

## A. Lingkungan

- Ubuntu 24, Odoo 19 Community source install.
- Python: `/opt/odoo19/venv/bin/python3`
- Bin: `/opt/odoo19/odoo/odoo-bin`
- Config: `/etc/odoo19.conf`
- Service OS: `odoo19.service`, OS user `odoo19`
- Addon custom: `/opt/odoo19/custom-addons`, disalin dari folder `addons/` repo.
- Log Odoo: `/var/log/odoo19/odoo19.log`; jika proses upgrade keluar **255** tetapi stdout kosong, periksa file ini.
- **DB utama:** `erp-yussyakmal` — jangan gunakan untuk uji coba belum lulus.
- **DB test:** `erp-yussyakmal-integer-test`.
- Snapshot terdahulu `erp-yussyakmal-master-v1`; pernah terlihat database `ya_erp`.
- Upgrade modul via CLI `-u` pada database test, kemudian **restart service Odoo** sebelum memeriksa UI agar registry proses web ikut memuat field Python baru.

## B. Master yang sudah berjalan

| Master | Hasil audit/log |
|---|---|
| COA YA | 391 kode YA; total 486 akun termasuk bawaan. Tambahan 3 akun BOP (5121035, 5121036, 5121037) berhasil → total **489** akun. |
| Kategori | Revisi kategori, tambahan Paket, Gas, dll. Total terakhir **76 kategori**. |
| Gudang | **30 warehouse**, 64 stock locations, 90 operation types (30 incoming, 30 internal, 30 outgoing), audit issues 0. CDC pusat, PCK packing, dapur, toko, KONS titipan. Rute khusus **ditunda**. |
| Produk | **2.543 SKU YA**. Audit pasca-impor 2.543 cocok, mismatch 0, stok/transaksi 0 saat audit. POS kemudian menambah produk teknis `TIPS` dan `Down Payment (POS)`; jangan memakai total semua `product.product` untuk mengukur 2.543 SKU YA. |
| UoM dasar | Impor satuan untuk 2.543 SKU (26 jenis dari Excel, 23 UoM baru). Koreksi 12026 ke Toples, 11234 ke Pcs, 50 SKU filling Premix/WIP ke Gram. |
| Konversi PO | **608 aturan** impor dari 754 baris Excel privat, 607 SKU unik. Audit ulangan 608 cocok, tambah 0. Pada DB test pernah ditambah aturan 10840 Cabe Jengki: 1 Kg=1000 Gram. |
| Vendor | **561 partner** impor pada **DB test**, audit `MITRA_AUDIT_OK` tanpa temuan; 175 penanda CS, 13 telepon kedua, 37 telepon ambigu disimpan di catatan. Belum dapat diasumsikan terimpor ke DB utama. |

Sumber master privat berada di server; jangan dipublikasikan. Produk awalnya seluruhnya purchase_ok/sale_ok False. Di test, 683 produk kategori Bahan Baku telah diaktifkan pembeliannya. Kuantitas BOM/proses wajib integer sesuai SOP. Satuan dasar = satuan terkecil yang dipakai **oleh SKU tersebut** (contoh sabun botol tidak perlu ml). Pembelian 2,5 kg dilakukan sebagai dua line (2 Kg + 500 Gram); konversi antar satuan dapat lintas besaran hanya **per SKU** dan dikendalikan faktor, bukan global.

Paket = SKU produksi di Dapur Packing yang menggabungkan beberapa produk jadi melalui BoM, lalu masuk PCK/Stock sebelum distribusi. Berbeda dari pesanan multi-item yang hanya diberi kemasan. FEFO/FIFO dan rute gudang belum diputuskan/diterapkan otomatis.

## C. Modul custom dan status

1. **`ya_purchase_multi_uom`**: `ya.purchase.uom.rule` dengan produk, label satuan beli, integer faktor, UoM dasar, active, company. Mendukung beberapa unit pembelian SKU (misal Sak/Kg/Gram) dihitung langsung relatif ke satuan dasar; satu PO mengontrol ekuivalensi harga antarsatuan, **tidak** mengikat harga lintas supplier. PO UI akhirnya menyederhanakan kolom Product, Quantity, Unit, Unit Price, Taxes, Amount. Riwayat aturan yang dipakai PO tidak boleh diedit faktor/identitas; arsipkan dan buat aturan baru.
2. **`ya_integer_quantity`**: pemeriksaan integer pada Purchasing, Inventory, Sales, POS, Manufacturing/BoM. Pengujian virtual dan CREATE/WRITE PO, stock.move, SO, BoM, MO di DB test berhasil dengan rollback. Pengaturan digits UI `Product Unit of Measure` pernah diubah Feri menjadi 0; itu hanya presentasi, bukan jaminan semua alur divalidasi.
3. **`ya_purchase_discount`**: Discount PO UX gaya Sales (wizard) mendukung persen atau Rupiah; per-line dan global **eksklusif**. Uji hitungan dan ORM wizard berhasil. Masalah izin wizard dulu sudah diperbaiki dan Feri menyatakan UI oke.
4. **`ya_partner_phone2`**: menambahkan `res.partner.ya_phone2` karena field `mobile` pada instalasi tidak ada. Terpasang di DB test, field diuji tersedia.
5. OCA Accounting serta Inventory/Purchase/Sales/POS/MRP diinstal bertahap; jangan anggap seluruh konfigurasi operasional/rute sudah siap.

## D. Masalah terakhir dan keputusan UI Multi-UoM (BELUM SELESAI)

Feri meminta:
- Filter kategori pada **Master Multi-UoM YA** (fokus Bahan Baku dan Packaging), **bukan penguncian SKU** menurut `purchase_ok`.
- Filter `Dapat Dibeli` boleh ada namun opsional dan dapat dilepas; aturan konversi produk yang `purchase_ok=False` tetap harus dapat dimasukkan/edit.
- Impor/ekspor XLSX standar Odoo untuk **tambah dan update**. Ketika update wajib mempertahankan External ID; uji `Test` pada importer, mulai dari beberapa baris di DB test.
- SKU baru harus dapat dikelola langsung dari master, tanpa perlu developer.

Perubahan repo `addons/ya_purchase_multi_uom`:
- `models/purchase_uom_rule.py`: related stored `product_categ_id` ke `product_id.categ_id`.
- `views/purchase_uom_rule_views.xml`: kolom kategori, pencarian, filter opsional Dapat Dibeli, group-by kategori; domain pemilih SKU dibebaskan.
- `README.md`: panduan fitur XLSX Odoo.
- Commit terakhir untuk perbaikan view: `2789f2e`.

**Error yang dialami:**
1. Upgrade test pernah `UPGRADE_EXIT_CODE=255`, log output redirect kosong. Di log Odoo: `ParseError` karena `<group expand="0">` tidak valid pada search XML. Sudah diganti pada commit `2789f2e` dengan filter group-by sederhana.
2. Feri kemudian membuka Master Multi-UoM dan mendapat **OwlError `"ya.purchase.uom.rule"."product_categ_id" field is undefined`**. Field pada UI tidak dikenali registry web saat itu. Status masalah **belum dikonfirmasi beres**. Asisten menyarankan restart service sesudah upgrade sukses, hard refresh, lalu cek ORM apakah field terdaftar. **Belum ada hasil pemeriksaan dikirim**.
3. Screenshot sebelumnya dengan judul `Categories` merupakan master kategori produk, bukan master aturan UoM. Jangan salah diagnosis menu.

**Langkah pertama ketika lanjut percakapan:** cek output upgrade terbaru + restart service; jika masih gagal, inspeksi di DB test:
```python
m = env["ya.purchase.uom.rule"]
print("DATABASE:", env.cr.dbname)
print("FIELD KATEGORI:", "product_categ_id" in m._fields)
print("JUMLAH ATURAN:", m.search_count([]))
```
Jangan menganggap perbaikan selesai sebelum UI list/form dan filter kategori diuji.

## E. Keputusan deployment database

Feri bertanya menyalin database atau langsung membangun `erp-yussyakmal`. Keputusan kerja: stabilisasi modul custom **di DB test lebih dulu**, kemudian duplikasi DB utama ke checkpoint baru (mis. `erp-yussyakmal-pre-custom-v1`) menggunakan Database Manager Odoo, lalu upgrade modul yang sudah lulus di utama dengan audit pasca upgrade.

**Penting:** perubahan data yang ada di DB test (terutama 561 vendor dan aturan tambahan test) **tidak otomatis pindah** dengan `git pull` atau upgrade kode. Harus ada impor data dan verifikasi eksplisit; jangan menimpa DB utama dengan salinan DB test tanpa keputusan dan audit. Route gudang tetap ditunda.

## F. Perintah standar

```bash
cd ~/odoofromzero
git pull
sudo cp -a addons/ya_purchase_multi_uom/. /opt/odoo19/custom-addons/ya_purchase_multi_uom/

sudo -u odoo19 /opt/odoo19/venv/bin/python3 \
  /opt/odoo19/odoo/odoo-bin \
  -c /etc/odoo19.conf \
  -d erp-yussyakmal-integer-test \
  -u ya_purchase_multi_uom \
  --stop-after-init --no-http \
  > multi_uom_upgrade_test.txt 2>&1
echo "UPGRADE_EXIT_CODE=$?"

# Bila gagal, lihat log (CLI dapat diam)
sudo tail -n 100 /var/log/odoo19/odoo19.log

# Bila sukses, refresh registry proses web
sudo systemctl restart odoo19.service
sudo systemctl is-active odoo19.service
```

## G. Saat pindah ke chat baru

Salin pesan:

> Kita lanjut **ODOO FROM ZERO**. Saya **Feri**. Baca seluruh dokumen `doc/ODOO_FROM_ZERO_HANDOFF_2026-11-20.md` di `yussyakmal-dotcom/odoofromzero` terlebih dahulu. Jangan asumsikan masalah terakhir selesai: UI Master Multi-UoM sebelumnya error `product_categ_id field is undefined`. Fokus stabilisasi UI master, uji filter kategori dan ekspor/impor XLSX pada `erp-yussyakmal-integer-test`; jangan ubah DB utama tanpa uji, snapshot, dan persetujuan. Catat hasil baru ke dokumen handoff agar konteks tidak hilang.

Setelah setiap milestone, perbarui file ini dengan tanggal, versi/commit, DB target, hasil tes, status `OK/BELUM`, dan langkah berikutnya.

## H. Pembaruan 20 November 2026 — Modul Receiving dalam pengembangan

Feri memutuskan Multi-UoM juga dipakai saat **penerimaan fisik**: beberapa baris untuk satu SKU, unit Dus/Kg/Gram sesuai kemasan, kuantitas integer, konversi otomatis ke unit dasar saat menerima, laporan mempertahankan jumlah/unit fisik. Penerimaan kurang dianggap **selesai tanpa backorder**; pengiriman berikutnya memakai PO baru; Vendor Bill mengikuti received quantity.

Audit `script/audit_multi_uom_receiving_ya.py` pada test:
- PO `P00009` SKU 10164: 25 Kg→25.000 Gram dan 500 Gram→500 Gram.
- Receipt `CDC/IN/00001`: assigned, 2 stock.move / 2 stock.move.line, tujuan CDC/Stock, belum Validate.
- `stock.picking.type` CDC incoming id=1 `create_backorder=ask` (opsi ask/always/never).
- `purchase_method=receive`, `qty_received_method=stock_moves`, benar.
- 3.158 aturan Multi-UoM pada test (termasuk aturan base).

Audit hook `script/audit_receiving_hooks_ya.py` menunjukkan form `stock.view_picking_form`, tombol `button_validate`, field `stock.move.quantity` computed/editable, `stock.move.line.quantity` computed/editable. **Tidak aman memodifikasi quantity tanpa tes integrasi**.

**Kode baru ditulis (BELUM DIINSTAL/DIUJI di Odoo server):** addon
`addons/ya_multi_uom_receiving/`, plus
`script/test_multi_uom_receiving_orm_ya.py` yang melakukan CREATE/APPLY hanya pada DB test lalu **ROLLBACK**. Addon menyimpan baris satuan fisik per stock.move dengan faktor/label snapshot, menyediakan tab di Receipt dan tombol `Apply Satuan Fisik`, memvalidasi sebelum tombol Validate; menuntut policy backorder `never` untuk PO receipts. Belum dipromosikan ke DB utama.

Pemeriksaan sintaks Python/XML dan tes matematika awal di lingkungan pengembangan **lulus**, tetapi itu **belum membuktikan integrasi ORM**. Tahap berikut: Feri `git pull`, jalankan unittest, compile, salin addon, instal **hanya di `erp-yussyakmal-integer-test`**, jalankan rollback ORM test, kirim log. Jika install/test gagal, perbaiki modul sebelum uji UI dan sebelum Validate Receipt. Jangan ubah CDC backorder hingga uji dikonfirmasi.
