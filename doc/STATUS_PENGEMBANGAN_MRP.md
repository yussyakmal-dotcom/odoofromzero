# ODOO FROM ZERO — Status Pengembangan dan Handoff Manufacturing

**Pembaruan:** 22 November 2026 — addon Production Planning sudah terpasang/digunakan di MRP test; RO toko, konsolidasi MO, SO, DO tetap belum implementasi  
**Cakupan:** ringkasan teknis aman untuk repository publik. Detail lingkungan, daftar akun, identitas transaksi dan konfigurasi internal disimpan terpisah secara privat.

> **Dokumen ini adalah acuan status terbaru.** Catatan handoff sebelumnya adalah riwayat pengerjaan dan dapat memuat status lama yang sudah diselesaikan.

> **STATUS HISTORIS SCRAP (22 November 2026):** Multi-SKU Scrap `ya_scrap_multi` **terinstal dan form sudah muncul di `erp-yussyakmal-mrp-test`** menurut verifikasi pengguna. Konfigurasi Scrap bersama dan alasan Rusak/Expired **APPLY committed**. Pengujian end-to-end `3 SKU → 3 native Scrap → 3 Stock Move → 1 batch` **PASS** dan **rollback terkonfirmasi**. Belum ada hasil uji impor Excel terpisah atau promosi ke DB utama. Lihat checkpoint paling akhir dan `doc/HANDOVER_ODOO_FROM_ZERO.md`.

## CHECKPOINT TERBARU — 22 November 2026: YA Production Planning IMPLEMENTASI MRP TEST

> **Checkpoint ini mengesampingkan pernyataan lama dalam dokumen bahwa Master Capacity Template masih akan dibuat atau tidak ada addon Planning.** Rencana 3×dapur master template permanen **diganti** oleh Excel XLSX multi-sheet untuk tiap jadwal. Semua rancangan RO/MO/SO/DO di bagian bawah tetap belum diimplementasikan.

**Bukti server dan GUI:** addon `ya_production_planning` sudah terinstal pada `erp-yussyakmal-mrp-test`, empat model tercatat ada, source preflight lulus, Odoo service menerima deploy addon ke `/opt/odoo19/custom-addons/`. File input: `info` memetakan sheet→kode dapur; sheet dapur `DAPUR | Product | Max | Unit`. Ada sepuluh dapur dalam template contoh dengan 588 baris SKU. SOP menentukan SKU yang masuk sheet; importer memvalidasi teknisnya. Input tanggal kirim + S1 05.00 / S2 09.00 / S3 11.00 WIB.

**Alur UI final yang pengguna menyatakan sesuai:** **Upload Planning (menu) → list Planning Draft/Published → Upload Baru → Upload XLSX → Validate & Preview → Save Draft**, kemudian buka satu dapur untuk **Publish This Kitchen**. **Bukan** Publish Entire Upload. Pada Draft operator dapat mengedit Max, Published terkunci. Kosmetik minor UI ditunda. Menu Planning harus menampilkan keduanya dengan filter Draft/Published.

**Reupload:** kunci `delivery_date + slot + kitchen_code`. Belum ada → CREATE Draft; masih Draft → REPLACE SKU dan Max dapur; Published → SKIP dan tidak mengubah; dapur di luar file tidak tersentuh. Preview/notifikasi menampilkan CREATE/REPLACE/SKIP. Yang telah terlihat pada GUI antara lain notifikasi lima dapur Created Draft untuk jadwal baru; semua kombinasi tidak boleh diklaim E2E PASS tanpa tes tersendiri.

**UoM:** `Unit` Excel berasal dari **BoM Header UoM** produk, bukan dari stok master. Audit global menunjukkan 955 BoM, 902 satuan sama master, 53 berbeda; dari impor ada 29 mismatch vs master yang mengarah pada kebutuhan validasi BoM output UoM. Importer sekarang memeriksa BoM produk pada warehouse dapur dan Unit sama dengan BoM output. Tidak membuat konversi jumlah atau mengubah master. Premik, Trial, Dahlia 5 tidak masuk 10 dapur jadwal; Packing merakit produk paket dan penanganannya dirancang terpisah.

**Masalah teknis yang telah dipelajari:** `line_row field undefined` karena servis belum membaca Python terbaru walau XML sudah di-upgrade. `Cannot read properties of undefined (reading 'map')` sesudah Save Draft terjadi pada navigasi hasil upload; data sudah disimpan dan kode action ditambahkan `views`. Saat muncul popup, cek record dahulu, jangan upload ulang langsung. `git pull` tidak otomatis deploy custom-addons; kode Python, XML, ACL dapat memerlukan `-u` pada DB test dan restart `odoo19.service`. Lihat [SKILL_ODOO19_ADDON_WORKFLOW.md](SKILL_ODOO19_ADDON_WORKFLOW.md).

**BATAS:** Produksi/RO toko belum dijalankan oleh addon Planning. Published Planning Max > 0 adalah sumber daftar yang **akan** dipakai RO. Belum ada booking capacity RO, RO Confirm, MO ataupun accounting end-to-end. DB `erp-yussyakmal` dan `erp-yussyakmal-integer-test` tidak disentuh. Status akuntansi dan distribusi dalam dokumen adalah desain, bukan bukti tes.

**Next:** modul RO toko per toko + dapur + tanggal kirim + slot, dengan Excel Qty Pesan dan hanya SKU Published Max>0. Tidak perlu mengaudit 955 BoM lagi untuk mulai desain RO; kosmetik Planning pending.

---

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


## Checkpoint 21 November 2026 — APPLY BoM berhasil

**Berhasil menurut log server yang dikirim pengguna; verifikasi independen read-only/GUI berikutnya belum dilakukan.**

- Database target: `erp-yussyakmal-mrp-test`, bukan DB utama atau checkpoint Purchasing.
- Script: `script/import_bom_bulk_ya.py`, mode `YA_BOM_MODE=apply`.
- `APPLY_EXIT_CODE=0`; log final: **`BOM_BULK_APPLY_OK COMMITTED: 955 8502`**.
- **955 BoM** dan **8.502 baris komponen** telah dibuat serta diverifikasi oleh script sebelum commit. **14** Manufacturing Operation Type dipetakan; **tidak ada** Work Order Operations yang dibuat.
- Source file SHA-256 sesuai dengan file yang lulus test rollback sebelumnya:
  - Header: `f39036870ae7a0f439d23932ae91faef4765ad7cb6b02e2ff06d127c504b1b86`
  - Komponen: `d05c8bff41df4d7eadf1e60484090ab1b20e9cafe9d8a1911bdbce3b40a9fb50`
- Jangan menjalankan APPLY ulang. Importer sengaja menolak database yang sudah memiliki BoM.
- Tahap berikut: verifikasi **read-only** total `mrp.bom` dan `mrp.bom.line`, sample cek SKU, kuantitas, komponen, picking type dan GUI. Setelah itu mulai tes satu Manufacturing Order dengan rollback, cek stok tidak negatif, konversi UoM, WIP, dan alur gudang sebelum alur produksi nyata.
- `git pull` hanya memperbarui repository; script Odoo shell ini tidak memerlukan salin addon karena tidak mengubah addon. Hindari upgrade modul tanpa alasan.


