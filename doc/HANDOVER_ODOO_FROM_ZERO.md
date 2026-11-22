# ODOO FROM ZERO — Handover Operasional

**Checkpoint aktif: 22 November 2026, akhir sesi Production Planning.**
**ATURAN BARU PENDING TEST (22 Nov): Max harus kelipatan terdekat Qty BoM; kode v19.0.1.4.0 sudah ada di GitHub, BELUM diuji/deploy ke Odoo server. Baca bagian "CHECKPOINT TAMBAHAN — Max Capacity" di akhir file sebelum lanjut RO.**  
**Prioritas berikutnya: desain dan implementasi RO Toko dari Published Planning; kosmetik UI/UX Planning PENDING.**  
**Panduan eksekusi addon:** [SKILL_ODOO19_ADDON_WORKFLOW.md](SKILL_ODOO19_ADDON_WORKFLOW.md).  
**Riwayat detail MRP:** [STATUS_PENGEMBANGAN_MRP.md](STATUS_PENGEMBANGAN_MRP.md).

> **PENTING — CHECKPOINT INI MENGGANTIKAN RENCANA MASTER CAPACITY TEMPLATE LAMA.** Jangan mulai lagi dari desain master 30 template atau pengauditan seluruh BoM untuk memulai Planning. Kebijakan yang disetujui sekarang adalah **upload file XLSX multi-sheet setiap pembuatan jadwal**. Bagian historis di bawah tetap berguna untuk RO/SO/MO/Distribusi, tetapi bila bertentangan, dahulukan checkpoint ini.

## CHECKPOINT TERBARU — YA Production Planning sudah berjalan di MRP TEST

### Status terbukti berdasarkan output Feri dan uji GUI

- Addon **`ya_production_planning` terinstal** pada **`erp-yussyakmal-mrp-test`**: `ir.module.module.state=installed`, empat model Planning/Header/Line/Import/Preview dikenali. **Bukan produksi**, jangan klaim live.
- **`git pull` dan SOURCE_PREFLIGHT_OK** telah berhasil. `openpyxl 3.1.2`, 10 kode Work Center dari sheet `info`, master produk/UoM, dan manifest dibaca. Kode harus **disalin ke `/opt/odoo19/custom-addons/`**, lalu **upgrade `-u` bila model/view/ACL berubah**, dan **restart `odoo19.service`** agar proses web memuat field Python.
- File acuan **`template_jadwal(1).xlsx`** (file operasional milik pengguna; **jangan masukkan file master privat ke GitHub publik**). Sheet `info`: `NO | Sheet | Code Dapur`; 10 sheet dapur: `DAPUR | Product | Max | Unit`, `Product` berbentuk `[Reference] Nama Produk`. SOP pengguna adalah validasi pertama daftar SKU per sheet.
- Importer melakukan **Upload → Validate & Preview → Save Draft**. Satu workbook untuk **tanggal kirim + slot** (S1 05.00, S2 09.00, S3 11.00 WIB) dapat menghasilkan dokumen per dapur. Dari screenshot/operator, **Draft per dapur dan daftar SKU sudah tersimpan**; ada bukti notifikasi `Created Draft: ASN, GRG, PST, ROTI, TART` pada satu upload. **Jangan menganggap semua skenario sudah lulus uji otomatis.**
- Keputusan final: **Publish This Kitchen** satu dapur saja; Draft lain tidak ikut. **Satu daftar Planning menampilkan Draft dan Published**, filter status. **Max boleh diedit operator saat Draft, terkunci setelah Published**. UI kecil/kosmetik ditunda setelah pengguna menyatakan flow benar.
- **Re-upload** menurut desain/kode: identitas `tanggal kirim + slot + kode dapur`. Jika belum ada → **CREATE Draft**; sudah Draft → **REPLACE semua SKU/Max dapur tersebut**; sudah Published → **SKIP tanpa mengubah**; dapur tidak ada pada workbook → tidak diubah. Preview dan notifikasi memberi ringkasan CREATE/REPLACE/SKIP. **Belum ada hasil tes lengkap seluruh kombinasi Published + Draft bersamaan**.
- UI final yang **dinyatakan sesuai flow oleh pengguna**: menu **Upload Planning** → **List Planning** → tombol **Upload Baru** → form XLSX. Menu/list tetap menampilkan Draft dan Published. Versi kode terakhir pada repository: **`19.0.1.3.0`** (cek manifest aktual saat sesi baru; jangan asumsikan versi server sama hanya dari GitHub).
- **UoM**: dari BoM Header hasil produksi (`mrp.bom.product_uom_id`), **bukan harus sama dengan UoM stok master**. Audit global 955 BoM: 902 UoM sama, 53 berbeda; 29 error importer yang dikirim pengguna adalah kasus UoM Excel/BoM berbeda dari master. Validasi sekarang mencari satu BoM produk pada Warehouse `DAPUR` dan mengecek UoM hasil BoM. **Tidak ada konversi UoM otomatis**.
- Dapur **Premik** membuat bahan produksi, **Dahlia 5/Trial** bukan dapur produksi reguler; **Packing** merakit paket. Mereka bukan 10 sheet Planning yang disepakati. Pemeriksaan 955 BoM pernah menampilkan Premik karena auditnya global; **jangan tambahkan Premik ke upload Planning toko**.
- Error `line_row field undefined` dulu disebabkan XML database baru sementara kode Python servis masih lama; pemecahan dengan deploy/upgrade/restart. Error browser `Cannot read properties of undefined (reading 'map')` terjadi **sesudah Save Draft berhasil**, pada action navigasi yang tak punya `views`; kode kemudian ditambah `views: [(False,'list'),(False,'form')]`. **Jangan upload ulang secara membabi buta bila notifikasi Created sudah muncul**—cek list dulu.
- **Planning hanya batas kapasitas**, belum membuat RO, SO, MO, stock move, jurnal atau HPP. **RO toko BELUM diimplementasikan**: Published Planning dengan Max > 0 akan menjadi sumber SKU yang dapat diminta toko saat modul RO dibuat.

### Keputusan tahap selanjutnya

1. **Stop polishing minor UI Planning** hingga modul RO berlanjut; jangan audit ulang Work Center/BoM/Premik hanya untuk membuat RO.
2. **RO toko**: satu RO per **toko + dapur + tanggal kirim + slot**, SKU hanya dari **Published Planning** dapur/jadwal tersebut dengan Max > 0. Qty Pesan diisi toko via template XLSX RO; Draft → Confirmed. Satu file Planning dan file RO adalah dua proses berbeda.
3. Setelah RO: Close oleh Packing per tanggal+slot, konsolidasi RO/SO → MO per SKU/dapur/jadwal, material replenishment Central→Transit→Dapur, produksi, alokasi SO dulu lalu toko dari stok aktual Packing, DO gabungan per toko+tanggal+slot; discrepancy dan anti-fraud sesuai catatan historis.
4. Accounting/valuation/WIP/HPP wajib diperiksa untuk **pergerakan fisik**, bukan otomatis untuk upload Planning/RO. **Accounting produksi end-to-end belum PASS**.

### Jangan ulang kesalahan saat sesi baru

Baca **[SKILL_ODOO19_ADDON_WORKFLOW.md](SKILL_ODOO19_ADDON_WORKFLOW.md)** sebelum menjalankan perintah terminal. **Jangan kirim ZIP manual**, kode lewat GitHub → `git pull`; jangan membaca script dalam `/home/feri` sebagai `odoo19`; untuk tes source gunakan `python3` sebagai `feri`; untuk Odoo shell gunakan `sudo -u odoo19 ... < script/name.py`; jangan lupakan copy addon aktif, `-i` untuk instalasi pertama, `-u` untuk upgrade XML/ACL/model, restart service, dan baca exit code/log. Backup lewat GUI adalah pilihan pengguna.

---

## 1. Prinsip dan batas proyek

**Pahami Odoo terlebih dahulu, tetapkan policy setelah dipelajari.** Jangan menyalin policy, data historis atau asumsi dari proyek/bisnis lain. Bedakan keputusan user, standar Odoo, hasil tes aktual, dan usulan. Tidak ada policy larangan stok minus atau approval Scrap yang telah diputuskan di proyek ini.

**Database:**
- **Aktif untuk pengembangan & pengujian:** `erp-yussyakmal-mrp-test`
- **JANGAN DISENTUH:** `erp-yussyakmal` (utama)
- **JANGAN DISENTUH:** `erp-yussyakmal-integer-test` (checkpoint Purchasing)

**Lingkungan:** Ubuntu + Odoo 19 Community, Odoo Python `/opt/odoo19/venv/bin/python3`, binary `/opt/odoo19/odoo/odoo-bin`, config `/etc/odoo19.conf`; custom addons aktif di `/opt/odoo19/custom-addons`; repository `~/odoofromzero`, GitHub `yussyakmal-dotcom/odoofromzero`. Jangan menganggap `git pull` saja sudah memperbarui addon aktif. Jangan commit data master privat ke repo publik.


## 2. Fokus arsitektur saat ini — RO toko dahulu (BELUM IMPLEMENTASI)

**Sumber keputusan:** diskusi pengguna 22 November 2026. Detail lengkap dan daftar celah ada pada bagian **“22 November 2026 — Desain Replenishment Toko, Konsolidasi MO, dan Prioritas SO”** dalam [STATUS_PENGEMBANGAN_MRP.md](STATUS_PENGEMBANGAN_MRP.md). Desain dasar berasal dari PDF pengguna “Dokumentasi Alur Kerja Sistem ERP Odoo 19 Community”; jalur SO merupakan penambahan.

