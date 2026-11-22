# CHECKPOINT TERKINI — ODOO FROM ZERO — 23 NOVEMBER 2026
**Status resmi handover; keputusan terakhir mengungguli catatan historis sebelumnya.**
**Repository:** `yussyakmal-dotcom/odoofromzero`.
**DB yang boleh diuji:** `erp-yussyakmal-mrp-test`.
**DILARANG menyentuh:** `erp-yussyakmal` (utama) atau `erp-yussyakmal-integer-test` (Purchasing test).

## 1. Titik terakhir yang sudah benar-benar terbukti
- User Feri menyatakan MO **sudah berhasil dibuat** melalui Packing **Produksi OK**. Output audit read-only menunjukkan batch `Packing 2026-Nov-27 S1`, **20 MO**, status semua `confirmed`, berasal dari **Dapur Asin** dan **Dapur Gorengan**.
- Audit read-only `script/audit_mo_material_cdc_readonly_ya.py` dengan `odoo-bin shell` di DB TEST menghasilkan `AUDIT_READ_ONLY_OK`: **247 raw moves**; **97 kombinasi dapur–bahan**; tidak ada mismatch source location yang dilaporkan; warehouse pusat **code CDC**, name **Gudang Central**, lokasi **CDC/Stock** (warehouse ID=1 pada DB test).
- Hanya **75 dari 97** kombinasi ditampilkan di output karena limit, dengan stok fisik/reservasi dapur=0 dan CDC free=0 untuk baris yang ditampilkan. **22 sisanya belum dibuktikan nol**; jangan menyatakan semua 97 nol. Hasil berupa diagnosis, bukan persetujuan transfer atau pembelian.
- `script/check_capacity_prorata_source_readonly_ya.py`, `script/test_capacity_prorata_ya.py`, dan `script/check_ya_store_ro_source_readonly.py` sebelumnya lulus untuk source `ya_store_ro` v19.0.8.1.0. User sudah berhasil membuat MO di GUI. Status versi dan install di server untuk modul lain harus dicek saat perlu; jangan menyamaratakan source PASS sebagai install PASS.
- `ERROR_COUNT: command not found` pernah terjadi karena user menyalin baris **contoh output** sebagai shell command, bukan kesalahan script Odoo.

## 2. Keputusan bisnis terakhir — scope DIKUNCI
**Workflow yang dibangun hanya:**
```
MO Confirmed
→ Material Requirement per dapur (BoM / raw move MO)
→ hitung kebutuhan netto dan stok tersedia dapur
→ permintaan bahan ke CDC
→ CDC cek stok / reservasi / FEFO
→ standard Odoo Internal Transfer CDC → dapur
→ dapur terima bahan
→ cek kesiapan material MO
```

**Bila stok CDC kurang:** tampilkan `CDC Kurang — Info Gudang` / angka kekurangan dalam alur ini saja. **Admin Gudang melakukan replenishment CDC di luar flow**, memakai **standard Odoo Purchase** yang sudah ada. Setelah stok CDC masuk, refresh kebutuhan, lanjut pemenuhan dapur. **JANGAN membuat modul Purchasing, auto-RFQ/PO, purchase request, purchasing queue, approval khusus, atau proses pengadaan paralel dalam flow ini.** Jangan melebar ke procurement.

Aturan keselamatan: tidak boleh stok minus; jangan transfer melebihi free/available CDC; hindari double-count reservasi MO; selisih UoM harus dihitung dalam UoM dasar produk sebelum diringkas; konsolidasi bahan yang sama antar dapur sebelum membandingkan total dengan stok CDC bersama (jangan mendobel stok CDC). Gunakan Odoo stock picking/internal transfer standar, cek rute warehouse, lot/FEFO, transfer pending dan penerimaan sebelum tindakan. Tidak ada penerimaan atau MO baru yang boleh otomatis dibuat saat hitung preview.