## Checkpoint 21 November 2026 — Verifikasi independen pasca-impor BoM LULUS

Pengguna menjalankan Odoo shell **read-only** langsung pada database MRP test setelah APPLY:
- `TOTAL BOM: 955`
- `TOTAL COMPONENT: 8502`
- `BOM12499: 1`; SKU produk `12499`; `SAMPLE QTY: 10.0`; `SAMPLE LINES: 16`; Operation Type `Dapur Tart: Manufacturing`.
- `BOM11913: 0` (sesuai keputusan menghapus).
- `POST_IMPORT_AUDIT_OK`.

**Status akhir master:** 16 Work Center telah ditampilkan di GUI, 955 BoM + 8.502 baris komponen sudah diimpor dan lulus verifikasi ORM independen. **Jangan impor ulang.** Belum ada bukti tes transaksi MO selesai. Berikutnya inspeksi sampel GUI BoM bila perlu, lalu uji Manufacturing Order dengan rollback; jangan membuat operasi/durasi/kapasitas fiktif atau mengubah stok produksi tanpa uji dan persetujuan.


## Checkpoint 21 November 2026 — Koreksi UoM SKU 11055 berhasil

Berdasarkan log CLI `erp-yussyakmal-mrp-test` dari pengguna:
- Script `script/fix_sku_11055_uom_gram_ya.py` uji mode `test`: `TEST_EXIT_CODE=0`, perubahan master dari Pcs ke Gram serta restore dua BoM line lulus, kemudian rollback dikonfirmasi.
- Mode `apply`: `APPLY_EXIT_CODE=0`; `UOM_CHANGE_VERIFIED: SKU 11055 BASE: Gram RESTORED_LINES: 2 TOTAL_BOMS: 955 TOTAL_LINES: 8502`; `UOM_CHANGE_APPLY_OK COMMITTED`.
- Komponen `BOM12499` = 500 Gram dan `BOM12326` = 300 Gram. Baris komponen tersebut direkonstruksi melalui ORM sehingga ID internalnya bisa berubah; jangan gunakan ID lama secara hard-code.
- Pemeriksaan script: `stock.move`, `stock.move.line`, `stock.quant`, `mrp.production`, `purchase.order.line`, `sale.order.line` semuanya 0 untuk SKU 11055 pada saat APPLY; model stock valuation layer tidak tersedia di registry yang diuji.
- Belum ada bukti uji konsumsi stok/Mark as Done. Audit seluruh BoM sebelumnya: 8.248 line satuan sama persis, 191 beda UoM dengan hasil konversi 1:1, 63 cross-family; **angka ini sebelum koreksi 11055 dan perlu diperbarui jika menilai status terkini**.
- Tidak perlu menjalankan ulang APPLY SKU 11055 atau impor BoM. Lanjut meninjau daftar UoM berbeda per SKU dan validasi stok dengan rollback.


## Checkpoint — 21 November 2026: Koreksi UoM 73 SKU selesai (MRP test)

Berdasarkan output terminal pengguna dan audit independen:
- SKU 11055 telah diubah dari Pcs menjadi Gram melalui script terpisah; BoM dan komponen dipertahankan.
- Koreksi massal 72 SKU dengan `YA_UOM_KOREKSI_72_SKU_REVISI_2.csv` (SHA256 `5e120a0057a8c73c10abdef83b9def3eb1e94844da574d796bd16945f85c2d38`) selesai pada database `erp-yussyakmal-mrp-test`. Log: `UOM_72_APPLY_OK COMMITTED`.
- Keputusan khusus: SKU 10473 = Resep untuk master dan BoM; SKU 11074 = Pcs untuk master dan BoM; SKU 10732 = Bungkus untuk master dan BoM.
- Audit independen `script/audit_post_apply_uom_72_ya.py` sukses (`AUDIT_EXIT_CODE=0`, `POST_APPLY_72_AUDIT_OK`, `ISSUE_COUNT: 0`). Audit mencakup 72 SKU, 253 referensi komponen, 65 Header BoM; hasil global `GLOBAL_QTY_ONE_GRAM: 0`. Total tetap **955 BoM dan 8.502 baris komponen**.
- Script audit bersifat read-only (`NO_DATABASE_CHANGES`). Tidak perlu mengulang APPLY atau impor BoM. UoM berdasarkan keputusan pengguna sudah konsisten; pengujian tidak membuktikan ekuivalensi fisik antarunit yang berbeda, yang tetap harus divalidasi di penggunaan operasional.
- Selanjutnya: validasi MO, consumptions, WIP, lokasi sumber/tujuan, stok tidak minus dan penyelesaian produksi **di MRP test dengan rollback dahulu**. Jangan ubah database produksi atau Purchasing test.


## 22 November 2026 — Multi-SKU Scrap addon disiapkan (BELUM INSTAL)

Keputusan baru di ODOO FROM ZERO: hentikan audit Scrap dan buat **satu dokumen dengan satu Source Document, satu alasan, satu lokasi asal, satu lokasi virtual Scrap bersama seluruh Central/dapur/toko, dan banyak SKU**. Tambahkan **impor Excel .xlsx**.
- Addon baru: `addons/ya_scrap_multi` (Odoo 19 Community), tergantung `stock`, memakai tag alasan bawaan `stock.scrap.reason.tag`.
- Parent `ya.scrap.batch`, lines `ya.scrap.batch.line`, tautan ke native `stock.scrap` melalui `ya_batch_id`. Validasi membuat satu native stock.scrap per baris dan memanggil `action_validate()`; seluruh proses satu transaksi database.
- Input Excel: SKU, Quantity, UoM; template unduh, validasi kesesuaian satuan, maksimum 1.000 baris; semua baris tambahan tetap Draft sampai validasi.
- Script cek Draft/import-Excel (rollback): `script/test_multi_scrap_xlsx_rollback_ya.py`; membutuhkan addon dan lokasi Scrap serta tag `Rusak` sudah terpasang.
- **Kode baru commit, belum ada bukti terdeploy, terinstal, atau diuji pada server Odoo.** Jangan anggap siap operasi sebelum install+smoke test+uji stock move dengan rollback.
- Jangan membawa policy dari proyek lain. Tidak ada approval atau larangan stok minus dalam addon; pembelajaran konsekuensi dilakukan sebelum policy bisnis.


## Checkpoint terbaru — 22 November 2026: Multi-SKU Scrap, E2E PASS + ROLLBACK

**Sumber bukti:** log terminal pengguna dari `erp-yussyakmal-mrp-test`; bukan verifikasi ulang langsung ke server melalui konektor. Bagian historis di atas mencatat keadaan pada tanggal checkpoint masing-masing dan **tidak boleh dibaca sebagai status terkini** bila bertentangan dengan checkpoint ini.

### Keputusan scope pengguna