### Alur toko yang HARUS dikerjakan lebih dulu

- **Setiap SKU mempunyai dapur produksi tetap**; gudang **Packing** adalah tempat konsolidasi hasil produksi lintas dapur dan distribusi, bukan dapur penghasil SKU.
- **1 dokumen RO per toko per dapur** (dalam siklus/jadwal permintaan terkait), dapat berisi banyak SKU dapur itu. Contoh toko memerlukan barang dari **8 dapur → 8 dokumen RO**; jangan membuat satu RO gabungan semua dapur. Rincian kunci tanggal/jadwal per dokumen masih perlu difinalkan.
- **Entry melalui template Excel .xlsx per dapur**: Reference | Nama Produk | Qty Pesan. Daftar 50–200 SKU sudah terisi dari master produk; operator **hanya mengisi Qty Pesan**, lalu unggah. Reference menjadi kunci SKU; verifikasi kecocokan dapur. Untuk kosong/0, duplikat, invalid qty dan upload ulang, rancang validasi yang jelas sebelum coding.
- Konsolidasi **semua RO toko per dapur + jadwal produksi + SKU**, terapkan batas kapasitas PPIC dan kelipatan BoM, **prorata** kuantitas toko jika perlu, lalu hasilkan **satu MO per SKU/jadwal/dapur** sesuai hasil konsolidasi (bukan MO per RO).
- Pisahkan dan simpan **Qty Requested**, **Qty Allocated**, **Qty Delivered** untuk setiap toko/SKU. Permintaan asli tidak dihapus jika alokasi berkurang.
- Hasil fisik: **Dapur → Transit → Packing → Transit → Toko**, dengan validasi pengiriman/penerimaan sesuai tahapan yang nanti diuji.

### SO adalah tahap tambahan SETELAH alur RO matang

- SO lazimnya dibuat **2–3 hari sebelum tanggal pengiriman** dengan volume sekitar **10–50 order/hari**, bukan transaksi instan seperti POS.
- Satu SO dapat berisi SKU dari banyak dapur. **Confirm seluruh SO atau gagal seluruhnya**: semua baris harus lolos; jangan reservasi parsial.
- **Validasi PERTAMA pada Confirm SO:** status **Production Schedule** dan **Delivery Schedule** yang relevan harus **Open**. Jika salah satunya **Locked**, tolak konfirmasi tanpa perlu mengecek kapasitas lebih lanjut. Status MO sudah diterbitkan **tidak sama** dengan jadwal Locked.
- Jika Open, cek kapasitas masing-masing SKU/dapur/jadwal, termasuk kapasitas toko yang masih bisa dialihkan dan batas kelipatan BoM.
- **SO lebih prioritas dari RO toko.** Walau MO sudah terbit, SO baru bisa mengambil **seluruh alokasi toko yang belum dikirim** selama jadwal masih Open dan memang cukup kapasitas; **prorata toko dijalankan otomatis tanpa persetujuan PPIC**.
- **Barang yang sudah dikirim dari Packing ke Transit tidak boleh diambil melalui realokasi biasa.** Jika pengiriman/picking masih belum Done, desain harus menangani pelepasan reservasi dengan benar; kuantitas Delivered tidak berubah.
- Pastikan tidak ada **MO ganda** dari konfirmasi SO standar/MTO sekaligus engine konsolidasi khusus. Konfirmasi, pengecekan lock, reservasi kapasitas seluruh SKU dan prorata toko harus konsisten satu transaksi.

### Jangan memutuskan aturan yang belum disetujui pengguna

Belum diputuskan: siapa yang membuat/mengunci/membuka jadwal, apakah RO boleh direvisi setelah lock, hubungan beberapa jadwal produksi dalam satu RO, pilihan jadwal jika SKU dalam SO berbeda dapur, exception hasil MO kurang, detail kebijakan SO dibatalkan/diubah, dan alur shortage setelah sebagian barang dikirim. Jangan membuat keputusan diam-diam.

### Batas pelaksanaan

**Belum ada addon/skrip khusus RO/Allocation Engine yang dikerjakan, belum ada konfigurasi/rute/DB yang diubah oleh diskusi ini, dan belum ada tes implementasi.** Langkah terdekat adalah menyelesaikan detail RO Excel per dapur dan konsolidasi toko dahulu, kemudian **hanya bila diminta** buat implementasi di DB erp-yussyakmal-mrp-test dengan tes kecil/rollback. Tidak perlu audit besar ulang struktur Odoo default.


## Integrasi Accounting wajib sejak desain (22 November 2026)

**Keputusan/arah pengguna:** semua proses **RO, SO, Inventory, Internal Transfer, MO, WO, Packing, pengiriman, Scrap dan penyesuaian stok** harus ditelaah bersamaan dengan Accounting di belakangnya. **Jangan mendesain hanya kuantitas dan kemudian menambahkan akuntansi belakangan**. Ini kewajiban desain; **belum ada perubahan DB atau tes akuntansi produksi**.

- **RO/Allocation/Production Plan dan SO Confirm** adalah tahap permintaan/komitmen, **bukan otomatis jurnal persediaan atau HPP**.
- **Receipt pembelian, Central → Transit → Dapur, konsumsi bahan ke WIP/produksi, MO Done, Dapur → Packing, Packing → Toko, pengiriman SO ke customer, Scrap/opname/return** masing-masing harus dipetakan dampaknya ke **saldo stok, nilai stok, biaya MO, HPP, akun produksi, dan pencatatan akuntansi/closing yang benar**.
- **Transfer toko bukan otomatis penjualan**, apabila tetap berada dalam perusahaan/pemilik stok yang sama; status lintas perusahaan dan tipe lokasi perlu diverifikasi, bukan diasumsikan.
- **Odoo 19 mengubah cara/timing pencatatan valuation vs accounting** dari versi lama: **jangan anggap tiap stock move pasti membuat journal entry**. Periksa metode valuation/costing dan modul/accounting setup aktual di Odoo 19 Community + OCA yang terpasang sebelum mengambil keputusan teknis.
- Untuk tiap skenario uji nanti, periksa **(1) qty dan status move** serta **(2) inventory valuation, costing MO/WIP, dampak accounting dan rekonsiliasi** jika relevan. Stok awal pada MRP test belum ada; lakukan pengujian terkendali/rollback dan jangan sentuh DB utama.
- **Status integrasi Accounting Inventory–Manufacturing: BELUM DIUJI END-TO-END**. Keberhasilan audit jurnal Vendor Bill atau stok dalam pengujian Scrap tidak membuktikan siklus accounting produksi sudah benar.

**Jalur pekerjaan tetap: RO toko per dapur + Excel → konsolidasi RO → kapasitas/prorata → MO → distribusi; lalu SO.** Pada **setiap langkah** tambahkan *accounting impact check* yang relevan, bukan membuat modul Accounting terpisah di ujung proyek.

Rincian matriks dampak tiap transaksi dan sumber Odoo 19 ada di [STATUS_PENGEMBANGAN_MRP.md](STATUS_PENGEMBANGAN_MRP.md) bagian **Integrasi Accounting pada Inventory dan Manufacturing**.


## Checkpoint keputusan terbaru — Delivery Schedule, Planning, Distribusi, dan Anti-Fraud

**22 November 2026. DESAIN, BELUM IMPLEMENTASI.** BAGIAN INI MENGGANTIKAN KESIMPULAN LAMA YANG BERTENTANGAN. Dokumen status terbaru memuat uraian lengkap pada bagian “Keputusan desain terbaru: Planning, RO, MO, Packing, DO, selisih, anti-fraud”.

**Kunci jadwal:** tepat 3 slot tetap per hari kirim: **S1 Subuh 05.00 WIB, S2 Pagi 09.00 WIB, S3 Siang 11.00 WIB**. Seluruh planning, RO, konsolidasi, SO dan DO terhubung **tanggal kirim + slot**. Tanggal produksi hanya informasi (produksi lintas tengah malam); bukan dasar lock/penyatuan MO. Close/lock per tanggal-slot, tidak merembet ke slot lain.

**Mulai dari Production Planning PPIC, BUKAN Packing membuka pesanan:**
1. **3 × jumlah dapur** Master Capacity Template (misal 10 dapur = 30 template) berisi Reference, Nama Produk, Max Capacity per SKU. **Export/Import Excel untuk MASTER TEMPLATE saja**; tidak ada Excel upload pada planning harian.
2. Admin Produksi **Generate Planning Massal** untuk tanggal kirim, slot, dan dapur yang dipilih → satu Draft per dapur/tanggal/slot berisi salinan kapasitas standar → edit langsung bila perlu → Publish. Jangan mengubah template akibat koreksi Draft; jangan menggandakan kombinasi dokumen.
3. SKU **Max Capacity = 0 tidak muncul/boleh dipesan toko** untuk slot tersebut. Hindari menyalahgunakan Work Center capacity per-cycle sebagai batas produksi per jadwal.

**RO toko:** satu RO **per toko + dapur + tanggal kirim + slot**; header punya **tanggal pesan** serta tanggal/jam kirim. Draft → Confirmed. Operator **download/upload Excel Reference, Nama Produk, Qty Pesan**; hanya SKU yang ada pada Published Planning dengan kapasitas positif dan dapur sesuai boleh masuk. Reject SKU tambahan/salah dapur/duplikat/qty invalid ketika upload; qty kosong/0 tidak dimasukkan; upload ulang Draft mengganti bukan menjumlah. Qty RO adalah permintaan, **bukan garansi kuantitas kirim**.