## 3. Source addon baru, BELUM TERPASANG / BELUM DIUJI GUI
- Addon: `addons/ya_material_requirement/`
- Versi: **19.0.1.1.0**
- Model transient wizard dan line: `models/material_requirement.py` + `models/material_rules.py`.
- UI: menu **Manufacturing → YA Production Capacity → Material Requirement** (berdasarkan XML source, bukan klaim menu sudah terlihat di server). Pilih Tanggal Kirim + Slot, tombol `Hitung / Refresh Kebutuhan`. Tab `Kebutuhan Bahan per Dapur` dan `Ringkasan CDC per Bahan`.
- Hanya membuat snapshot laporan **TransientModel**; saat ini **belum ada tombol permintaan/transfer barang dan tidak ada mutasi stok/PO/MO**.
- Field/status sudah diganti dari purchase-centric menjadi `cdc_shortage_count`, `cdc_short_min_qty`, `cdc_short_max_qty`, `cdc_short` = `CDC Kurang - Info Gudang`. Kode dan docs di GitHub diperbarui mengikuti scope terakhir.
- Formula laporan sementara menunjukkan rentang: min shortage `max(need - physical,0)`, max shortage `max(need - max(physical-reserved,0),0)`. **Bukan** jumlah final permintaan bahan: reservasi yang sudah menjadi milik MO sendiri harus direkonsiliasi. Data CDC hanya dipakai sekali per SKU untuk seluruh dapur.
- **Source checks 10/10 konsistensi nama field** telah dilakukan dari isi GitHub; **belum ada laporan Feri menjalankan** `script/check_material_requirement_source_readonly_ya.py` atau `script/test_material_requirement_rules_ya.py`, dan belum ada bukti `-i ya_material_requirement` sukses di DB test.

## 4. Urutan kerja selanjutnya (jangan loncat)
**A. Tarik source dan jalankan preflight sebagai user feri**:
```bash
cd ~/odoofromzero
git pull
python3 script/check_material_requirement_source_readonly_ya.py
python3 script/test_material_requirement_rules_ya.py
```
Target output `MATERIAL_REQUIREMENT_SOURCE_OK` dan `MATERIAL_REQUIREMENT_RULES_OK`.

**B. Baru setelah PASS dan backup GUI DB test yang selesai:**
- Deploy `addons/ya_material_requirement` hanya ke `/opt/odoo19/custom-addons/ya_material_requirement`.
- Cek state `ir.module.module`: **`-i` bila belum installed, `-u` bila installed**, hanya pada `erp-yussyakmal-mrp-test`. Jika exit code nonzero, periksa error sebelum restart.
- Restart service `odoo19` hanya setelah berhasil dan ketika aman; service dipakai bersama. Verifikasi registry dan UI terlebih dahulu.
- Jalankan audit GUI untuk `2026-11-27 / S1` dan cocokkan minimal `20 MO / 247 raw moves / 97 dapur-bahan`. Buka seluruh 97 rows, cek CDC dan perhitungan per jenis UoM.
- Belum mengeluarkan picking/transfer/PO dari modul ini.

**C. Sesudah GUI lolos**: rancang dan implementasikan **permintaan bahan CDC** dengan perhitungan saldo/reservasi/transfers incoming yang benar; kemudian draft **standard Odoo Internal Transfer CDC→dapur**, admin CDC validasi ketersediaan & FEFO dan dapur menerima. Bila CDC kurang, **informasi saja**, tidak membangun alur Purchase.

## 5. Praktik perubahan, batas, referensi
- Workflow resmi kode: **GitHub-first** → `git pull` → source checks → backup GUI DB test → copy addon → `-i`/`-u` → restart Odoo aman → uji GUI/ORM.
- Jangan membocorkan password, data customer, vendor atau rahasia di GitHub.
- Perubahan code dalam test source bukan berarti aplikasi sudah terdeploy.
- Catatan lebih lama dalam `doc/HANDOVER_ODOO_FROM_ZERO.md`, `doc/STATUS_PENGEMBANGAN_MRP.md`, dan `doc/SKILL_ODOO19_ADDON_WORKFLOW.md` adalah rekaman historis dan mungkin menyebut fase RO/Packing sebagai future. **Dokumen checkpoint ini yang berlaku untuk starting point terbaru.**
- Rujuk `addons/ya_material_requirement/README.md` untuk instalasi addon dan `doc/SKILL_ODOO19_ADDON_WORKFLOW.md` untuk cara deployment.

**Resume prompt**: "Baca `doc/CHECKPOINT_2026-11-23_MO_MATERIAL_CDC.md`. Mulai dari modul `ya_material_requirement` 19.0.1.1.0 source-only; Feri sudah punya 20 confirmed MO untuk 2026-11-27 S1, read-only audit 247 moves/97 bahan-dapur dan CDC Gudang Central teridentifikasi. Jangan bangun Purchasing; replenishment stok CDC dikerjakan Admin Gudang via Purchase standar di luar alur. Langkah berikutnya preflight script, install GUI test, validasi angka, lalu CDC→dapur internal transfer." 