- **Hentikan audit perbandingan Scrap vs Opname.** Lanjutkan pengembangan modul multi-SKU.
- **Satu dokumen induk** berisi **banyak SKU**, **satu alasan**, **satu Source Document**, **satu lokasi asal** serta **satu lokasi Scrap virtual bersama** yang bisa dipakai Central, semua dapur, dan semua toko.
- Pilihan alasan Scrap **harus dari master yang sudah ada**; form Multi-SKU Scrap **tidak menawarkan Create / Create and Edit / Quick Create**. Ini pembatasan UI form tersebut, **bukan** pembatasan administratif global.
- Tambahkan **impor file .xlsx** ke baris dokumen: `SKU, Quantity, UoM`; UoM opsional (fallback satuan dasar); baris tetap Draft sebelum validasi.
- **Tidak ada** keputusan untuk menambah approval, membatasi stok minus, atau mengubah metode costing. Jangan mengimpor kebijakan dari percakapan/proyek lain.
- Pemahaman bisnis pengguna: Scrap untuk barang fisik yang rusak/expired/dimusnahkan dengan sebab jelas; Opname untuk selisih audit fisik vs sistem. Jangan menyamakan selisih hasil MO dengan Scrap otomatis.

### Status instalasi / master (MRP TEST ONLY)

- Addon `addons/ya_scrap_multi`, nama teknis `ya_scrap_multi`, telah **installed** menurut hasil SQL `ir_module_module.state = installed`; pengguna mengonfirmasi menu/form sudah muncul dan OK.
- Konfigurasi master sudah **committed** (log: `APPLY_EXIT_CODE=0`, `SCRAP_SETUP_APPLY_OK COMMITTED`): lokasi virtual `Scrap` (ID saat APPLY: **248**, usage `inventory`); tag `Rusak` (ID **3**) dan `Expired` (ID **4**). ID hanya identitas DB MRP test, jangan hard-code untuk DB lain.
- Lokasi standar `Inventory adjustment` tetap terpisah, bukan tujuan Scrap.
- Form memilih `reason_tag_id` dari model bawaan `stock.scrap.reason.tag`. `stock.scrap` menyimpan alasan pada `scrap_reason_tag_ids`.
- Perbaikan kompatibilitas Odoo 19 mengganti validasi `uom.uom.category_id` yang **tidak tersedia** menjadi pemeriksaan native `_has_common_reference()` di `addons/ya_scrap_multi/models/scrap_batch.py`. Commit perbaikan `014fe71`. Versi yang dipakai oleh uji E2E berikutnya berhasil melewati langkah ini.

### Bukti uji End-to-End

Script: `script/test_multi_scrap_3sku_e2e_rollback_ya.py`, commit pembuatan `a2802da`.

Log pengguna:
- `TEST_EXIT_CODE=0`
- `E2E_3_SKU_3_NATIVE_SCRAPS_1_BATCH_OK`
- `E2E_3_SKU_ROLLBACK_CONFIRMED`
- Source `TART/Stock`; tujuan `Scrap`; alasan tunggal `Rusak`; Source Document tunggal `YA-E2E-3SKU-ROLLBACK`; dokumen induk `SCRB/2026/00003`.
- Data simulasi: SKU `10440` qty **1** -> `SP/00001`, stock move **46**, saldo sementara **9**; SKU `10180` qty **2** -> `SP/00002`, move **47**, saldo **8**; SKU `10182` qty **3** -> `SP/00003`, move **48**, saldo **7**.
- Ketiga `stock.scrap` memiliki `state=done`, alasan sama, origin/source document sama, `ya_batch_id` sama; ketiga `stock.move` berstatus `done` dan mengalir ke lokasi Scrap.
- Seluruh objek dan perubahan stok simulasi di-**rollback**. Nomor dokumen, IDs transaksi serta saldo di atas adalah **hasil sementara pengujian**, **bukan transaksi permanen**; tidak boleh dicari sebagai riwayat posting nyata.
- Kegagalan awal (`AttributeError: uom.uom has no attribute category_id`) **sudah diatasi**; rollback tes gagal juga terkonfirmasi. Jangan kembali memakai `category_id`.

### Fitur addon dan batas verifikasi

- Model: `ya.scrap.batch` (header), `ya.scrap.batch.line` (baris), native `stock.scrap` (satu per baris) dengan tautan `ya_batch_id`; `action_validate()` native menangani stok. Kesalahan baris membatalkan validasi dalam satu transaksi melalui savepoint.
- Form, menu dan instalasi: pengguna sudah konfirmasi.
- **Belum ada bukti tes terpisah impor Excel .xlsx** (termasuk preview dan error handling), meskipun kode import/template tersedia dan script Draft rollback `script/test_multi_scrap_xlsx_rollback_ya.py` dibuat.
- **Belum ada** bukti uji manual operator penuh, uji multi-company, pengujian lot/serial-tracked products, atau audit jurnal dan biaya kerugian Scrap. Jangan klaim semuanya lulus.
- **Belum ada promosi ke `erp-yussyakmal`** (utama) atau `erp-yussyakmal-integer-test` (checkpoint Purchasing).

### Lanjutan teknis yang tepat

1. Jalankan `script/test_multi_scrap_xlsx_rollback_ya.py` di MRP test setelah meninjau SKU sampel pada script (jangan anggap data hard-code berlaku di luar DB ini); perbaiki bila perlu, lalu cek import 3 SKU melalui GUI.
2. Uji satu dokumen Manual dan satu impor Excel; cek header, pilihan alasan existing-only, tiga `stock.scrap`, stock moves, dan tampilan smart button. Gunakan rollback untuk tes otomatis yang memanipulasi saldo.
3. Pastikan GUI menolak pembuatan alasan baru dari header. Kebijakan akses administratif tag alasan belum diputuskan.
4. Catat hasil dan hanya setelah persetujuan eksplisit rencanakan deployment di lingkungan lain.
5. Jangan mengulang audit Scrap vs Opname yang sudah ditutup pengguna; jangan menjalankan ulang impor master BoM/UoM.


---

## 22 November 2026 — Desain Replenishment Toko, Konsolidasi MO, dan Prioritas SO (BELUM IMPLEMENTASI)

**Status:** keputusan desain dari diskusi pengguna; **belum dibuat addon, belum mengubah rute, database, MO, transfer, atau konfigurasi Odoo**. Fokus implementasi berikutnya adalah **alur permintaan toko terlebih dahulu**. Integrasi SO dirancang setelah fondasi RO toko matang. Jangan salah membaca bagian ini sebagai bukti tes PASS.

### A. Karakter operasi yang menjadi acuan

- Setiap SKU mempunyai **dapur produksi yang telah ditentukan**. Dapur memproduksi SKU miliknya; tidak ada pemilihan dapur secara bebas pada saat konsolidasi.
- **Gudang Packing** adalah titik konsolidasi permintaan, hasil produksi lintas dapur, pemisahan pesanan, dan distribusi; Packing **bukan** dapur produksi.
- Sales Order **bukan POS** dan tidak mewakili pemesanan instan: perkiraan volume **10–50 SO/hari**, lazimnya pemesanan **2–3 hari sebelum pengiriman**. Desain harus berbasis jadwal yang realistis; jangan over-engineer transaksi seolah berkecepatan POS.