**Packing:** Admin Packing **hanya menutup** akses pemesanan RO per tanggal+slot, **tidak membuka** jadwal dan tidak menunggu tombol “selesai memesan” dari toko. Setelah Close, konsolidasi RO Confirmed per dapur/SKU/jadwal bersama SO dan kapasitas PPIC, pembulatan kelipatan BoM → **MO satu SKU per dapur + jadwal**. **JANGAN mengalokasikan final ke toko pada saat konsolidasi.**

**Material supply wajib antara MO dan produksi:** konsolidasi kebutuhan komponen BoM seluruh MO per dapur/jadwal, perhitungkan stok dapur, **Internal Transfer Central → Transit → Dapur**, dapur konfirmasi receipt; lalu MO/WO konsumsi dan produksi, kirim produk jadi **Dapur → Transit → Packing**.

**SO prioritas:** satu SO boleh multi-SKU lintas dapur; semua baris wajib lolos untuk Confirm, validasi **jadwal pengiriman Open/Locked pertama**, lanjut kapasitas per SKU; bisa mengambil kuota toko belum dikirim walau MO terbit, selama slot Open. Volume realistis 10–50 SO/hari dan lead time 2–3 hari; jangan membuat logika POS. Jangan menciptakan MO ganda dari native SO/MTO dan engine.

**Di Packing, saat barang jadi AKTUAL tersedia dan hendak dikirim:** alokasikan/reservasi SO **terlebih dulu**, lalu **sistem prorata otomatis stok sisa kepada toko berdasarkan RO**, termasuk surplus akibat batch BoM; **Admin Packing boleh mengubah alokasi final toko** selama tidak mengambil kuota SO. Baru **generate 1 DO per toko + tanggal + slot** yang menggabungkan SKU seluruh dapur. DO Dispatch Packing → Transit; toko Receipt Transit → Toko berdasarkan fisik.

**Penerimaan toko dan selisih:** Toko **boleh Validate Receipt sesuai Qty fisik** meskipun berbeda dari DO; discrepancy otomatis tercatat per SKU dan ditindaklanjuti setelahnya. Jenis investigasi: salah hitung, tertinggal, salah kirim, rusak, belum ditemukan. DO/stock move Done asli tidak diam-diam diubah; kekurangan Transit/receiving parsial perlu tes operasional.

**Keputusan KONTROL FRAUD (penting):**
- **Barang rusak dipisahkan, jumlah/kondisi dicatat, lalu Scrap; TIDAK ADA RETUR untuk kasus barang rusak ini.**
- **Admin Packing HANYA investigasi dan mencatat hasil/pengajuan koreksi; TIDAK BOLEH validasi Scrap, Inventory Adjustment atau transfer koreksi.**
- **Petugas terpisah yang ditunjuk** mengeksekusi/validasi koreksi sesuai bukti. Simpan ID investigator, eksekutor, referensi discrepancy dan transaksi, alasan serta waktu. Kasus selesai ketika transaksi koreksi dan cek stok yang diperlukan selesai, bukan sekadar memilih alasan.
- Hak akses aktual/petugas belum dikonfigurasi. **Ini desain Segregation of Duties**, bukan bukti kontrol sudah berjalan.

**Accounting wajib setiap tahap:** cek qty, valuation, WIP/MO costing, HPP, akuntansi/closing sesuai Odoo 19 Community + OCA aktual. Pergerakan internal dalam satu perusahaan bukan otomatis penjualan, dan Planning/RO bukan jurnal. **Belum ada uji Accounting end-to-end.** Jangan ubah DB produksi atau DB Purchasing test.

**Lanjutan yang benar:** diskusi/implementasi terarah Master Capacity Template dan Planning di MRP test hanya setelah diminta; lalu RO toko, konsolidasi, material supply, produksi, distribusi dan penanganan discrepancy. Jangan kembali mengasumsikan alokasi toko final saat Generate MO atau Packing membuka jadwal.

## 3. Yang sudah selesai

### Manufacturing master
- 16 Work Center; 955 BoM; 8.502 BoM component lines; 14 Manufacturing Operation Types; tidak ada Work Order Operations.
- Koreksi UoM 73 SKU telah selesai dan diaudit (lihat status teknis). Jangan impor ulang BoM maupun perubahan UoM tanpa kebutuhan baru.
- Uji MO persyaratan bahan pernah lulus rollback; test DB tidak mempunyai saldo stok awal. Belum ada bukti penuh MO selesai dengan valuasi/akuntansi produksi.

### Scrap setup
- Pengguna mengakhiri audit perbandingan Scrap versus Opname; fokus pada Multi-SKU Scrap.
- Keputusan: satu virtual lokasi tujuan **Scrap** untuk Central, semua dapur dan seluruh toko; **satu lokasi asal per dokumen**, satu Source Document, satu alasan, banyak SKU.
- Pembuatan lokasi dan alasan telah **APPLY COMMITTED** pada MRP test: lokasi Scrap ID 248, reason tag Rusak ID 3, Expired ID 4. Ini **ID pada MRP test saja**, bukan ID global.
- Master alasan menggunakan model bawaan `stock.scrap.reason.tag`; reason dalam `stock.scrap` adalah `scrap_reason_tag_ids`.
- Alasan hanya dapat **dipilih**, tidak dibuat baru dari form `Multi-SKU Scrap` (pengaturan no_create/no_create_edit/no_quick_create pada UI). Belum ada keputusan pembatasan admin global.

### Addon Multi-SKU Scrap
- Sumber: `addons/ya_scrap_multi` — installed pada MRP test menurut hasil SQL `state=installed`; menu dan form sudah muncul dan dinyatakan OK oleh pengguna.
- Model parent `ya.scrap.batch`, lines `ya.scrap.batch.line`, native `stock.scrap` terhubung melalui `ya_batch_id`.
- Tombol **Validate All Scrap** membuat 1 native Scrap per baris dan memanggil `stock.scrap.action_validate()`. Semua berhasil bersama atau rollback jika gagal.
- Excel (.xlsx): kolom `SKU, Quantity, UoM`; baris ditambahkan di Draft, UoM kosong mengikuti unit produk, tersedia template unduh, maksimum 1000 baris tiap impor. **Kode ada; workflow Excel belum lulus tes terpisah.**
- Bug versi awal `uom.uom.category_id` tidak tersedia di Odoo 19, diperbaiki menggunakan `_has_common_reference()` di commit `014fe71`.

## 4. Bukti tes terbaru: 3 SKU → 3 Scrap → 1 Batch (PASS)

**Asal informasi:** output terminal pengujian yang user berikan.  
**Script:** `script/test_multi_scrap_3sku_e2e_rollback_ya.py`  
**Target DB:** `erp-yussyakmal-mrp-test`  
**Hasil:** `TEST_EXIT_CODE=0`, `E2E_3_SKU_3_NATIVE_SCRAPS_1_BATCH_OK`, `E2E_3_SKU_ROLLBACK_CONFIRMED`.

| SKU | Quantity | Native Scrap | Stock Move | Sisa stok sementara |
|---|---:|---|---:|---:|
| 10440 | 1 | SP/00001 | 46 | 9 |
| 10180 | 2 | SP/00002 | 47 | 8 |
| 10182 | 3 | SP/00003 | 48 | 7 |

Ketiganya memiliki alasan **Rusak**, Source Document `YA-E2E-3SKU-ROLLBACK`, sumber `TART/Stock`, tujuan `Scrap` dan parent batch `SCRB/2026/00003`. Tiga native Scrap dan tiga Stock Move berstatus Done; stok berkurang sesuai jumlah masing-masing.

**PENTING:** Output di atas **hanya terjadi dalam transaksi uji dan sudah di-rollback**. Nomor/id transaksi dan stok sementara **tidak menetap** di DB.

## 5. Masih harus diuji (jangan klaim PASS)

1. **Impor Excel Draft:** jalankan `script/test_multi_scrap_xlsx_rollback_ya.py` dan cek data SKU sampel script dahulu; lakukan juga tes impor tiga SKU melalui UI.
2. **Alur GUI:** dokumen Draft, tambah manual, template unduh, impor, validasi, buka 3 native scraps via smart button.
3. **Pembatasan alasan UI:** pastikan user biasa tidak bisa membuat alasan baru pada field header, dan tag master tetap bisa dipilih.
4. **Error handling:** SKU tidak ditemukan / duplikat, UoM tak kompatibel, Qty nol/negatif, satu baris gagal -> seluruh dokumen tidak posting parsial.
5. **Batasan yang belum diuji:** barang ber-lot/serial, multi-company, laporan akuntansi kerugian Scrap, penerapan pada gudang/toko lain, hak akses operasional.

**Bukan tugas sekarang:** mengulang audit Scrap versus Opname, mengulang impor BoM, atau merancang policy yang tidak diminta.

## 6. Langkah teknis aman

1. `cd ~/odoofromzero && git pull` untuk sinkronisasi Git.
2. Untuk perubahan addon, deploy folder `addons/ya_scrap_multi/` ke `/opt/odoo19/custom-addons/ya_scrap_multi/`, periksa hak akses dan perbedaan file; **jangan upgrade DB lain**.
3. Jika diperlukan, upgrade hanya `erp-yussyakmal-mrp-test`:
   ```bash
   sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin \
     -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test \
     -u ya_scrap_multi --stop-after-init --no-http
   ```
4. Uji dengan Odoo shell `--no-http` dan skrip rollback, baca exit code serta log; jangan tinggalkan saldo stok hasil simulasi.
5. Setelah hasil valid, perbarui status dan handover ini. Perlu persetujuan user sebelum promosi keluar DB test.

## 7. Pesan singkat untuk sesi berikut (TERBARU)

