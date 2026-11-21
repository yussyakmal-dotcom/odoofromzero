# ODOO FROM ZERO — Status Pengembangan dan Handoff Manufacturing

**Pembaruan:** 20 November 2026  
**Cakupan:** ringkasan teknis aman untuk repository publik. Detail lingkungan, daftar akun, identitas transaksi dan konfigurasi internal disimpan terpisah secara privat.

> **Dokumen ini adalah acuan status terbaru.** Catatan handoff sebelumnya adalah riwayat pengerjaan dan dapat memuat status lama yang sudah diselesaikan.

## Status tahapan

| Area | Status | Catatan batasan |
|---|---|---|
| Master produk, kategori, dan vendor | Lulus audit pada lingkungan test | Replikasi ke lingkungan lain memerlukan pemeriksaan data terpisah |
| Multi-UoM Purchasing | Lulus pengujian unit, ORM, dan UI | Harga antar satuan konsisten dalam satu dokumen, bukan lintas vendor |
| Integer Quantity | Lulus pengujian modul utama | POS belum diuji secara operasional |
| Diskon Purchase | Lulus pengujian | Diskon per baris atau global, tidak bersamaan; persen dan nilai tetap |
| Penerimaan Multi-UoM | Lulus pengujian ORM, alur validasi dan uji pengguna | Input di baris Operations; kuantitas fisik dikonversi ke satuan dasar |
| Integrasi Vendor Bill | Lulus | Kuantitas tagihan mengikuti barang diterima |
| Laporan PO, Receipt, Vendor Bill | Lulus HTML/PDF dan tinjauan pengguna | Receipt ringkas untuk operasi biasa; detail pelacakan tetap dipertahankan bila diperlukan |
| Jurnal Vendor Bill | Lulus audit saldo Debit/Kredit dan akun pajak | Belum membuktikan seluruh akuntansi produksi atau penutupan stok |
| Routing gudang | Ditunda | Diselesaikan setelah master dan kebutuhan produksi matang |
| POS | Ditunda | Aktivasi modul bukan berarti alur operasional siap |
| Manufacturing | Tahap berikutnya | Audit master dan pengujian harus dilakukan pada salinan test khusus |

## Modul kustom dalam scope

- `ya_purchase_multi_uom`
- `ya_integer_quantity`
- `ya_purchase_discount`
- `ya_partner_phone2`
- `ya_multi_uom_receiving`
- `ya_purchase_reports`

Modul yang tersedia dalam kode repository **bukan** bukti bahwa modul atau data master sudah terpasang di setiap database. Status actual harus diperiksa dari registry dan database target.

## Aturan proses yang disepakati

1. Satuan dasar produk merupakan unit terkecil yang bermakna untuk SKU; konversi multi-unit dikendalikan **per SKU**.
2. Quantity input operasional harus integer; angka stok dasar dapat merupakan hasil konversi unit.
3. Pembelian boleh menggunakan beberapa baris berbeda satuan untuk SKU yang sama.
4. Penerimaan dapat kurang atau sama dengan demand; **tidak boleh lebih**. Kekurangan dianggap selesai menurut kebijakan operasi yang telah disetujui; pengiriman berikutnya menggunakan PO baru.
5. Vendor Bill mengikuti kuantitas diterima, bukan jumlah PO yang belum diterima.
6. Uji perubahan harga lintas satuan dilakukan dalam satu PO; harga antar supplier boleh berbeda.
7. Tidak melakukan transaksi operasional POS sebelum master dan alurnya siap.
8. Tidak mengaktifkan rute gudang/Manufacturing otomatis sebelum pengujian lengkap.

## Standar deployment yang WAJIB

**Sumber kode Git dan direktori addons Odoo aktif adalah dua lokasi berbeda.** `git pull` **tidak otomatis** memasang perubahan kode ke Odoo.