### B. Dokumen Replenishment Order / Request (RO) dari toko — prioritas desain PERTAMA

1. **Satu dokumen RO per toko untuk satu dapur produksi**, berisi **banyak SKU milik dapur tersebut**. Contoh: jika toko meminta dari 8 dapur, terbentuk **8 dokumen RO**; bukan satu RO yang mencampur 8 dapur.
2. RO membawa identitas toko, dapur, hubungan jadwal produksi dan tanggal/jadwal pengiriman, serta baris SKU dan kuantitas. Perincian final pengelompokan per siklus/jadwal, terutama jika satu dokumen memuat beberapa jadwal produksi SKU, **masih perlu ditetapkan**.
3. Input SKU bersifat **unggah template Excel (.xlsx) per dapur**, bukan entry manual 50–200 SKU satu per satu. Template berisi kolom **Reference, Nama Produk, Qty Pesan** dan daftar SKU yang diambil dari master Odoo. Operator hanya mengisi Qty Pesan; 8 dapur dapat berarti 8 file/template dan 8 RO.
4. **Reference** digunakan untuk mencocokkan SKU dengan master; nama produk adalah petunjuk baca. SKU yang tidak termasuk dapur di header tidak boleh diterima. Usulan teknis yang perlu diuji: baris Qty kosong/0 dilewati, cegah duplikat Reference, tolak Qty negatif/tidak valid, beri pesan error jelas, dan definisikan perilaku unggah ulang agar tidak menggandakan jumlah. Ini adalah rancangan validasi, **bukan fungsi yang sudah teruji**.
5. **Permintaan asli toko wajib dipertahankan**, terpisah dari kuantitas alokasi terbaru dan kuantitas yang sudah dikirim. Alokasi dapat berubah, tetapi jejak permintaan awal tidak boleh hilang.

### C. Konsolidasi toko → MO

1. Kumpulkan RO dari banyak toko dan **kelompokkan per dapur, jadwal produksi, dan SKU** (serta dimensi BoM/batch apabila relevan). Satu RO memuat banyak SKU, tetapi **satu MO hanya satu SKU** pada kelompok produksi yang bersangkutan.
2. Jumlah permintaan seluruh toko dibandingkan dengan Production Plan/kapasitas PPIC untuk SKU dan jadwal tersebut. Jika permintaan melebihi kapasitas yang tersedia, alokasi toko dibagi **prorata**, dengan pembulatan integer yang mempertahankan total (misalnya metode floor + largest remainder seperti dalam dokumen arsitektur awal).
3. **Kelipatan batch BoM** harus diperhitungkan sebelum kuantitas MO dan alokasi akhir dianggap final. Kapasitas nominal tidak otomatis sama dengan jumlah yang benar-benar bisa diproduksi; hasil dan surplus buffer perlu dipisahkan dari permintaan toko.
4. MO gabungan tidak dibuat satu per RO/toko. Packing tetap mengetahui toko penerima melalui rekam alokasi, meskipun produk berasal dari MO yang sama.

### D. Integrasi Sales Order — tahap SETELAH RO toko

1. **Prioritas SO di atas permintaan toko.** Alokasi toko bersifat dapat dialihkan (*soft allocation*) hingga barang **dikirim dari Packing**. SO terkonfirmasi memiliki komitmen lebih tinggi; permintaan asli toko tidak diubah.
2. SO dapat berisi banyak SKU dari **beberapa dapur**. **Semua baris SO wajib lulus atau seluruh SO tetap Draft**. Jangan memesan kapasitas sebagian SKU bila satu SKU gagal.
3. Pada klik **Confirm SO, pemeriksaan pertama adalah flag Open/Locked untuk jadwal produksi dan jadwal pengiriman yang relevan**. Jika salah satu Locked, **SO tidak bisa dikonfirmasi**, meskipun kapasitas masih ada. MO sudah terbit **tidak otomatis** berarti jadwal Locked.
4. Jika kedua jadwal Open, cek kapasitas untuk **setiap SKU pada dapur/jadwal produksinya**, termasuk kebutuhan kelipatan BoM dan jumlah toko yang masih boleh dialihkan. SO baru yang lolos dapat mengurangi alokasi toko **sampai nol**.
5. **Realokasi toko dilakukan otomatis secara prorata terhadap toko yang alokasinya masih dapat ditarik**, tanpa approval PPIC tambahan. Berlaku **meskipun MO telah diterbitkan**, selama barang toko terkait **belum dikirim**. Barang yang sudah dikirim dari Packing ke Transit tidak dihitung sebagai kuota yang dapat diambil.
6. Perubahan alokasi tidak otomatis berarti harus membatalkan/membuat ulang MO bila total produksi masih sama. Jika kuota SO melebihi kemampuan slot yang sungguh tersisa, konfirmasi gagal (jangan menjanjikan stok yang tidak bisa dipenuhi).
7. Saat sistem menulis konfirmasi, pemeriksaan jadwal dan kapasitas serta perubahan alokasi harus konsisten sebagai **satu transaksi**; hindari penjadwalan ganda atau konfirmasi parsial. Ini kontrol integritas data, bukan target throughput POS.
8. Agar tidak menghasilkan MO ganda, jalur SO yang menuju konsolidasi khusus perlu dibedakan dari pemicu produksi otomatis native MTO/route standar. Pengaturan integrasi belum diputuskan.
9. **Tanggal order, tanggal produksi, dan tanggal pengiriman berbeda**; jadwal SO harus mendukung lead time 2–3 hari (atau sesuai kebutuhan aktual), bukan asumsi produksi/kirim langsung saat Confirm.

### E. Penguncian dan ruang lingkupnya

- Rancangan mempunyai **Production Schedule Open/Locked** dan **Delivery Schedule Open/Locked**. Kedua status harus Open untuk menerima **SO baru** pada jadwal terkait.
- Status diterapkan pada **slot yang tepat**, tidak otomatis menutup seluruh dapur atau seluruh perusahaan. Definisi persis slot, pengguna yang berwenang mengunci/membuka, serta kebijakan perubahan RO setelah lock **belum ditetapkan**.
- Kondisi **MO diterbitkan** terpisah dari kondisi **jadwal terkunci** dan terpisah dari status **barang sudah dikirim**.
- Realokasi harus menangani kuantitas yang sudah dikeluarkan untuk toko, serta *stock reservation/picking* yang belum Done, tanpa mengubah transaksi Done secara diam-diam.

### F. Celah implementasi yang belum ditutup