> **BACA CHECKPOINT AKTIF DI AWAL DOKUMEN DAN SKILL INSTALASI.** `ya_production_planning` sudah terinstal dan flow upload XLSX multi-sheet → Preview → Save Draft → Publish per dapur telah dipakai di MRP test. Menu Upload Planning membuka list, tombol Upload Baru membuka wizard. Reupload CREATE/REPLACE Draft/SKIP Published. Kosmetik UI pending. **Selanjutnya bangun RO Toko dari Published Planning (Max > 0)**; jangan kembali ke Master Capacity Template permanen atau mengulang audit BoM. Tidak ada RO yang berjalan saat checkpoint ini. Perintah GitHub/deploy/upgrade/restart ada dalam `doc/SKILL_ODOO19_ADDON_WORKFLOW.md`. Hanya `erp-yussyakmal-mrp-test`; DB utama dan Purchasing test tidak disentuh. Aturan SO prioritas, Packing/Transit, anti-fraud, serta Accounting pada tahapan fisik tetap seperti riwayat.

## CHECKPOINT TAMBAHAN — Max Capacity harus kelipatan hasil BoM (22 November 2026)

**Keputusan terbaru pengguna, lebih tinggi prioritas dari catatan Max sebelumnya:** Qty **Max Capacity pada Planning harus merupakan kelipatan terdekat dari `mrp.bom.product_qty` (output BoM Header)**, dalam UoM BoM. Jika user memberikan angka tidak kelipatan, sistem menghitung nilai paling dekat dan memperlihatkan perubahan **angka asal → angka baru**; jika dua pilihan berjarak sama, versi awal memilih kelipatan lebih rendah. Nol tetap nol. Misalnya BoM 24 Pcs: 50→48, 70→72, 100→96, 120→120.

**Kode dibuat di GitHub `ya_production_planning` v19.0.1.4.0, status belum diuji di server.** Import XLSX: Preview memperlihatkan `Excel Max`, `BoM Output`, `Adjusted Max`, `Adjusted?` dan aksi Create/Replace/Skip. **Save Draft** menggunakan nilai adjusted yang telah ditinjau; Published yang di-SKIP tidak berubah. Edit Max langsung di Draft: `@api.onchange` mengubah ke kelipatan terdekat dan memunculkan warning; validasi ORM menolak angka yang tidak sesuai jika onchange dilewati. Sebelum Publish per dapur, semua Max diperiksa. **Data Draft/Published lama tidak dinormalisasi massal secara diam-diam**; Draft lama yang tidak kelipatan perlu diedit sebelum Publish.

**Batasan:** karena field `Max` Integer, BoM output dengan pecahan/<=0 belum dapat dinormalisasi otomatis; importer menampilkan error agar data diperiksa. Konversi UoM stok dan pembuatan MO tetap belum diimplementasikan. Tidak boleh menganggap kode lulus UI sampai `script/test_planning_capacity_batch_pure_ya.py`, preflight, deploy, upgrade, restart, dan GUI test PASS. Skill instalasi: [SKILL_ODOO19_ADDON_WORKFLOW.md](SKILL_ODOO19_ADDON_WORKFLOW.md).

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

## CHECKPOINT BERIKUT — RO Toko tahap 1: template XLSX (22 November 2026)

**Baru dibuat di GitHub, BELUM di-install dan BELUM diuji di server**: addon terpisah `addons/ya_store_ro/`, dependensi `ya_production_planning`, dengan wizard manager-only **RO Toko - Download Template**. Input: Published Planning **satu dapur + tanggal kirim + slot**, serta gudang toko (warehouse) pilihan; hasil file `RO_YYYYMMDD_SLOT_DAPUR_TOKO.xlsx` berisi sheet `info` (Planning ID, tanggal, slot, dapur, toko, identitas format) dan sheet `RO` (**Reference | Nama Produk | Qty Pesan**). Hanya SKU dari Planning Published dengan Max > 0. Qty Pesan kosong untuk toko dan kelak **bebas integer tanpa pembulatan**.

**Batas fase:** tombol ini baru **generator template**, BELUM ada upload RO, Draft/Confirmed, data RO toko, akses toko/store role, Packing Close, MO, stock move atau accounting. Pemilihan warehouse toko belum dibatasi otomatis karena flag toko belum disepakati; pada uji pilih hanya warehouse toko sungguhan. Jangan klaim siap digunakan operasional toko. Ketika membuat import RO nanti, metadata spreadsheet harus divalidasi terhadap record Published; tidak dipercaya sebagai kebenaran tanpa pemeriksaan.

**Aturan Packing dari keputusan user:** saat konsolidasi semua RO dan SO terkait, Qty Produksi dibulatkan **SELALU KE ATAS** ke kelipatan output BoM; surplus dikirim/alokasikan ke toko dengan Qty RO asli tetap dipertahankan dan jejak tambahan terpisah. Tidak menggunakan aturan Max Planning kelipatan terdekat untuk Qty RO individual.

**Langkah berikut yang aman:** `cd ~/odoofromzero && git pull && python3 script/check_ya_store_ro_source_readonly.py`. Harap `RO_TEMPLATE_SOURCE_PREFLIGHT_OK`. **Jangan install dulu** sampai kode/UX dan daftar gudang toko diperiksa. Baca `addons/ya_store_ro/README.md` dan `doc/SKILL_ODOO19_ADDON_WORKFLOW.md`.

## Hasil uji Feri — generator template RO XLSX berhasil (22 November 2026)

**Bukti laporan Feri:** addon `ya_store_ro` sudah dijalankan di Odoo server MRP test; Feri berhasil **Generate dan Download XLSX**, serta memeriksa isi template: **SKU sesuai daftar SKU pada dapur yang Published**. Ini **PASS untuk smoke test unduh dan kecocokan SKU menurut pemeriksaan pengguna**, bukan uji penuh akses toko atau alur RO. Jangan mengulang source preflight maupun instalasi pertama addon ini pada sesi baru; status instalasi sebaiknya tetap diverifikasi pada DB bila diperlukan. Source preflight sebelumnya `RO_TEMPLATE_SOURCE_PREFLIGHT_OK`.

**Checkpoint selanjutnya:** buat proses upload XLSX RO → Draft (toko + dapur + tanggal kirim + slot); validasi Reference hanya dari Published Planning, Qty Pesan bebas integer tanpa pembulatan, pengelolaan hak akses toko, lalu Confirm RO. Pembulatan Qty produksi **selalu ke atas** hanya nanti pada konsolidasi Packing. Tetap database `erp-yussyakmal-mrp-test`.

## Decision confirmed by Feri — RO Draft editable; Confirm is final validation

Excel **only speeds up input**. Once imported and saved as Draft RO, operator may **edit Qty Pesan directly in Odoo** and save repeatedly. No batch rounding on individual store quantities. **Confirm RO is the last validation/commit point**: verify Published Planning, eligible SKU, Qty integer/nonnegative, and at least one positive Qty. Confirmed RO immutable; reupload cannot overwrite Confirmed. Source implementation in addon `ya_store_ro` `19.0.2.0.0` committed to GitHub but **has not yet passed server install/upgrade or GUI tests**. Packing consolidation and internal transfer remain next stages; Qty production rounded UP to BoM multiple only in Packing.

## Checkpoint laporan uji Feri — RO Tahap 2 PASS (22 November 2026)

**Feri melaporkan seluruh flow RO Toko berhasil di GUI MRP test:** (1) upload XLSX, (2) Save Draft, (3) edit Qty Pesan pada Draft, (4) Confirm RO. Artinya **smoke test fungsional alur RO Tahap 2 PASS menurut laporan user**; belum ada bukti uji edge cases (file rusak, duplicate, pembatasan hak toko, Confirmed immutable via API, atau akuntansi). Jangan mengulang instalasi/upgrade tahap ini tanpa perubahan kode.

**Tahap 3 berikutnya: konsolidasi oleh Packing** untuk semua RO Confirmed per tanggal kirim + slot + dapur + SKU; pertahankan requested per toko, hitung kebutuhan gabungan, Qty Produksi **ceil ke kelipatan BoM** (bukan nearest/bukan down), catat surplus terpisah untuk dialokasikan ke toko, rancang penanganan Max Capacity dan prioritas SO, lalu MO dan DO/internal transfer pada tahap berikutnya. **Belum diimplementasi.** Jangan membuat transfer atau MO saat Confirm RO. Detail algoritma alokasi surplus dan kasus kapasitas belum final.

## RO-only cycle decision — prorata surplus until store receipt (22 November 2026)

**Feri decided:** Phase 1 RO-only Packing consolidation uses **PRORATA of production surplus by original requested Qty per store**. **SO is deferred entirely** from the first-cycle MO logic, and its priority/allocation rules must be revisited when SO is activated; do not implement SO logic now. Complete **one end-to-end operational cycle** first: Confirmed RO → Packing consolidation → MO/production → transfer from kitchen to Packing → Packing/Transit to store → receipt at store.

**Allocation method chosen for implementation:** deterministic **largest remainder** (Hamilton) with whole-unit Qty and store ID ascending tie-break: total required = sum of all Confirmed store RO for the same kitchen/date/slot/SKU; produced = round UP to BoM batch; surplus = produced - required; each store receives at least its original Qty, plus floor(surplus * its Requested / Total Requested), remaining units go to largest fractional remainder. Zero-request stores receive zero additional Qty; no random or manual splitting. Keep original requested, allocated surplus and final allocated as distinct quantities. Example BoM24, requests 13/27/9 → required49, produced72, surplus23 → allocated 19/40/13. This arithmetic choice requires user UI test before actual distribution.