1. Catat Git commit untuk versi yang akan diuji.
2. Salin **hanya addon yang dituju** ke direktori addons aktif dengan backup dan izin file yang sesuai.
3. Bandingkan file sumber dan file aktif (hash atau `diff`); jika berbeda, **jangan** menganggap upgrade sebagai validasi kode baru.
4. Upgrade modul **hanya** pada database test yang dipilih dan periksa kode keluar **serta** log.
5. Perbarui proses web/registry bila perlu; cek hasil UI, QWeb, dan tes ORM.
6. Simpan hasil uji dan keputusan; **tidak ada promosi ke database utama tanpa audit dan persetujuan eksplisit**.

Peringatan dokumentasi/indentasi tidak selalu sama dengan kesalahan instalasi; cari traceback atau parse error bila kode keluar gagal.

## Checkpoint Manufacturing

Pemilik server mengonfirmasi **database duplikat khusus Manufacturing sudah dibuat**. Nama dan identitas teknis duplikat dicatat secara privat. Jangan membuat duplikat baru hanya karena memulai sesi/chat baru.

**Sebelum perubahan apa pun:**

1. Verifikasi database target yang benar dan bahwa salinan tidak mengaktifkan email/automasi eksternal.
2. Audit read-only modul MRP, Work Center, Operations, BoM/komponen, MO, stock location, dan hubungan ke master sebelumnya.
3. Bandingkan jumlah/status master dengan sumber migrasi yang tersedia; **jangan langsung mengimpor ulang**.
4. Tetapkan skenario tes: satu MO untuk satu SKU, quantity integer, konsumsi bahan baku, WIP, output produk jadi, stok tidak boleh minus, dan kebijakan tanpa backorder yang telah disetujui.
5. Jalankan tes ORM dengan rollback; setelah lulus, uji antarmuka dan output laporan.
6. Audit penilaian persediaan dan HPP pada tahap integrasi produksi; jangan mengubah metode accounting hanya karena satu transaksi pembelian berhasil.

## Area yang belum diselesaikan

- Finalisasi data resmi perusahaan dan logo: ditunda sesuai keputusan pemilik.
- Konfigurasi pajak: perhitungan contoh pembelian sudah diaudit; kesesuaian kebijakan akuntansi dan supplier tetap perlu validasi bisnis.
- Seluruh siklus MRP, persediaan produk jadi, HPP, dan penutupan periode: **belum lulus tes**.
- Promosi modul dan data ke database utama: **belum dilakukan** dalam fase ini.

## Pesan handoff untuk chat berikutnya

> Lanjutkan ODOO FROM ZERO dari dokumen `doc/STATUS_PENGEMBANGAN_MRP.md`. Purchasing, Receiving Multi-UoM, diskon, Vendor Bill, laporan PDF, dan audit jurnal pembelian sudah lulus pada lingkungan test; **jangan ulangi audit itu tanpa kebutuhan baru**. Database khusus Manufacturing sudah diduplikasi: verifikasi nama dan statusnya dari konteks privat/server, lalu mulai audit MRP read-only. Jangan sentuh database utama atau POS. Selalu sinkronkan addon Git ke direktori aktif sebelum upgrade modul.


## Checkpoint 21 November 2026 — Master Work Center

**Status: PASS berdasarkan log terminal yang diberikan pelaksana (belum audit ulang independen).**