- Kejadian produk selesai kurang dari target MO, sebagian toko sudah dikirim, atau kuantitas tersedia tidak cukup untuk SO yang sudah terkonfirmasi: perlu kebijakan kekurangan/exception dan pelaporan; jangan mengarang penanganannya.
- Kapasitas SKU per dapur perlu selaras dengan sumber daya bersama (Work Center, jam kerja), jika itu memang membatasi produksi.
- Perubahan, pembatalan, dan pengiriman parsial SO/RO harus mempertahankan histori alokasi; detail lifecycle belum final.
- Tentukan hubungan satu RO per dapur dengan tanggal/jadwal produksi SKU yang bisa berbeda, serta cara memilih jadwal saat impor Excel.
- Aturan cutoff, otorisasi lock/unlock, dan revisi RO setelah locking belum mendapat keputusan eksplisit.
- Perlu tes integrasi SO, RO, MO, Picking, Packing dan Transit di database test sebelum klaim siap operasi.

### G. Urutan kerja yang disetujui dalam diskusi

1. **Desain dan implementasi RO toko per dapur + template/impor Excel** terlebih dahulu.
2. Rancang dan uji konsolidasi **RO lintas toko → kapasitas PPIC → prorata → MO per SKU/dapur/jadwal**.
3. Uji alur produksi dan distribusi **Dapur → Transit → Packing → Transit → Toko** dengan jejak kuantitas Requested / Allocated / Delivered.
4. **Baru tambahkan SO** multi-SKU lintas dapur: first-check lock, seluruh baris lolos, prioritas SO, realokasi prorata toko otomatis, dan konsolidasi pengiriman di Packing.
5. Untuk semua pekerjaan: perubahan hanya jika diminta/disetujui, uji di **MRP test**, hindari audit ulang sistem default yang tidak relevan, dan jangan menyentuh DB utama/Purchasing test.

**Rujukan desain:** diskusi arsitektur terbaru dan PDF pengguna “Dokumentasi Alur Kerja Sistem ERP Odoo 19 Community” (dua jalur asli: PPIC supply + replenishment toko; tambahan jalur demand SO diputuskan kemudian). PDF bukan bukti konfigurasi sudah dibuat.

---

## 22 November 2026 — Integrasi Accounting pada Inventory dan Manufacturing (PRINSIP DESAIN, BELUM UJI)

**Arahan eksplisit pengguna:** **semua tahapan dan proses Inventory serta Manufacturing harus memperhitungkan modul Accounting yang berjalan di belakang transaksi**. Jangan menyelesaikan rancangan RO, konsolidasi, MO, stock moves, Packing, atau pengiriman hanya dari sisi kuantitas tanpa memperhitungkan valuasi, biaya produksi, HPP, dan konsistensi catatan akuntansi. **Ini persyaratan lintas modul sejak tahap desain**, bukan pekerjaan tambahan setelah operasional selesai.

### Matriks lintas alur: kejadian operasional dan konsekuensi accounting yang harus dirancang / diuji

| Tahapan | Operasional | Dampak Accounting yang harus diperiksa |
|---|---|---|
| RO toko / upload Excel / konsolidasi / prorata / Production Plan | Demand dan alokasi rencana, belum perpindahan fisik | **Tidak mengarang jurnal stock/COGS hanya karena demand dibuat atau dialokasikan**; hubungan ke valuasi saat stok benar-benar bergerak harus tetap dapat ditelusuri |
| SO Draft / Confirm | Komitmen pemesanan dan slot produksi/pengiriman | Pisahkan reservasi demand dari realisasi stock; Invoice/payment dan pengakuan biaya harus mengikuti konfigurasi aktual, bukan diasumsikan terjadi saat Confirm |
| Pembelian / penerimaan komponen di Central | Receipt PO, lokasi stok, Vendor Bill | Nilai perolehan bahan, metode costing, mapping akun persediaan dan kewajiban/timing posting; pembelian telah dites sebagian, integrasi valuasi end-to-end belum |
| Central → Transit → Dapur | Internal Transfer material | Ketepatan kuantitas/nilai persediaan menurut tipe lokasi & perusahaan; **jangan otomatis mengasumsikan setiap internal move membuat jurnal** |
| Dapur → Pre-Production / konsumsi BoM | Konsumsi bahan baku dan WIP | Biaya bahan, biaya dalam proses, metode penilaian, dan jejak sumber biaya MO |
| MO / WO → hasil produksi jadi | Produksi aktual, hasil kurang/lebih, scrap jika ada, biaya Work Center jika digunakan | Nilai barang jadi, HPP produksi aktual, selisih/variance, akun produksi/WIP, dan rekonsiliasi konsumsi vs output; **jangan mengarang biaya tenaga kerja atau overhead jika master belum disiapkan** |
| Dapur → Transit → Packing | Transfer produk jadi | Valuasi dan kepemilikan barang tetap konsisten; perpindahan lokasi tidak otomatis berarti penjualan |
| Packing → Transit → Toko | Transfer untuk replenishment toko | Persediaan antarlokasi tetap dapat ditelusuri, accounting benar terhadap status lokasi/perusahaan, tidak otomatis mengakui penjualan/HPP pelanggan |
| Packing → Customer (SO Delivery) | Pengiriman pelanggan | Penilaian keluar stok, saat pengakuan HPP mengikuti metode accounting/valuation yang benar; Invoice SO ditangani terpisah |
| Scrap / inventory adjustment / return | Penyesuaian atau barang keluar/masuk tidak biasa | Pengurangan/penambahan nilai stok, akun kerugian/selisih, trace stock dan accounting; tes Scrap 3-SKU sebelumnya **hanya menguji alur stok, bukan jurnal/valuasi** |

### Aturan implementasi dan pengujian

1. Sebelum membuat atau memvalidasi modul RO/Allocation/MO/Transfer, lakukan **pemeriksaan terarah yang diperlukan saja** atas metode valuasi dan costing (mis. AVCO/FIFO/Standard), konfigurasi akun produk/kategori/lokasi, stock valuation, serta mekanisme jurnal/closing **yang benar-benar tersedia pada Odoo 19 Community + modul Accounting/OCA terpasang**. Jangan membuat audit massal tanpa tujuan.
2. Setiap **tes end-to-end** nantinya menilai dua lapis: **(a) transaksi dan kuantitas stok**, **(b) nilai stok, biaya produksi/HPP, dan jurnal/closing bila berlaku**. Gunakan saldo uji terkendali dan rollback; jangan sentuh DB utama.
3. **Perubahan Odoo 19:** dokumentasi resmi menjelaskan pembedaan real-time inventory valuation dan timing journal accounting; model perpetual versi 19 **tidak boleh disamakan begitu saja dengan Odoo versi lama yang membuat jurnal pada setiap stock move**. Metode dan dukungan modul yang tersedia pada instalasi Community ini harus diverifikasi dahulu.
4. Jangan memaksakan jurnal pada setiap RO, alokasi, internal transfer, atau konfirmasi SO. Jurnal yang memang diperlukan harus mengikuti **kejadian ekonomi, metode, company ownership, akun dan konfigurasi aktual**.
5. Pertahankan **traceability**: RO/line → alokasi → MO/komponen/finished goods → stock moves/picking → delivery toko/SO → nilai persediaan/biaya/jurnal atau penutupan periode yang relevan.
6. Status **BELUM DIUJI**: integrasi akuntansi atas seluruh siklus produksi–distribusi termasuk WIP, costing, stock valuation, pengakuan HPP, scrap loss, dan rekonsiliasi GL. Modul OCA Accounting yang sudah terpasang **bukan bukti** bahwa seluruh integrasi ini otomatis berfungsi.