**Source milestone (not yet deployed or GUI tested):** `addons/ya_store_ro/models/allocation_rules.py` pure calculation + `script/test_ro_packing_prorata_pure_ya.py` script. **No new Odoo view, database table, MO or stock move yet.** This file is deliberately independent of Odoo and does not affect the currently installed RO behavior. Next: source test, add Packing consolidation preview (confirmed RO only) with capacity exception if rounding up exceeds Published Max; then stage MO and warehouse moves/receipt with accounting valuation test. Do not silently cut quantity below requested or exceed Published capacity.

## Koreksi KRITIS alur end-to-end: replenishment bahan sebelum MO berjalan (22 November 2026)

**Keputusan eksplisit Feri — menggantikan alur ringkas sebelumnya yang melewatkan tahapan bahan baku.**

Alur RO-only untuk satu siklus sampai toko menerima barang:
1. **RO toko Confirmed** per toko/dapur/tanggal kirim/slot.
2. **Packing mengonsolidasikan RO** per SKU/dapur/tanggal kirim/slot. Produksi dibulatkan **SELALU KE ATAS** sesuai output BoM. Surplus dialokasikan **PRORATA** berdasarkan Qty RO asli; SO belum diaktifkan dalam siklus ini.
3. **Generate MO per SKU/jadwal/dapur** dari hasil konsolidasi (MO boleh dibuat pada tahap ini, **tetapi dilarang menjalankan MO/WO sebelum material ready**).
4. **Material Replenishment**: hitung kebutuhan komponen BoM MO, periksa stok yang tersedia di **gudang produksi/dapur** (dengan memperhitungkan komitmen/reservasi lain agar tidak double count), tentukan kekurangan bahan per dapur.
5. Kekurangan bahan memicu **permintaan Internal Transfer Gudang Central → Gudang Produksi/Dapur**. **Central menghasilkan Picking List** untuk mengumpulkan seluruh kebutuhan bahan **dikelompokkan per dapur**. Validasi bahwa permintaan tidak menduplikasi pemindahan bahan yang sudah dilakukan.
6. **Central picking/dispatch dan internal transfer**, lalu **gudang produksi/dapur melakukan konfirmasi penerimaan** (alur multi-step dengan status dan kuantitas yang terlacak; bukan hanya marking request as done).
7. **Availability Gate wajib:** setiap komponen BoM yang dibutuhkan MO harus **benar-benar available di lokasi dapur** setelah penerimaan (dengan cek stok bebas reservasi sesuai konfigurasi). Jika kurang satu komponen, **MO/WO belum boleh dijalankan**. Jika Central juga kekurangan, proses harus berstatus shortage/exception; jangan membuat stok minus atau mengasumsikan replenishment sukses.
8. Baru **MO/WO dijalankan** dan bahan dikonsumsi sesuai kebijakan produksi.
9. Produk jadi ditransfer **Dapur → Transit → Packing** dan diterima Packing.
10. Packing melakukan alokasi akhir dan **Internal Transfer Packing → Transit → Toko**.
11. Toko **mengonfirmasi Receipt aktual** sehingga siklus selesai dan Qty Requested/Allocated/Delivered/Received dapat ditelusuri.

**Gate implementasi:** pembuatan MO **tidak boleh secara otomatis memicu start production**; start/WO harus dicegah secara server-side jika material dapur belum ready, bukan hanya mengandalkan tombol di UI. Perlu desain dan pengujian khusus untuk status MO, operasi reservasi, picking, stock moves, warehouse receipts, Accounting/valuation, kekurangan bahan di Central, dan perubahan stok setelah material ready. **Belum diimplementasi** untuk MO, picking, gate availability, atau transfers; dokumen ini keputusan flow, bukan bukti implementasi.

**Pekerjaan berikut:** kerjakan konsolidasi RO-only terlebih dulu (preview+prorata+round-up+capacity handling), lalu generate MO dan replenishment bahan secara berurutan dengan tes pada `erp-yussyakmal-mrp-test`. Jangan loncat dari generate MO langsung ke produksi. UI/UX minor tetap HOLD.

## RO-only Packing Consolidation PREVIEW source — addon v19.0.3.0.0 (22 November 2026)

**SOURCE COMMITTED; NOT YET UPGRADED OR GUI-TESTED**: `addons/ya_store_ro/wizard/packing_preview.py`, `views/packing_preview_views.xml`. Menu manager-only **YA Production Capacity → Packing - Consolidation Preview**. Pilih SATU Published Planning (kitchen + delivery date + slot), klik Calculate Preview: sistem membaca **hanya RO Confirmed** yang terkait planning tersebut (Draft dikecualikan), menghitung Total RO/SKU, output BoM, produksi **dibulatkan KE ATAS**, surplus, Max Planning, dan status **Within Max / Exceeds Max**. Tab kedua memperlihatkan rincian toko: Requested, Surplus Prorata, Allocated, dengan metode integer largest-remainder yang deterministik. Recalculate untuk data terbaru.

Jika qty produksi > Max Planning, preview **menandai Exceeds Max** dan menghitung blocked_count; **tidak menciptakan MO** dan **tidak mengurangi permintaan**. Jika kitchen BoM tak dapat ditemukan secara unik, tampil error per SKU agar mapping dicek. Menu ini hanya READ-ONLY terhadap RO, Planning, Inventory, MO, transfer dan accounting; ia hanya menyimpan record transient preview sementara. SO tidak dilibatkan; aturan SO ditinjau kembali nanti sesudah siklus pertama RO selesai. **Material replenishment Central→Dapur + picking list Central + konfirmasi receipt dapur + material availability gate tetap WAJIB sebelum menjalankan MO.**

**PRE-FLIGHT:** `cd ~/odoofromzero && git pull && python3 script/test_ro_packing_prorata_pure_ya.py && python3 script/check_ya_store_ro_source_readonly.py`. Jika semua PASS, backup GUI DB `erp-yussyakmal-mrp-test`, copy addon dan `-u ya_store_ro`, restart, uji Preview. **Jangan jalankan MO/transfer pada tahap ini**.

## KOREKSI PENTING Packing Preview — sumber CONFIRMED RO, bukan Planning (22 November 2026)

Feri menegaskan Preview Packing **tidak boleh membuka daftar PPIC Planning (termasuk Draft)**. Titik masuk benar: **pilih Tanggal Kirim + Slot → ambil semua RO toko status CONFIRMED pada jadwal tersebut, lintas toko dan dapur → grup menurut dapur + SKU → masing-masing grup menjadi dasar tepat SATU MO** untuk dapur+SKU+tanggal+slot (setelah validasi/close/kapasitas kelak). Planning hanya direferensikan di belakang layar untuk BoM, Max Capacity, dan memastikan RO yang sudah Confirmed terhubung pada Planning Published. **Draft RO diabaikan sepenuhnya.** Jangan menggabungkan dapur yang berbeda, meskipun SKU sama.

**Kode telah dikoreksi di GitHub (addon `ya_store_ro` v19.0.3.1.0), belum diuji/upgrade di server.** Wizard `ya.packing.preview` sekarang memiliki `delivery_date` + `slot`, query `ya.store.ro` state confirmed, dan hasil tab konsolidasi/prorata memuat kode dapur. Tidak ada MO/transfer yang dibuat. Sebelum upgrade lakukan source preflight dan pure arithmetic tests; tes GUI untuk memastikan yang muncul adalah RO Confirmed lintas toko/dapur. Kalau Planning Draft muncul sebagai pilihan pada Packing Preview, itu bug.

Koreksi ini menggantikan instruksi lama yang menyuruh memilih satu Published Planning dari menu Packing.

## Tampilan tanggal RO dan Packing — YYYYMMDD (22 Nov 2026)

Keputusan Feri: tanggal yang ditampilkan tidak boleh format locale seperti `Nov 22`; gunakan **`YYYYMMDD`** (mis. `20261122`). Source addon `ya_store_ro` versi **19.0.3.2.0** telah diperbarui (**belum di-upgrade/GUI tested**): RO list/detail menampilkan **Tgl Kirim** dan **Tgl RO** format YYYYMMDD sebagai field string computed; Tgl RO diambil dari waktu pembuatan RO `create_date` dikonversi ke timezone pengguna, sedangkan Tgl Kirim dari jadwal Planning. Pada Packing Preview, input tanggal kirim berupa teks YYYYMMDD dengan validasi ketat; tab Prorata per Toko menampilkan **RO sumber, Tgl RO, Tgl Kirim**. Tanggal internal Odoo/DB tetap bertipe Date/Datetime, hanya format tampilannya yang diubah. Konsolidasi tetap hanya berasal dari RO Confirmed, tidak dari Draft Planning. Uji preflight lalu upgrade hanya di `erp-yussyakmal-mrp-test`.

## Koreksi format tanggal oleh Feri — 2026-Nov-22

Keputusan terbaru menggantikan instruksi sebelumnya `YYYYMMDD`: tanggal tampilan RO Toko dan Packing harus **`YYYY-Mon-DD`**, misalnya **`2026-Nov-22`**. Bulan singkatan Inggris tiga huruf dengan kapital awal, bukan `20261122`, bukan `Nov 22`. Addon `ya_store_ro` versi `19.0.3.3.0` memakai utilitas `models/date_labels.py` untuk format tetap tanpa bergantung locale server dan validasi input tanggal konsolidasi. Kolom Tgl RO dan Tgl Kirim, label RO serta input tanggal Packing diperbarui. **Kode sudah di GitHub tetapi belum diuji/upgrade server; pengujian lebih dulu.** Database date tetap Date/Datetime; metadata XLSX RO `Delivery Date` tetap format ISO yang sudah dipakai importer, tidak diubah.