- Database khusus MRP telah dikonfirmasi dan dipakai untuk audit serta impor; database utama dan checkpoint Purchasing tidak menjadi target.
- Audit struktur: modul MRP/stock dan validasi integer terpasang; sebelum impor tercatat **0 Work Center, 0 Operations, 0 BoM, 0 komponen BoM, dan 0 MO**.
- Odoo 19 pada instalasi ini memiliki `mrp.workcenter.resource_id` required, `capacity_ids` melalui `mrp.workcenter.capacity` (kapasitas dapat spesifik produk), `resource_calendar_id`, `time_efficiency`, dan `costs_hour`. Tidak ditemukan field tunggal `capacity`.
- Sumber data Work Center berasal dari CSV privat; **16 entri**, tidak ada kode/nama kosong atau duplikat menurut preview.
- Script versi Git: `script/import_workcenter_ya.py`. Proses berjalan dengan mode PREVIEW (rencana create 16, skip 0), kemudian APPLY (log `IMPORT_OK committed created=16 total=16`). Script membuat Work Center melalui ORM, mengecek resource terkait, memverifikasi nama+kode, dan melakukan commit atau rollback.
- **Jangan jalankan impor ulang tanpa kebutuhan**. Jika perlu rerun untuk verifikasi gunakan mode PREVIEW; hasil ideal berikutnya create 0, skip 16. Jangan membuat ulang Work Center yang sudah ada.
- **Operations dan BoM belum diimpor** berdasarkan log terakhir. Jangan menyatakan sudah selesai.
- Nama/kode master sumber dan CSV privat **tidak dimasukkan ke Git publik**.

### Urutan berikutnya

1. Gunakan Work Center yang sudah dibuat sebagai referensi; tidak perlu audit teknis berulang jika tidak ada perubahan.
2. Siapkan sumber BoM dan hubungan Operations; Operations merupakan record `mrp.routing.workcenter` yang terkait BoM dan Work Center. Jangan buat daftar operasi lepas tanpa memperhatikan hubungan tersebut.
3. Validasi pemetaan SKU hasil, komponen, satuan, jumlah integer, dan referensi Work Center. PREVIEW sebelum APPLY; cegah duplikasi.
4. Uji sedikit data lebih dahulu dengan rollback di database MRP test, baru impor keseluruhan; kemudian cek UI dan hasil ORM.
5. Dokumentasikan hasil serta SHA commit. Tidak ada promosi ke database utama tanpa persetujuan.

**Catatan kesinambungan:** Dokumen handoff historis tanggal 20 November memiliki status awal yang telah kedaluwarsa. Untuk status operasional terbaru, gunakan **dokumen ini** dan log audit/commit terbaru, bukan bagian `BELUM SELESAI` pada handoff lama.


## Checkpoint 21 November 2026 — Uji massal BoM berhasil, BELUM APPLY

- Target tetap **database test Manufacturing**; database utama dan checkpoint Purchasing tidak diubah.
- Sumber privat yang sudah dibersihkan: **955 BoM** dan **8.502 baris komponen**. Header BOM12499 versi 1.100 Pcs dan BOM11913 dihapus berdasarkan keputusan pemilik; komponen kuantitas 0 dibuang; label satuan `Paket` dan `Botol 80ml` dipetakan menjadi `Pcs` sesuai satuan master produk. Operations/work orders, durasi, kapasitas belum dipakai.
- PREVIEW `script/preview_import_bom_ya.py`: `BOM_IMPORT_PREVIEW_OK`, 14 jenis Operation Type terpetakan berdasarkan gudang, existing BoM 0.
- Uji satu BoM `BOM12499` dengan 16 baris komponen via ORM: `ROLLBACK_TEST_OK` dan `ROLLBACK_CONFIRMED`.
- Uji massal `script/import_bom_bulk_ya.py`, Git commit `0f2d55c`, mode `YA_BOM_MODE=test`: **`TEST_EXIT_CODE=0`**, `BOM_BULK_TEST_OK created and verified: 955 8502`, `BOM_BULK_ROLLBACK_CONFIRMED: zero BoMs retained`.
- SHA-256 sumber CSV header: `f39036870ae7a0f439d23932ae91faef4765ad7cb6b02e2ff06d127c504b1b86`. SHA-256 komponen: `d05c8bff41df4d7eadf1e60484090ab1b20e9cafe9d8a1911bdbce3b40a9fb50`. Simpan CSV sebenarnya tetap privat.
- **Status sekarang: mass rollback TEST PASS, APPLY permanen BELUM dilakukan.** Langkah selanjutnya adalah menjalankan mode `YA_BOM_MODE=apply` pada DB MRP test menggunakan CSV yang sama (periksa hash), lalu audit read-only dan GUI. Tidak perlu mengulang audit lama.