**Rujukan publik teknis:** dokumentasi resmi Odoo 19 Inventory Valuation dan Valuation Cheat Sheet serta Manufacturing Order Costs / Work-in-Progress; rujukan bersifat perilaku standar, **bukan hasil verifikasi DB pengguna**:
- https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/inventory/inventory_valuation/cheat_sheet.html
- https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/inventory/inventory_valuation/operations_valuation.html
- https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/manufacturing/basic_setup/mo_costs.html
- https://www.odoo.com/documentation/19.0/applications/inventory_and_mrp/manufacturing/basic_setup/work_in_progress.html


---

## 22 November 2026 — Keputusan desain terbaru: Planning, RO, MO, Packing, DO, selisih, anti-fraud

**STATUS: DESAIN TELAH DIDISKUSIKAN, BELUM DIIMPLEMENTASIKAN ATAU DIUJI DI ODOO.** Bagian ini **menggantikan usulan lama yang bertentangan** (misalnya membuka pemesanan oleh Packing, alokasi final toko pada saat membuat MO, penggunaan tanggal produksi sebagai kunci, dan tombol selesai pesan oleh toko). Jangan menganggap mockup form sebagai hasil implementasi.

### 1. Delivery Schedule sebagai kunci tunggal operasional

- Tepat **3 slot tetap per tanggal pengiriman**, WIB: **S1 Subuh 05.00**, **S2 Pagi 09.00**, **S3 Siang 11.00**.
- **Tanggal pengiriman + slot** merupakan kunci jadwal untuk planning, penerimaan RO, konsolidasi, penerimaan SO dan alokasi. Close/Lock satu tanggal-slot tidak menutup slot lainnya.
- Tanggal/waktu produksi hanya **informasi operasional**, bukan kunci lock/konsolidasi: produksi berlangsung malam melewati pergantian hari. Tidak memerlukan batch terpisah hanya karena perubahan tanggal.
- SKU punya dapur produksi tertentu. Gudang Packing mengonsolidasikan hasil dari berbagai dapur.

### 2. Master Capacity Template dan Generate Planning Massal — TAHAP PERTAMA

- Jumlah kombinasi master template standar: **3 × jumlah dapur** (contoh 10 dapur → 30 template), masing-masing berisi **Reference, Nama Produk, Max Capacity per SKU** untuk dapur + slot.
- **Export/Import Excel hanya pada Master Capacity Template** untuk memperbarui daftar/kapasitas standar. **TIDAK ada upload Excel pada Production Planning harian.**
- Admin Produksi memilih tanggal kirim, slot dan dapur; **Generate Massal** membuat Draft Planning terpisah untuk tiap kombinasi **tanggal pengiriman + slot + dapur** dari master template. Dapur/slot boleh dipilih massal, hindari dokumen ganda. Kapasitas Draft boleh dikoreksi langsung di form; perubahan harian tidak mengubah master dan perubahan master tidak mengubah planning lama.
- Draft → Publish; Published adalah dasar pemesanan toko. **Planning SKU berkapasitas 0 tidak ditawarkan pada RO**. Kapasitas berarti batas untuk SKU/jadwal, bukan Work Center per-cycle capacity. Jangan menyalahgunakan field Odoo standar dengan makna berbeda.
- Publish, Close RO dan Lock untuk SO adalah konsep berbeda. Tidak perlu membuat kebijakan baru perubahan kapasitas Published tanpa permintaan pengguna.

### 3. RO toko — banyak SKU, Excel terfilter

- **1 RO = 1 toko + 1 dapur + 1 tanggal pengiriman + 1 slot**, berisi banyak SKU dapur itu. Toko memilih **jadwal kirim**, tidak perlu memilih kapan diproduksi.
- Header minimal: nomor RO, **tanggal pesanan**, toko, dapur, **tanggal + slot/jam pengiriman**, status.
- **Draft → Confirmed**, hanya Confirmed yang masuk konsolidasi. Toko **download Excel** berisi **Reference, Nama Produk, Qty Pesan**, mengisi Qty, lalu **upload** ke RO dan review sebelum Confirm.
- Hanya SKU dengan **Published Max Capacity > 0** untuk dapur dan jadwal terkait yang boleh diminta. Validasi juga saat upload: SKU di luar daftar, beda dapur, qty negatif/tidak valid, duplikat ditolak; 0/kosong tidak diikutkan; upload Draft ulang mengganti baris, bukan menjumlahkan. Toko tidak bisa menambahkan item di luar daftar baik dari Excel maupun UI.
- Qty Requested adalah *demand*, **bukan kuota pengiriman yang dijamin**. Bisa berakhir alokasi 0 karena SO lebih prioritas, atau lebih besar dari RO berkat surplus hasil pembulatan resep.

### 4. Packing Close RO → Konsolidasi → MO → Material Replenishment

- **Admin Packing tidak membuka pemesanan.** Jadwal tersedia ketika PPIC Publish; **Admin Packing menutup akses pemesanan RO toko per tanggal + slot**, lalu menjalankan konsolidasi RO Confirmed. Draft tidak ikut.
- Konsolidasi menggabungkan kebutuhan **per jadwal kirim + dapur + SKU** bersama demand SO; mengacu kapasitas maksimal PPIC serta kelipatan hasil BoM. **Bukan alokasi final per toko**.
- Hasil konsolidasi membuat **MO satu SKU per dapur dan jadwal kirim**, bukan MO per RO; tidak membuat MO setiap toko Confirm RO.
- **Di antara Generate MO dan pelaksanaan produksi wajib ada Material Replenishment**: hitung seluruh kebutuhan bahan dari BoM MO terkonsolidasi, periksa stok dapur tersedia, buat kebutuhan **Internal Transfer Central → Transit → Dapur**, dan validasi penerimaan fisik oleh dapur sebelum dipakai produksi.
- Setelah itu, MO/WO dikonsumsi/diproses; produk jadi berpindah **Dapur → Transit → Packing**. Produksi bisa menghasilkan kuantitas lebih tinggi dari demand karena kelipatan resep, tetapi tidak boleh melewati batas produksi yang disepakati.

### 5. Alokasi SO dahulu; alokasi final toko dan DO dilakukan TERAKHIR