## KEPUTUSAN FINAL — Admin Packing boleh koreksi RO Confirmed sampai Produksi OK (22 Nov 2026)

**Koreksi eksplisit Feri mengesampingkan aturan lama 'Confirmed RO immutable' tanpa pengecualian.** RO toko **Draft** dapat diedit operator toko; **Confirmed** tidak dapat diedit oleh operator toko, tetapi **Admin Packing Konsolidasi** memiliki jendela koreksi terakhir untuk **mencari RO Confirmed dan mengubah Qty Requested per SKU** apabila operator toko meminta revisi. Setiap perubahan qty wajib **berjejak audit** (siapa/kapan/alasan/sebelum/sesudah), tidak mengubah status asal RO menjadi Draft, dan memicu/menuntut **perhitungan ulang konsolidasi + prorata** dari data RO Confirmed terkini. Hanya Admin Packing yang diberi kewenangan khusus; **jangan membuka edit umum bagi seluruh user toko**.

**Batas mutlak:** koreksi hanya selama konsolidasi untuk **tanggal kirim + slot belum berstatus `Produksi OK`**. Saat Admin Packing menyelesaikan konsolidasi, sistem validasi ulang semua RO Confirmed/Qty, BoM, rounding-up, prorata, kapasitas, dan menciptakan MO **satu per dapur + SKU + tanggal kirim + slot**. **Status `Produksi OK` hanya boleh ditetapkan pada transaksi yang sama ketika seluruh MO yang diharapkan benar-benar berhasil dibuat, terhubung ke konsolidasi, dan tidak ada duplikasi.** Jika pembuatan salah satu MO gagal, rollback seluruhnya: tetap belum Produksi OK dan RO masih dapat direvisi Packing. Produksi OK berarti **MO sudah dibuat**, BUKAN MO selesai ataupun work order sudah dimulai; setelah itu Qty RO dikunci untuk revisi normal, termasuk oleh Packing. Perubahan pasca Produksi OK memerlukan workflow exception terpisah, belum ditetapkan.

**Sesudah Produksi OK:** MO memicu pemeriksaan bahan baku dapur; kekurangan memicu material replenishment Central→Dapur; Picking List Central dikelompokkan per dapur; transfer/receipt dapur dikonfirmasi; **MO/WO tidak boleh dijalankan sampai semua bahan tersedia di dapur**. Setelah produksi selesai: Dapur→Packing→Transit→Toko→Receipt toko. SO belum masuk pada siklus pertama.

**STATUS IMPLEMENTASI:** ini keputusan workflow yang **BELUM diimplementasikan** dalam modul. Kode `ya.store.ro` saat ini masih melarang semua perubahan Qty setelah Confirmed, dan `Packing Consolidation Preview` masih transient/read-only tanpa status Produksi OK ataupun MO. Jadi **jangan klaim fitur koreksi Admin Packing atau Produksi OK sudah berjalan**. Implementasi perlu role/group Admin Packing khusus, model konsolidasi permanen per tanggal-slot, audit trail dan tindakan atomik generate MO + set status. Jangan menyamakan Preview dengan Produksi OK.

## IMPLEMENTASI SOURCE Packing Correction (v19.0.4.0.0) — belum upgrade/test server

Sesuai instruksi Feri, addon `ya_store_ro` di GitHub kini memiliki role baru **YA Packing - Admin Konsolidasi** (`group_ya_packing_admin`, tidak otomatis diberikan kepada operator toko), wizard menu **Packing - Koreksi RO Confirmed**, dan audit readonly di form RO. Admin Packing memilih RO berstatus Confirmed, baris SKU, Qty baru dan **alasan wajib**. Metode `ya.store.ro.line.write` hanya mengizinkan update Qty Confirmed jika user berada di group Packing Admin dan membawa alasan; ia menyimpan **qty_before, qty_after, alasan, changed_by, changed_at** di model `ya.store.ro.qty.audit` dalam transaksi sama. RO tetap Confirmed; Qty Draft tetap mengikuti hak akses Manager lama. Akses audit dibuat hanya oleh service, pengguna hanya bisa melihatnya. Field `production_ok` baru **cadangan penguncian (default False)** dan ditolak bila ada yang mencoba mengisi manual lewat `create/write`; **belum ada metode yang mengaktifkannya** karena Generate MO belum dibuat. Revisi Confirmed ditolak jika ada RO pada tanggal+slot dengan `production_ok=True`. **Tidak ada MO/stock/transfer atau jurnal** pada implementasi ini.

**STATUS:** source committed, belum diuji di Odoo server. Pastikan group Packing Admin ditetapkan secara eksplisit ke user penguji (Settings → Users → Access Rights; jangan beri operator toko). Preflight tanpa DB: `python3 script/check_packing_correction_source_readonly_ya.py` dan `python3 script/check_ya_store_ro_source_readonly.py`; pure date dan prorata tests bila belum dilakukan. Setelah PASS + backup GUI, upgrade `-u ya_store_ro` hanya di `erp-yussyakmal-mrp-test`; uji via user Packing Admin bahwa koreksi membuat audit, tetap Confirmed, recalculation Preview menunjukkan Qty terbaru, user non-Packing ditolak, status `production_ok` tetap False. **Belum implementasi status Produksi OK setelah semua MO dibuat secara atomik, material replenishment Central→Dapur, picking dan receipt dapur, MO availability gate.** Tahap berikut: desain konsolidasi persisten dan Generate MO tanpa duplikasi serta status lock atomik.

## Generate MO standar — checkpoint safe preflight (22 Nov 2026)

**Pengguna melaporkan sudah menguji workflow Odoo standar sebelumnya dan BERHASIL. Jangan meminta pengujian alur standar dari nol lagi.** Keputusan: satu MO per **dapur + SKU + tanggal kirim + slot**, MO standar `mrp.production` (bukan custom MO), grup/pelacakan Packing per dapur+tanggal+slot. Final konsolidasi dihitung dari semua RO **Confirmed** pada tanggal-slot; Admin Packing masih boleh koreksi Qty dan Preview recalculates sampai **Produksi OK**. Status Produksi OK diset atomik setelah semua MO sukses dibuat; bukan tanda MO selesai. Selepasnya material replenishment Central→Dapur, picking list Central per dapur, receipt dapur dan availability gate sebelum WO dimulai; SO menyusul setelah satu siklus.

**Skrip baru DI-COMMIT, tidak mengubah DB:** `script/check_mo_creation_schema_readonly_ya.py`; dipanggil via Odoo shell stdin dengan database **HANYA `erp-yussyakmal-mrp-test`**, menampilkan field mrp.production, action_confirm, defaults, serta contoh mapping RO Confirmed → Planning line → BoM → Manufacturing Operation Type/location dari data riil. PENTING: ini bukan pengulangan uji standar, hanya verifikasi schema & mapping sebelum kita memasang fungsi Generate MO agar tidak menebak setting gudang atau field Odoo 19. **Belum ada kode Generate MO baru**. Tahap berikut setelah log diterima: implementasi konsolidasi permanen & pembuatan MO atomik, idempotent anti-duplikasi, link MO→batch/SKU/toko, lock RO, dan perhitungan bahan melalui Odoo standard. Jangan claim Produksi OK aktif atau MO dibuat sampai pengujian selesai.

## SOURCE milestone — Production OK + standard MO from Confirmed RO (19.0.5.0.0) (22 Nov 2026)

**Feri supplied successful read-only schema/mapping test on DB `erp-yussyakmal-mrp-test`: `MO_SCHEMA_READONLY_OK`.** Standard `mrp.production`: `product_id`, `product_qty`, `product_uom_id`, `bom_id`, `picking_type_id`, `location_src_id`, `location_dest_id`, `date_start`, `company_id` available. `action_confirm=True`. Source mapping: RO 3 ASN Asin (BoM1153 Pcs output46, BoM1624 output31, BoM1161 output300), Production Picking Type282 source/dest ASN/Stock; RO2 GRG Gorengan BoM output1, PT291 source/dest GRG/Stock; RO1 ASN additional; ALL READ ONLY PASS. These are test examples, not hardcoded into addon.

**Committed GitHub but NOT installed / not GUI tested**: `ya_store_ro` v19.0.5.0.0. Added persistent immutable `ya.packing.batch` unique by delivery_date+slot, `ya.packing.batch.line` unique by batch+Planning+SKU (1 standard MO per kitchen/SKU/date/slot), `ya.packing.batch.allocation` frozen original RO/Qty/Prorata, link `mrp.production.ya_packing_batch_line_id` unique per line. Menu `Packing - Produksi OK` shows released MO and allocation details. On `Packing Consolidation Preview`, Admin Packing has button **Produksi OK + Generate MO** with confirmation (only shown when preview not capacity blocked). Backend **re-locks date+slot, RE-CALCULATES from all current RO CONFIRMED, checks capacity and BoM/product/UoM/PT, snapshots RO + allocation, creates standard MO `mrp.production` per dapur/SKU, calls `action_confirm()` on each, links MO to batch, and validates total allocations = total production.** Database transaction rollback on any exception; batch unique + MO line unique prevent duplicates. `ya.store.ro.production_ok` now a read-only computed flag based on released batch; Confirm RO and Packing corrections use same PostgreSQL transactional date/slot advisory lock; cannot Confirm new RO or correct Qty after Produksi OK. Draft RO not included. SO deferred. **MO confirmation ≠ start/WO/production completion.**