## 6. Developer-only test stock seeding — NOT part of business replenishment flow

**Feri requested** a one-off inventory adjustment for an otherwise empty transaction **DEVELOPMENT test database** so subsequent CDC→kitchen internal transfers can be tested. Request: make CDC stock **10× shortages per raw material** from MO. This is **NOT a standard replenishment workflow** and does not affect the scope freeze (Warehouse Admin handles actual CDC replenishment via existing standard Odoo Purchase outside this flow).

Source added **only** as `script/dev_seed_cdc_material_10x_ya.py` and static guard `script/check_dev_seed_cdc_material_10x_source_readonly_ya.py`. NOT EXECUTED, NOT COMMITTED TO DATABASE. Strict DB whitelist `erp-yussyakmal-mrp-test`, batch `2026-11-27 S1`, CDC warehouse code `CDC`. Uses linked Confirmed MO `move_raw_ids` per kitchen/product base UoM, subtracts free physical stock per kitchen and aggregates across kitchens by ingredient. Computes **outstanding = max(sum(kitchen shortfall) - CDC stock,0)**, CDC target = **max(current CDC stock, 10×outstanding)**, inventory adjustment quantity difference = target - current; no adjustment when no shortage. It does not multiply already stocked quantities on repeated runs. Refuses if products require lots/serial, non-storable products, CDC/kitchen reservations, negative stock, ambiguous CDC child stock, changed MO status, wrong DB. Uses Odoo standard `stock.quant` inventory count + `action_apply_inventory`, with post-validation and commit only on explicit `YA_DEV_CDC_STOCK_APPLY=YES_I_CONFIRM_TEST_DB`. Default preview rolls back.

**Never run APPLY without backup GUI of test DB and human inspection of all printed target values**. This does create stock valuation/inventory adjustment stock moves in test DB, unlike readonly Material Requirement audit; it is exclusively test fixture data. First run:
```bash
cd ~/odoofromzero
git pull
python3 script/check_dev_seed_cdc_material_10x_source_readonly_ya.py
sudo -u odoo19 /opt/odoo19/venv/bin/python3 \
 /opt/odoo19/odoo/odoo-bin shell -c /etc/odoo19.conf \
 -d erp-yussyakmal-mrp-test --no-http \
 < script/dev_seed_cdc_material_10x_ya.py
```
Only after preview approved and GUI backup:
```bash
cd ~/odoofromzero
sudo -u odoo19 env YA_DEV_CDC_STOCK_APPLY=YES_I_CONFIRM_TEST_DB \
 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell \
 -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test --no-http \
 < script/dev_seed_cdc_material_10x_ya.py
```
Expected `APPLY_COMMITTED_TEST_DB_ONLY`, else stop and inspect error. No module install, no service restart; Python script only. Last known state is source-only and unverified on actual Odoo inventory flow. In development this populates **CDC**, not kitchen, so internal transfer CDC→kitchen remains testable.

## 7. Verifikasi stok dummy CDC dari Feri — 23 Nov 2026

Setelah script dev-only `dev_seed_cdc_material_10x_ya.py` dijalankan terpisah dalam APPLY (user tidak mengirim log APPLY), Feri memberikan **output verifikasi DRY RUN** pada `erp-yussyakmal-mrp-test` untuk batch `2026-11-27 S1`:
```text
MODE: DRY_RUN_READ_ONLY
CONFIRMED_MOS: 20
KITCHENS: Dapur Asin, Dapur Gorengan
MO_KITCHEN_COMPONENT_GROUPS: 97
PRODUCTS_TO_ADJUST: 0
PREVIEW_ONLY_OK: No stock changes.
```
Interpretasi yang dibuktikan: perhitungan saat audit ulang tidak membutuhkan tambahan stok CDC berdasarkan target multiplier 10× di script. Ini kuat mengindikasikan seeding stok CDC sudah terlaksana, namun **tidak menggantikan** audit Inventory Odoo maupun bukti log `APPLY_COMMITTED_TEST_DB_ONLY`, dan tidak menunjukkan semua stok efektif/lot/FEFO bebas dipindah. Jangan apply ulang. Tahap berikutnya: preflight + instalasi/uji GUI `ya_material_requirement` versi `19.0.1.1.0` di DB test saja; lalu lanjut desain permintaan Internal Transfer CDC→dapur dengan kontrol stok tersedia. Replenishment CDC, Premik dan WIP tetap dilakukan di luar flow melalui Odoo standar.