- SO bisa multi-SKU dari beberapa dapur; saat Confirm **cek status Open/Locked jadwal pengiriman terlebih dahulu** serta validasi semua SKU terhadap planning/kapasitas. Jika satu SKU gagal, **seluruh SO tidak Confirm**. SO punya prioritas mutlak atas kuota toko belum dikirim, termasuk setelah MO terbit, **selama slot pengiriman masih Open**.
- SO tidak instan seperti POS (estimasi 10–50 SO/hari, lazimnya 2–3 hari sebelum kirim); jangan over-engineer kecepatan.
- **JANGAN alokasikan toko secara final saat Planning, RO, konsolidasi atau penerbitan MO**. Tunggu **produk jadi aktual diterima di Packing**; alokasikan dan reservasi **SO lebih dahulu**.
- Setelah kebutuhan SO yang relevan dipenuhi/dilindungi, sistem menghitung stok produk jadi yang benar-benar dapat dipakai toko lalu **otomatis memprorata stok sisa berdasarkan Qty RO asli**, baik kekurangan maupun surplus hasil pembulatan. Admin Packing **boleh mengubah pembagian akhir secara manual sebelum pengiriman** tetapi tidak boleh mengambil stok yang sudah menjadi komitmen SO.
- **1 DO toko = 1 toko + tanggal pengiriman + slot**, **multi-SKU dari seluruh dapur**. RO tetap dipisah per dapur; DO disatukan untuk distribusi. Buat DO dari hasil alokasi final (bukan input ulang).
- Validasi Dispatch menggerakkan barang **Packing → Transit**; toko memvalidasi Receipt **Transit → Toko** berdasarkan barang fisik aktual.

### 6. Receipt toko dan discrepancy

- **Toko boleh Validate Receipt sesuai kuantitas fisik yang benar-benar diterima**, sekalipun berbeda dari DO Packing. Qty yang sesuai boleh menjadi stok jual POS tanpa menunggu investigasi item lain.
- Selisih **otomatis dicatat sebagai kasus discrepancy per SKU**, terhubung ke DO, jadwal, toko, qty dikirim/diterima, waktu, user; DO asli yang sudah Done **tidak diubah**. Sisa kurang diterima ditelusuri pada Transit sesuai perilaku transfer parsial yang harus diuji.
- Kategori investigasi: **salah hitung, barang tertinggal, salah kirim, rusak, atau belum ditemukan/hilang**. Selisih tidak otomatis menjadi inventory loss.
- **Barang rusak: pisahkan, catat SKU/qty/kondisi, lalu Scrap. TIDAK ADA RETUR untuk penanganan barang rusak ini.** Lokasi sumber Scrap harus sesuai lokasi fisik dan stock move aktual; jangan mengarang stock adjustment.
- Kasus dapat dicatat Open → In Progress → Resolved, tetapi Resolved hanya setelah tindakan korektif yang relevan selesai dan dibuktikan.

### 7. Pemisahan kewenangan anti-fraud — KEPUTUSAN PENGGUNA

**Admin Packing hanya melakukan investigasi dan mencatat hasil/permintaan tindak lanjut; DILARANG mengeksekusi koreksi stok berdasarkan investigasinya sendiri.** **Petugas yang ditunjuk** secara terpisah mengeksekusi dan memvalidasi:
- Scrap barang rusak;
- Inventory Adjustment bila sesuai hasil investigasi;
- transfer koreksi/penanganan salah lokasi.

Jejak audit harus membedakan **investigator, petugas eksekusi, dokumen koreksi, waktu, alasan, dan transaksi stok**. Tidak mengubah transaksi stock move/DO Done diam-diam. Hak akses teknis dan penunjukan personel belum diterapkan/ditetapkan rinci.

### 8. Accounting dan batas implementasi

- **Setiap pergerakan fisik** di Central → Transit → Dapur → produksi/WIP → Packing → Transit → Toko, serta Scrap/Inventory Adjustment, harus ditinjau dari **quantity, stock valuation, costing/HPP, dan jurnal/closing sesuai Odoo 19 Community + OCA aktual**. Internal transfer satu perusahaan tidak otomatis penjualan. RO dan Planning bukan jurnal atau stock move.
- Pengujian Accounting produksi/stock valuation end-to-end **BELUM LULUS**; audit Scrap 3-SKU sebelumnya bukan uji valuation. Jangan menjanjikan posting jurnal per setiap move tanpa verifikasi versi dan konfigurasi.
- Seluruh pernyataan di bagian ini adalah **rancangan yang disetujui secara konseptual**. **Belum ada addon baru atau perubahan database**, dan tidak boleh menyentuh DB utama ataupun purchasing test tanpa persetujuan eksplisit.
- **Fokus berikutnya:** detail mekanisme penanganan discrepancy (aksi penutupan, referensi stock move, kontrol peran) dan implementasi awal Master Template/Production Planning di test DB bila diminta; jangan kembali ke asumsi yang sudah dikoreksi di atas.

## Keputusan baru setelah checkpoint Planning — Max kelipatan BoM

**Keputusan pengguna (22 Nov 2026):** Max Capacity pada Planning tidak boleh angka sembarang: menggunakan **kelipatan terdekat `mrp.bom.product_qty` pada UoM hasil BoM**. Excel dapat berisi Max bebas; Preview harus menampilkan Max asli, hasil pembulatan dan **peringatan perubahan** sebelum Save Draft. Draft inline edit juga menormalisasi dengan warning. Saat Publish, Max diperiksa ulang; Published lama tidak otomatis diedit. Kelipatan seri memilih lebih rendah; 0→0. Contoh BoM 24 Pcs: 50→48, 70→72, 100→96. Implementasi sumber v`19.0.1.4.0` sudah di GitHub, **BELUM diuji/di-upgrade di server** pada checkpoint ini. Tes pure-Python: `script/test_planning_capacity_batch_pure_ya.py`. BoM output tidak bulat/invalid ditolak, tidak dipaksa konversi. Tidak ada perubahan master/BoM. Setelah lolos tes barulah melanjutkan RO toko.

## Koreksi RO Toko dan konsolidasi Packing — 22 November 2026

**Keputusan eksplisit user:** **Qty Pesan RO Toko BEBAS (integer sesuai satuan SKU), TIDAK perlu kelipatan Qty BoM dan TIDAK dibulatkan saat input/Confirm RO**. Kelipatan BoM berlaku pada **Qty Max Planning** (kapasitas), dan **Qty Produksi** yang dihitung **setelah semua RO toko digabung oleh Gudang Packing** untuk dapur, tanggal dan slot yang sama. Bila ada SO, kebutuhan SO masuk dalam konsolidasi sesuai prioritas SO yang telah disepakati. Jangan mengaplikasikan fungsi `closest_batch_multiple` ke Qty Pesan individual toko.

**Tiga kuantitas terpisah:**
1. **Planning Max Capacity:** batas produksi, telah disesuaikan ke kelipatan output BoM.
2. **RO Qty Pesan per toko:** permintaan asli, bebas dari kelipatan BoM; tetap tercatat dan tidak diam-diam diganti setelah konsolidasi.
3. **Packing Consolidated Production Qty:** jumlah kebutuhan gabungan toko (plus SO yang perlu diprioritaskan) yang disesuaikan menjadi kelipatan batch BoM untuk dasar MO, tetap dibatasi kapasitas Planning dan aturan alokasi.