**LIMITS IMPORTANT**: MO `date_start` currently `fields.Datetime.now()` as explicit required value (the actual production start scheduling policy per delivery slot is NOT YET implemented; do NOT claim MOs accurately scheduled for desired production window). No custom material-ready hard gate yet, nor Central picking/receipts or downstream goods transfer. Standard MO confirmation may create stock moves/procurement and must be tested in the isolated MRP DB, never main DB. Before real production, ensure availability gate and replenishment flow are properly hooked. **DO NOT click Generate MO on real production data yet.** First run pure source preflights + GUI backup of TEST DB; then upgrade TEST database, choose a tiny test day/slot with known RO+Planning+BoM and complete controlled test, verify MO count, PT per kitchen, component moves, no duplicates, status lock, audit, batch allocations. Revert test DB backup if needed; no blind production rollout.

**Preflight**: `python3 script/check_ya_store_ro_source_readonly.py`; `python3 script/check_packing_generate_mo_source_readonly_ya.py`; `python3 script/test_ro_packing_prorata_pure_ya.py`; `python3 script/test_ro_date_labels_pure_ya.py`. All source and test scripts should be checked before addon upgrade. No service update until preflights PASS.

## Warehouse routing safeguard for MO creation

Before creating ANY MO, action checks BoM production picking type warehouse name equals `Dapur ` + the associated Planning Work Center name (case/space normalized), in addition to BoM product, UoM, PT source/dest and Planning Max. Example observed from Feri's read-only test: ASN workcenter Asin → Dapur Asin / PT282 / ASN/Stock; GRG workcenter Gorengan → Dapur Gorengan / PT291 / GRG/Stock. No hardcoded PT ids. In user sample on 2026-Nov-27 S1 RO 1/3 ASN and RO2 GRG, six distinct dapur+SKU combinations were visible (3 ASN, 3 GRG); actual release count depends on ALL Confirmed RO for that date/slot and capacity. MO `date_start` is temporarily current time, NOT a committed production schedule by delivery slot. Test-only until scheduling and material readiness gate follow.

## UX Packing correction — Confirmed RO list is entry point (22 Nov 2026)

**Feri explicitly corrected the UX:** menu **Packing - Consolidation** MUST first open a **LIST of already CONFIRMED store RO**, not the wizard asking to type/select a date and slot and NOT the PPIC Planning list. Admin Packing selects the desired Confirmed RO rows from list (checkbox) then clicks **Konsolidasi SKU**; only then the modal with grouped kitchen+SKU Qty, BoM round-up, Max Capacity and prorata store allocations opens. List shows Tgl RO and Tgl Kirim as `2026-Nov-22`, Slot, Dapur, Toko, Qty, State, Produksi OK. `Draft` RO excluded by domain. Multi-selection MUST be same `Tanggal Kirim + Slot`, otherwise show explicit validation.

**Committed source `ya_store_ro` v19.0.5.1.0, not yet server-upgraded or GUI-tested:** new `views/packing_ro_selection_views.xml` defines list + action, **reuses existing `menu_ya_packing_preview` external id** to update the installed menu. Model `ya.store.ro.action_open_packing_selected` accepts list selected IDs and passes selection as wizard default `selected_ro_ids`; wizard calculates ONLY these selected confirmed RO. The modal displays selection count and source docs. For **Produksi OK + Generate MO**, the server REQUIRES all Confirmed RO of the same date and slot have been selected, because batch uniqueness/RO locks affect the entire slot. Partial selections can be PREVIEWED but cannot be released. No MO is generated merely by selecting/previewing. The user can return to list and select all matching Confirmed RO when ready. Do not silently incorporate unselected RO. SO excluded.

**QA without database:** `python3 script/check_packing_selection_source_readonly_ya.py`, `python3 script/check_ya_store_ro_source_readonly.py`, `python3 script/check_packing_generate_mo_source_readonly_ya.py`. Once source PASS, GUI backup test DB `erp-yussyakmal-mrp-test`, upgrade `-u ya_store_ro` and restart. On GUI verify list first, select RO1+RO3 (same date S1 ASN), click Konsolidasi SKU -> preview sum only selected; mixed date-slot error; selecting all RO date-slot permits Generate MO subject to capacities. **Never run MO in production/main DB.**

## NEW USER DECISION — Two-step Pre Produksi then Produksi OK (22 Nov 2026)

**Feri corrected the business flow** after Packing Consolidation: **Confirmed RO selection list → Konsolidasi SKU preview → button "Pindahkan ke Pre Produksi" → persistent list per Dapur+SKU with status "Pre Produksi" → select Pre Produksi SKU rows → click "Produksi OK" → ONLY THEN generate and confirm standard MO, change status to Produksi OK atomically.** Previous direct `Produksi OK + Generate MO` button in preview is REMOVED. No MO at staging time.

**Code committed to GitHub `ya_store_ro` v19.0.6.0.0; NOT yet tested/upgraded on server.** Wizard `action_move_to_preproduction` recomputes latest selected RO Confirmed, validates Max/BoM/routing, requires all Confirmed RO in date+slot included, creates persistent `ya.packing.batch` in `pre_production` with one `ya.packing.batch.line` per dapur/SKU, prorata store allocation and source RO snapshots, with no MO; RO `packing_batch_id` field marks it staged and removes it from selectable Confirmed RO packing queue (origin RO remains Confirmed for audit). New menu `Packing - Pre Produksi` shows selectable list per dapur+SKU with its own status (related to batch status). Admin Packing selects rows and clicks **Produksi OK** (source method `ya.packing.batch.line.action_generate_selected_mo`). Current atomic implementation **requires selecting ALL SKUs in a single date+slot**; PARTIAL SKU release is explicitly BLOCKED to prevent incomplete slot status or MO duplication. It locks slot, validates live Confirmed RO ids, SKU/Qty vs staged snapshot, BoM and kitchen routes, creates standard `mrp.production` MO one per dapur+SKU, calls action_confirm, and sets batch state `production_ok` only after all MO & allocation totals validate. Errors rollback complete transaction. Old RO amendments remain possible before Production OK, but after staging such amendments invalidate snapshot: **select a Pre Produksi line and click "Konsolidasi Ulang"** to reset entire staged date+slot (only allowed before any MO), then reselect RO to consolidate again. Reset never deletes MO. Menu `Packing - Produksi OK` now filters only approved batches, keeps view MO and final allocations. The last correct RO date display remains `YYYY-Mon-DD` (e.g., 2026-Nov-22).

**Operational warning:** The user's most recent attempted addon upgrade exited 255 due to missing `api` import in packing_preview (NameError). That missing import was fixed in GitHub but user has not yet supplied successful re-upgrade status. Therefore **do not presume this newer 19.0.6.0.0 source is live**. Before any server upgrade: `python3 script/check_ya_store_ro_source_readonly.py`, `python3 script/check_packing_selection_source_readonly_ya.py`, `python3 script/check_packing_generate_mo_source_readonly_ya.py`, `python3 script/check_packing_preproduction_source_readonly_ya.py`. GUI backup of **erp-yussyakmal-mrp-test only**, then addon deployment and controlled test. Do not click Produksi OK on operational data. MO date_start still current time, material-ready gate/replenishment Central→Dapur downstream not implemented here.

## Final clarification — RO locked irrevocably at Pre Produksi (2026-11-22)

Feri clarified: after Packing Konsolidasi moves selected RO to **Pre Produksi**, those RO MUST NOT appear in the **Packing Confirmed queue** and their Qty MUST NO LONGER be editable, even by Packing Admin. **Pre Produksi is the business cut-off for all Qty changes**, NOT Produksi OK. Existing RO master document `ya.store.ro.state` stays `confirmed` as the original source/audit state, while `packing_batch_id` and batch/line `state=pre_production` give the downstream Packing status; selection list domain is `state=confirmed AND packing_batch_id IS NULL`. In GitHub `ya_store_ro` v**19.0.6.1.0**, backend `ya.store.ro.line.write` takes date/slot lock and rejects Qty correction if any Packing batch exists for the slot, including Pre Produksi. Packing correction wizard domain excludes staged RO and submit validates it. Confirming new Draft RO into a slot already staged is also blocked. All Pre Produksi reset/un-staging buttons and methods were removed, and batch/line/allocation unlink is rejected; no normal workflow can return an RO from Pre Produksi to editable Confirmed. Only in Pre Produksi can Admin Packing choose all SKU rows for final Produksi OK; that action creates standard MOs atomically then updates status. Source committed to GitHub, **not yet installed/tested**. This decision supersedes earlier guidance suggesting Pre Produksi could be reset to change Qty. Do not claim Pre Produksi edits are possible.

## Packing ONE ENTRY workflow v19.0.7.0.0 (22 Nov 2026)

Feri clarified Packing Admin is ONE person; no menu jumping. Main nav remains **Packing - Consolidation** only; direct selectable list of Confirmed RO not yet staged. List-header **Konsolidasi SKU**, **Lanjut Pre Produksi**, **Lihat Produksi OK** navigate within the Packing workflow. On Consolidation modal, NEW **Koreksi Qty RO - Sebelum Pre Produksi** tab lists all selected Confirmed RO SKU lines (including zero Qty) per kitchen/store, **Qty Confirmed / editable Qty Koreksi / mandatory Alasan if changed**. Admin clicks **Simpan Koreksi Qty + Recalculate**. Under slot lock, current RO and source old Qty verified, changed underlying `ya.store.ro.line.qty_requested` written with existing required audit reason context, existing immutable RO Qty audit created, and same wizard recomputes total, BoM round-up/Max and prorata. Recalculate button refuses to discard uncommitted Qty changes. **Pindahkan ke Pre Produksi** similarly refuses uncommitted changes, re-calculates latest all selected Confirmed RO and validates full-slot coverage & Max. Then creates persistent batch and automatically navigates to **Pre Produksi** list per dapur-SKU; **no MO yet**. At Pre Produksi, user selects ALL SKU for ONE date+slot and clicks **Produksi OK**; creates/confirm standard MO atomically; then sees Produksi OK batch with MO details. Each list header has navigation buttons, so no side-menu bouncing. Redundant side menus `menu_ya_packing_preproduction` and `menu_ya_packing_batch` are marked inactive but corresponding actions remain reachable via list-header buttons and after staging.