## 8. KOREKSI URUTAN: Picking List CETAK CDC sebelum Internal Transfer (23 Nov 2026)

Feri menegaskan ada **tahap wajib antara kebutuhan bahan/permintaan CDC dan transfer stok**: CDC membuat **Picking List** untuk petugas lapangan yang mengambil barang dari rak/stok CDC; list harus **bisa dicetak**. Picking List adalah dokumen kerja fisik, **BUKAN** bukti perpindahan stok, dan saat dicetak tidak boleh otomatis menambah/mengurangi stok.

**Urutan final operasional:**
```
MO Confirmed
→ Material Requirement per dapur
→ Permintaan Bahan ke CDC
→ CDC memeriksa kebutuhan dan stok tersedia bersama
→ Buat Picking List CDC per dapur (tanggal kirim + slot)
→ CETAK Picking List, petugas gudang mengambil dan mengecek fisik
→ Admin CDC mengonfirmasi Qty yang benar-benar disiapkan
→ Standard Odoo Internal Transfer CDC → dapur
→ Dapur menerima bahan; stok bertambah hanya saat validasi pemindahan/penerimaan menurut route
→ cek kesiapan MO
```
**Format cetak picking list yang direncanakan:** nomor dokumen, tanggal/slot, dapur tujuan, petugas, waktu cetak, baris berurut lokasi rak/bin CDC (jika terdata), kode SKU, nama bahan, UoM, Qty diminta, Qty disiapkan (kolom kosong untuk tulisan tangan), lot/expired FEFO bila tersedia, kolom centang/tanda tangan petugas dan pemeriksa. Satu SKU bahan per dapur dikonsolidasikan dari banyak MO; stok CDC diperhitungkan satu kali melintasi semua dapur, tidak dibuat Qty minus. Jika tidak cukup, tandai kekurangan dan lanjutkan terpisah oleh Admin Gudang menggunakan Purchase standar Odoo tanpa membuat workflow pengadaan di modul YA. Picking list harus berasal dari snapshot permintaan yang ditandai tanggal/slot dan referensi MO; jangan membuat dua kali untuk permintaan yang sama; perubahan sebelum konfirmasi harus audit/revisi.

**PENTING:** `stock.picking` adalah dokumen operasional native Odoo dan dapat memiliki status/reservasi sendiri; kebutuhan cetak **"Picking List"** tidak berarti kita boleh langsung membuat/memvalidasi `stock.picking` yang memindah stok. Pilih secara eksplisit tahap cetak/penyiapan, lalu validasi transfer/penerimaan setelah cek fisik. Pada implementasi pastikan routing antarwarehouse dan FEFO; jangan membuat stock move selesai hanya dengan print.

**Implementasi:** aturan flow dan rancangan format ini sudah dikunci di dokumentasi; modul `ya_material_requirement` versi `19.0.1.1.0` yang ada sekarang masih *read-only* dan **belum memiliki** tombol generate/cetak Picking List atau transfer. Jangan klaim fitur print sudah tersedia. Tahap berikutnya implementasi picking list dan QWeb PDF print, diuji hanya pada `erp-yussyakmal-mrp-test` setelah source review/backup.

## 9. Implementasi CETAK CDC Picking List — SOURCE-ONLY 19.0.2.0.0

Feri meminta implementasi setelah rancangan tahap wajib picking list dicetak untuk petugas sebelum internal transfer. Addon `addons/ya_material_requirement` versi **19.0.2.0.0** sekarang mempunyai tombol `Cetak Picking List CDC (Draft)` di wizard Material Requirement setelah `Hitung / Refresh Kebutuhan`. QWeb PDF `report/cdc_picking_list_report.xml` memberi halaman terpisah per dapur, tanggal kirim/slot, referensi sementara `CDC-DRAFT-<date>-<slot>-<warehouse code>`, SKU, nama bahan, unit, estimasi Qty ambil, kolom Qty disiapkan, lot/FEFO, cek fisik, tanda tangan.