**SUDAH DIPUTUSKAN:** Qty konsolidasi Packing **SELALU DIBULATKAN KE ATAS** agar semua kebutuhan dapat dipenuhi; tidak menggunakan aturan kelipatan terdekat pada Planning Max. Detail alokasi surplus dan kapasitas tetap perlu desain.

Contoh BoM 24 Pcs: RO Toko A=13, B=27, C=32 → total=72, produksi 72 (3 batch). Jika total=70, produksi 72 Pcs dengan kebijakan pembulatan ke atas. RO masing-masing tetap 13/27/32.

## Keputusan final Packing — pembulatan Qty konsolidasi SELALU KE ATAS (22 November 2026)

**KEPUTUSAN PENGGUNA (final):** jumlah pesanan RO per toko **bebas, tidak dibulatkan**. Pada saat **Gudang Packing mengonsolidasikan** seluruh permintaan satu SKU untuk tanggal pengiriman + slot + dapur (ditambah SO sesuai prioritas yang sudah disepakati), **Qty Produksi/MO harus dibulatkan SELALU KE ATAS** ke kelipatan `mrp.bom.product_qty` (dalam UoM hasil BoM). **Tidak boleh dibulatkan ke bawah atau memakai kelipatan terdekat pada tahap konsolidasi**. Rumus untuk kebutuhan positif: `Qty Produksi = ceil(Total Kebutuhan / Qty Output BoM) * Qty Output BoM`; total nol → produksi nol. Contoh BoM 24 Pcs, total kebutuhan 49 Pcs → produksi 72 Pcs (bukan 48); total 70 → produksi 72.

**Kelebihan produksi setelah memenuhi kebutuhan asli akan dikirim/dialokasikan ke toko**, bukan hilang atau dipotong dari Qty Pesan. Kuantitas RO toko tetap utuh dan terlacak; alokasi Qty tambahan harus dicatat secara terpisah dari Qty RO asli agar audit jelas. Rincian algoritma pembagian antar-toko dan penanganan bila hasil pembulatan melebihi `Planning Max Capacity` belum diputuskan; jangan mengarang kebijakan kapasitas, kekurangan, atau distribusi sebelum implementasi.

**JANGAN SALAH TERAPKAN:** fungsi `closest_batch_multiple` saat ini **khusus normalisasi Planning Max Capacity (kelipatan terdekat)**. Untuk **Packing consolidation** nanti dibutuhkan fungsi pembulatan ke atas yang **berbeda**. Tidak ada implementasi modul RO/Packing baru pada checkpoint ini; ini dokumentasi aturan untuk desain berikutnya.

## Implementasi awal RO Toko (source only, 22 November 2026)

Addon baru `addons/ya_store_ro/` ditambahkan pada GitHub untuk **tahap 1: generate Excel template per toko dari Published Planning**, dan **BELUM DIINSTALL** ke `erp-yussyakmal-mrp-test`. Wizard manager memilih satu Published Planning dan warehouse toko, lalu generates workbook `info` (identitas jadwal + toko) dan `RO` (`Reference | Nama Produk | Qty Pesan`) yang hanya mencantumkan SKU dengan Max Planning positif. Qty Pesan dikosongkan dan kelak diisi bebas tanpa pembulatan. Tidak ada model RO permanen, tombol Confirm, toko permission, import Excel, Packing atau stok yang berubah.

Tes sumber read-only tersedia: `python3 script/check_ya_store_ro_source_readonly.py`. Status sampai ada log server: **source candidate, not installed/tested**. Perlu ketentuan mapping gudang toko dan record rules sebelum digunakan toko; phase 1 dibatasi Manufacturing Manager. Baca `addons/ya_store_ro/README.md` dan dokumentasi handover.

## Hasil uji user — RO XLSX download berhasil (22 November 2026)

Feri menyatakan addon `ya_store_ro` berhasil menghasilkan dan mengunduh XLSX dan isinya **sesuai SKU dapur yang sudah Published**. Hasil ini dianggap **smoke test PASS** untuk generator template, bukan bukti RO transaksi, import Draft, store permissions, Packing consolidation atau akuntansi. Tahap berikut: import RO XLSX → Draft, Qty Pesan bebas; jangan menginstal ulang addon yang sudah berjalan.

## Checkpoint laporan uji Feri — RO Tahap 2 PASS (22 November 2026)

**Feri melaporkan seluruh flow RO Toko berhasil di GUI MRP test:** (1) upload XLSX, (2) Save Draft, (3) edit Qty Pesan pada Draft, (4) Confirm RO. Artinya **smoke test fungsional alur RO Tahap 2 PASS menurut laporan user**; belum ada bukti uji edge cases (file rusak, duplicate, pembatasan hak toko, Confirmed immutable via API, atau akuntansi). Jangan mengulang instalasi/upgrade tahap ini tanpa perubahan kode.

**Tahap 3 berikutnya: konsolidasi oleh Packing** untuk semua RO Confirmed per tanggal kirim + slot + dapur + SKU; pertahankan requested per toko, hitung kebutuhan gabungan, Qty Produksi **ceil ke kelipatan BoM** (bukan nearest/bukan down), catat surplus terpisah untuk dialokasikan ke toko, rancang penanganan Max Capacity dan prioritas SO, lalu MO dan DO/internal transfer pada tahap berikutnya. **Belum diimplementasi.** Jangan membuat transfer atau MO saat Confirm RO. Detail algoritma alokasi surplus dan kasus kapasitas belum final.

## RO-only cycle decision — prorata surplus until store receipt (22 November 2026)

**Feri decided:** Phase 1 RO-only Packing consolidation uses **PRORATA of production surplus by original requested Qty per store**. **SO is deferred entirely** from the first-cycle MO logic, and its priority/allocation rules must be revisited when SO is activated; do not implement SO logic now. Complete **one end-to-end operational cycle** first: Confirmed RO → Packing consolidation → MO/production → transfer from kitchen to Packing → Packing/Transit to store → receipt at store.

**Allocation method chosen for implementation:** deterministic **largest remainder** (Hamilton) with whole-unit Qty and store ID ascending tie-break: total required = sum of all Confirmed store RO for the same kitchen/date/slot/SKU; produced = round UP to BoM batch; surplus = produced - required; each store receives at least its original Qty, plus floor(surplus * its Requested / Total Requested), remaining units go to largest fractional remainder. Zero-request stores receive zero additional Qty; no random or manual splitting. Keep original requested, allocated surplus and final allocated as distinct quantities. Example BoM24, requests 13/27/9 → required49, produced72, surplus23 → allocated 19/40/13. This arithmetic choice requires user UI test before actual distribution.

**Source milestone (not yet deployed or GUI tested):** `addons/ya_store_ro/models/allocation_rules.py` pure calculation + `script/test_ro_packing_prorata_pure_ya.py` script. **No new Odoo view, database table, MO or stock move yet.** This file is deliberately independent of Odoo and does not affect the currently installed RO behavior. Next: source test, add Packing consolidation preview (confirmed RO only) with capacity exception if rounding up exceeds Published Max; then stage MO and warehouse moves/receipt with accounting valuation test. Do not silently cut quantity below requested or exceed Published capacity.
