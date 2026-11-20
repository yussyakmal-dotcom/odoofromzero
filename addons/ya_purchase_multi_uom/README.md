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

## Pemeliharaan master lewat Excel (Odoo 19)

Pada **Purchase → Configuration → Master Multi-UoM YA**, daftar dapat **difilter atau dikelompokkan berdasarkan Kategori Produk**. Pilih kategori
induk, misalnya Bahan Baku atau Packaging, untuk memeriksa aturan SKU terkait.
Filter **Dapat Dibeli** tetap tersedia secara opsional, tetapi tidak aktif otomatis.
**Tidak ada pembatasan SKU** pada form tambah/edit: produk dengan `purchase_ok=False`
tetap boleh dipelihara aturan satuannya. Mengaktifkan pembelian tetap dilakukan
melalui master produk, bukan otomatis oleh pengaturan Multi-UoM.

**Ekspor / pembaruan massal:**

1. Masuk sebagai **Purchase Manager**. Buka Master Multi-UoM YA dan pilih record dari daftar.
2. **Action → Export** → centang **I want to update data (import-compatible export)**.
   Sertakan `Product`, `Purchase Label`, `Factor`, `Active`; simpan sebagai XLSX.
   Odoo menyertakan **External ID** untuk mengenali record saat impor ulang.
3. Ubah baris yang perlu diperbarui tanpa mengubah External ID. Pada halaman daftar,
   buka **Import records** (menu Favorites/ikon impor sesuai tampilan Odoo), unggah XLSX,
   periksa pemetaan kolom, lalu klik **Test** sebelum **Import**.
4. Untuk aturan **baru**, gunakan baris baru dengan External ID unik, SKU yang dipetakan
   melalui **Product / External ID** dari ekspor master produk, label satuan, dan faktor
   **bilangan bulat positif**. Jangan hanya mengandalkan nama produk (bisa tidak unik).
   Gunakan contoh ekspor Odoo untuk mendapatkan header relasi yang benar.

**Pengaman:** pengujian impor pertama harus di `erp-yussyakmal-integer-test`.
Aturan yang sudah dipakai pada PO tidak boleh diubah identitas/faktornya; arsipkan aturan
lama dan buat pengganti. Kombinasi SKU+label satuan tidak boleh duplikat, termasuk aturan
arsip. Odoo melakukan validasi, tetapi batch impor tidak otomatis menawarkan pratinjau
rekap khusus 608 aturan seperti skrip impor awal. Jangan impor hasil ekspor berisi baris
arsip yang tidak sengaja diubah.

**Catatan:** XLSX didukung langsung oleh fasilitas impor/ekspor standar Odoo 19;
modul ini tidak menambahkan file Excel privat ke GitHub.