**Batas fase ini:** dokumen DRAFT hasil transient (belum permintaan disimpan bernomor permanen); TIDAK membuat/menyetujui stock picking, stock move, reservation, transfer, atau pembelian. Tiap cetak menghitung ulang stok dan MO, menolak bila CDC tidak mencukupi kebutuhan gabungan atau Qty ambigu akibat reservasi dapur. Hanya test DB exact `erp-yussyakmal-mrp-test`, tidak pernah produksikan. Setelah PDF dan angka diuji, baru buat tahap persistent request, konfirmasi Qty fisik, dan Internal Transfer standar. Pembelian/premik/WIP tetap di luar flow ini.

Status: **GitHub source committed; BELUM ada bukti preflight Feri, install atau GUI/QWeb PDF print berhasil.** Jangan klaim cetak berhasil sebelum output PDF user.

Next actions Feri:
```bash
cd ~/odoofromzero
git pull
python3 script/check_material_requirement_source_readonly_ya.py
python3 script/test_material_requirement_rules_ya.py
```
Lalu backup GUI test, deploy `ya_material_requirement`. Pakai `-i` jika module belum installed, `-u` jika sudah installed; restart service hanya setelah exit=0 dan saat aman. Pilih 2026-11-27 S1, Hitung / Refresh, Cetak Picking List. Periksa halaman per dapur dan jumlah bahan. Jangan klik transfer.

## 10. ATURAN WAJIB FORMAT TANGGAL SEMUA UI / CETAK (2026-Nov-23)

**User Feri menegaskan:** setiap informasi tanggal yang ditampilkan ke pengguna di seluruh workflow YA harus mengandung **tahun 4 digit**, **bulan singkatan bahasa Inggris 3 huruf**, dan **tanggal 2 digit**: **`YYYY-Mon-DD`**. Contoh `2026-Nov-22`, `2026-Nov-23`, `2026-Nov-27`. Jangan gunakan `22-Nov`, `Nov-22`, `27/11`, atau format tanggal tanpa tahun pada label, judul, export, nama dokumen, maupun laporan cetak. Termasuk Planning, RO, Packing, MO, Material Requirement, dan CDC Picking List. Jika data disimpan dalam Odoo `fields.Date`, tetap simpan dalam standar ISO internal; format khusus hanya untuk label/display/report. Setiap UI baru atau revisi yang menyangkut tanggal wajib dicek konsistensinya sebelum di-commit. Format tanggal harus eksplisit menggunakan `%Y-%b-%d` (atau helper proyek `format_ymondd`) agar tidak bergantung pada locale pengguna.

## 11. ATURAN UI WAJIB MENU → LIST → FORM → TRIGGER (23 Nov 2026)

Feri menegaskan behavior UX seluruh modul Odoo YA: **klik menu TIDAK langsung mengeksekusi method, TIDAK langsung membuka form**, melainkan **membuka LIST dulu**. User memilih record atau `New` → masuk FORM record → baru ada **tombol/trigger tindakan** pada FORM (mis. `Hitung / Refresh Kebutuhan`, `Cetak Picking List`, konfirmasi qty, transfer). Hindari magic action di `menuitem`, header list, atau otomatis submit ketika dibuka kecuali diminta khusus dan diputuskan eksplisit.

**Sudah diimplementasikan dalam SOURCE `ya_material_requirement` 19.0.2.1.0:** menu action `view_mode=list,form` dengan `ir.actions.act_window.view` sequence list=1/form=2; list `view_ya_material_requirement_wizard_list`, menampilkan date label `YYYY-Mon-DD`, slot, state, count. Di Form baru tombol calculate dan cetak. Kode belum diuji oleh Feri pada GUI; butuh `git pull`, preflight, backup GUI test, deploy, `-u ya_material_requirement` jika addon sudah installed (atau `-i` jika belum), restart aman, lalu periksa klik menu buka list sebelum form. Transient wizard list tidak menyimpan riwayat permanen dan dapat dihapus sistem otomatis; kelak buat record persistent ketika permintaan bahan dikembangkan.

**Rule date tetap berlaku:** semua label, laporan PDF, referensi tanggal `YYYY-Mon-DD` (mis. `2026-Nov-27`), bukan ISO UI atau tanpa tahun. Form `fields.Date` input native dapat mengikuti locale pengguna, tetapi output/label yang kita buat sendiri wajib standardized; jangan klaim date-picker native bisa dikendalikan oleh format label.