**Irrevocable Qty cut-off** remains **Pindahkan ke Pre Produksi**, never at MO. `ya.store.ro.state` source remains Confirmed for audit; `packing_batch_id` makes it leave the Packing Confirmed queue. Packing corrections and late Confirm RO are blocked at batch stage. No reset and no direct MO in Preview. Pre Produksi selected ALL for slot initially, not partial release.

Committed GitHub source version `ya_store_ro 19.0.7.0.0`, NOT yet installed or GUI tested. Recent server attempt of prior v19.0.5.1.0 exited 255 due to missing `api` import; fixed subsequently, but Feri did not yet confirm a successful subsequent upgrade. Run source checks before any further test DB upgrade. New script: `python3 script/check_packing_workbench_source_readonly_ya.py`, and earlier three source checks. First GUI test must stop before Produce OK to validate Qty correction/audit, Recalculate, staging/list, lock, no MO. Back up TEST DB `erp-yussyakmal-mrp-test` prior to upgrade. Production DB `erp-yussyakmal` and integer-test remain strictly untouched. MO scheduling date_start still now (not target delivery slot), material-ready gate is pending.

## FINAL CORRECTION: Preview prorata is STORE DEMAND REDUCTION, NOT SURPLUS DISTRIBUTION (2026-11-22)

Feri clarified explicitly: **"harus nya prorate di preview sebelum produksi adalah membagi membuang hitungan kelebihan dari maximun setiap toko dikurangi secara proragte bukan malah membagi kelebihan, lebih apa yg di bagi kan belum produksi"**. This supersedes ALL older notes about distributing rounded-up BoM surplus to stores during Preview.

**Canonical logic `ya_store_ro` v19.0.8.1.0, committed but NOT yet server-deployed/tested:**
- Input one `(delivery date, slot, kitchen, SKU)`: store Original Confirmed RO quantities (immutable source once staged), Published Planning Max, BoM output B.
- Standard no-capacity-pressure path: if `ceil(RO total/B)*B <= Planning Max`, projected MO is this rounded amount, but **each store's final allocation remains EXACTLY original RO**, shortage zero; projected BoM rounding **gap is UNALLOCATED**, not allocated to any store. A new wizard summary `total_unallocated` and batch-line `qty_surplus` (legacy DB field labeled `Selisih BoM Belum Dialokasikan`) record this hypothetical gap; store `qty_surplus` ALWAYS 0.
- If rounded MO Qty would exceed Max: feasible whole BoM output `floor(Max/B)*B`; use integer Hamilton prorata to REDUCE each store's final Qty in proportion to original RO, assign shortages `original RO - final allocation`. **Each store final Qty never exceeds original RO.** Example SKU 10029: RO total180, B110, Max110 → MO110, store allocations for A/B/C originals 90/60/30 become 55/37/18, corresponding reductions 35/23/12. No hypothetical surplus distributed. If `floor(Max/B)*B=0`, remain blocked since no batch is feasible.
- Preview fields and UI label `Prorata Pengurangan Qty per Toko`, `Qty RO Asli`, `Jatah Setelah Prorata`, `Kekurangan`. Amber warning and explicit checkbox to accept shortages prior to irreversible Pre Produksi; blocked red for cannot make one batch. PRORATA IS DONE BEFORE PRODUCTION; no MO in preview/stage.
- Release invariants changed: `store.requested == store.allocated + store.shortage`, **store.surplus == 0**, `MO qty == sum(store allocated) + SKU unallocated BoM gap`. All shortages/BoM gaps immutable from Pre Produksi through MO. No silent distribution.
- Tests: `python3 script/test_capacity_prorata_ya.py` and `python3 script/check_capacity_prorata_source_readonly_ya.py` plus source preflights. Test DB `erp-yussyakmal-mrp-test` ONLY with backup; module version/ORM fields/XML changed so Odoo upgrade `-u ya_store_ro` needed. No approval for production main DB.

## NEXT PHASE — MO → Material Requirement → CDC (23 Nov 2026; readonly audit first)

User confirmed MO generation ("sudah jadi MO") after Packing Produksi OK and authorized next phase: calculate missing ingredients per kitchen from CDC, then use **standard Odoo Internal Transfer** and kitchen receipt; if CDC has insufficient free stock, surface Purchasing needs.

**First committed deliverable only:** `script/audit_mo_material_cdc_readonly_ya.py` plus static guard `script/check_mo_material_cdc_source_readonly_ya.py`. This is a NO-DB-WRITE Odoo shell report for TEST DB `erp-yussyakmal-mrp-test`, target 2026-11-27 S1. Reads link `ya.packing.batch.line.mo_id`, `mrp.production.move_raw_ids` (actual confirmed MO raw component moves), converts raw demand UoM to product base UoM, groups by kitchen WH/SKU, reads physical and reserved stock via `stock.quant` under each kitchen's `lot_stock_id`. Lists warehouse CDC/Central candidates and, only if unambiguous, free stock at CDC. Outputs per-component gross demand, physical, total reserved, free, **LOWER and UPPER SHORTFALL ESTIMATES**. These are NOT final replenishment amounts because reservations belonging to these very MOs can make naive "demand minus free stock" double-count shortages. Audits raw stock source locations and whether CDC mapping is unambiguous; no automatic transfer, stock reservation, PO, or MO changes.

**Next after Feri supplies report:** verify MO-owned reservations, replenishment in-transit, stock location hierarchy, CDC warehouse & picking type, FEFO/lots and exact UoM; then create a read-only Material Requirement UI with validated net shortages and subsequently draft standard Odoo `stock.picking` internal transfers CDC→kitchen, subject to user approval and no-negative rules. Do not assume one automatic stock transfer is valid between separate Odoo warehouses if two-step route requires different pickings. No implementation of transfers has been authorized beyond staged design; no CDC warehouse identifier confirmed.

Commands:
```bash
cd ~/odoofromzero
git pull
python3 script/check_mo_material_cdc_source_readonly_ya.py
sudo -u odoo19 /opt/odoo19/venv/bin/python3 \
 /opt/odoo19/odoo/odoo-bin shell \
 -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test --no-http \
 < script/audit_mo_material_cdc_readonly_ya.py
```
No module upgrade or service restart required for these reports. Source commit and reports are not evidence of actual inventory balances until shell output arrives.

## 23 Nov 2026 — New `ya_material_requirement` 19.0.1.0.0 (SOURCE ONLY)

After user reported `AUDIT_READ_ONLY_OK` on `erp-yussyakmal-mrp-test` 2026-11-27 S1 (20 Confirmed linked MO, 247 raw moves, 97 kitchen/product combinations from Dapur Asin and Dapur Gorengan, CDC uniquely `Gudang Central` code `CDC` at `CDC/Stock`), developed a new addon: `addons/ya_material_requirement`.

Important precision: the stdout printed only 75 of 97 groups; all 75 printed were zero in kitchen physical/reserved and CDC free, but 22 weren't shown; do not assert all 97 have zero stock without the new full view.

**Single UI menu:** `Manufacturing → YA Production Capacity → Material Requirement` (under `ya_production_planning.menu_ya_capacity_root`). Wizard date/slot and `Hitung / Refresh Kebutuhan`, two list tabs:
1. `Kebutuhan Bahan per Dapur`: consolidated from linked confirmed MO `move_raw_ids`, stock WH/Stock internal subtree, need/onhand/reserved/free and min/max shortage per base UoM.
2. `Ringkasan CDC per Bahan`: aggregates shortages from **ALL kitchens for same product BEFORE subtracting CDC free stock ONCE**, displays projected CDC purchasing gap min/max and warning badges.

**Reservation caveat:** This is a report only, not an automatic requisition: when reservations exist, `need - free` may double count those already belonging to the same MO. Display shortage interval `min=max(need-onhand,0)`, `max=max(need-(onhand-reserved),0)`, no definitive transfer until reservation ownership/incoming stock/FEFO reconciled. Rejects non-confirmed MO and ambiguous CDC/kitchen routing. Only test DB allowed in pilot runtime. Snapshot writes only ephemeral TransientModel reports, never stock/MO/picking/PO.

Source files: `models/material_requirement.py`, `models/material_rules.py`, `views/material_requirement_views.xml`, `security/ir.model.access.csv`, `README.md`, source/test scripts `script/check_material_requirement_source_readonly_ya.py`, `script/test_material_requirement_rules_ya.py`. **NOT YET installed, upgraded or user tested.** Do not claim new menu exists on server before Feri's `-i` success and GUI validation. User must use GUI backup of test DB, no production DB. Tests before install:
```bash
cd ~/odoofromzero && git pull
python3 script/check_material_requirement_source_readonly_ya.py
python3 script/test_material_requirement_rules_ya.py
```
If both PASS, install new addon to test DB using `-i ya_material_requirement`, coordinated restart of shared Odoo service, inspect menu and compare counts with earlier audit. No CDC transfers yet, no purchase generation.
