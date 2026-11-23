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

## 12. UI CORRECTION REQUIRED BY FERI — Existing Packing Batch, no New (23 Nov 2026)

After upgrade `19.0.2.1.0` user reported **"Hitung / Refresh Kebutuhan" button not visible**, rejected workflow `Menu → new empty wizard List → New → select date/slot`. Root cause: button originally in `<footer>` of a normal form and menu exposed temporary wizard list. Feri clarified: existing batch list must be reused, selected, then calculate/refresh in that same batch form. Do NOT ask user to create a new requirement record or choose date/slot again.

Source updated to **`ya_material_requirement 19.0.3.0.0`**:
- Visible menu `Material Requirement` opens existing `ya.packing.batch` **List filtered `state='production_ok'`**, not transient wizard, no `New`; shows existing `Packing 2026-Nov-27 S1` etc.
- On clicking existing batch, custom **Form** has **header** buttons `Hitung / Refresh Kebutuhan`, `Cetak Picking List CDC (Draft)`; date, slot and MO count already from Packing.
- Click Refresh calculates using existing MO → kitchen → CDC engine, and stores reporting-only snapshots `ya.material.requirement.snapshot.line` attached to existing batch. Two forms tabs: per-kitchen materials and CDC consolidation; no user-created audit wizard. Existing transient engine is internal only. No `ya.packing.batch.write`, no stock quant/picking/transfer/MO/PO changes.
- User's requested date `YYYY-Mon-DD` is shown in list/form and printed PDF.
- Source changed: `models/material_requirement_batch.py`, `views/material_requirement_batch_views.xml`, `models/__init__.py`, `__manifest__.py`, `security/ir.model.access.csv`, `script/check_material_requirement_source_readonly_ya.py`, README.
- Last user evidence: `UPGRADE_EXIT_CODE=0` from **previous** v19.0.2.1.0, but no button in GUI; does NOT count as upgrade/testing of v19.0.3.0.0. GitHub source committed, **not yet deployed or GUI tested**.

Next step: Feri `git pull`, run preflight, backup GUI, copy addon to `/opt/odoo19/custom-addons/ya_material_requirement/`, `-u ya_material_requirement` on exact **test DB** `erp-yussyakmal-mrp-test`, restart Odoo service when safe, test list/form/header button. No purchasing/replenishment scope expansion. Be receptive to traceback and fix source if issues.

## 13. Feri deploy/upgrade ulang v19.0.3.0.0 — 2026-Nov-23

Feri menjalankan `sudo cp -a addons/ya_material_requirement/. /opt/odoo19/custom-addons/ya_material_requirement/`, `chown`, lalu `odoo-bin -d erp-yussyakmal-mrp-test -u ya_material_requirement --stop-after-init --no-http`. Output **`UPGRADE_EXIT_CODE=0`**. Output juga mengandung `<string>:35: (ERROR/3) Unexpected indentation`, beberapa warning inline literal/reST, `<string>:82` (ERROR/3), dll, kemungkinan parsing dokumentasi reStructuredText Odoo (belum teridentifikasi konklusif, tidak boleh sebut fatal). Tidak ada traceback gagal install dalam log yang dikirim. Belum ada bukti restart service atau GUI form setelah upgrade ini. Next: restart `odoo19` ketika aman, Ctrl+Shift+R, klik Manufacturing → YA Production Capacity → Material Requirement, harus membuka LIST existing `ya.packing.batch` Produksi OK. Klik `Packing 2026-Nov-27 S1`, form header harus tampil tombol `Hitung / Refresh Kebutuhan`; verifikasi 20 MO/97 kelompok. Jika masalah, periksa module `installed_version`, action res_model dan views di Odoo shell test DB read-only sebelum patch. Jangan anggap warnings sebagai kegagalan Odoo jika exit 0.

## 14. GUI/PRINT VALIDATED BY FERI — CDC Picking List PDF (2026-Nov-23)

Feri confirmed in chat: **"pdf sudah muncul untuk picking list good"** after deploying/upgrading the batch-first Material Requirement `19.0.3.0.0` source. Earlier GUI screenshot showed menu opening an **existing Produksi OK Packing batch LIST** and row `Packing 2026-Nov-27 S1`, 20 MOs, 2 kitchens, date label `2026-Nov-27`. Following guidance to open the batch form by clicking its name instead of selecting its checkbox, the user reported the **Picking List PDF appeared**. Thus at least one successful PDF report rendering on test Odoo has been user-confirmed.

**Limits of evidence:** Actual PDF page content, material rows/counts, layout, printed FEFO/lot info, and exact calculated quantities have **not been independently reviewed**. Do not claim picking was physically performed, confirmed, reserved or transferred; no evidence of stock movement. Latest source preflight not directly pasted by user; successful deployment/GUI action is user evidence, not independent audit.

Next functional scope: field-staff **prepared quantities** confirmation and subsequent **standard Odoo Internal Transfer CDC → dapur**; preserve Menu→List→Form→buttons, `YYYY-Mon-DD`, free CDC/shared stock and FEFO, no custom purchasing workflow. Do not automatically transfer stock from PDF printing.

## 15. Feri setuju Physical Picking Qty > MO via Special Transfer same kitchen — source 19.0.4.1.0 (2026-Nov-23)

Feri confirms Picking List CDC is already printed, goods physically gathered, and next step is to **confirm actual picked Qty before Internal Transfer**. **Picked quantity may exceed MO demand** if additional stock is part of a **Special Transfer CDC to the exact same kitchen destination**; this is explicitly allowed. Split recorded Qty: `MO requirement` unchanged, `physical picked actual`, and `Special extra = max(actual - MO requirement,0)`; Special must have checkbox and reason (and optional `special_reference` to an existing request/transfer). For a Special-only SKU, operator can add a line with MO Qty=0; additional stock belongs to that kitchen, not another destination. Underpicked items are allowed but shortfall remains pending.

GitHub source discovered already contains initial `19.0.4.0.0` implementation of `ya.cdc.pick.confirmation` (persistent draft→confirmed per existing batch+kitchen), parent Form button `Konfirmasi Qty Picking CDC` → child LIST → selected destination Form → `Konfirmasi Qty Picking` header. The code keeps original MO Qty read-only, validates nonnegative/UoM/unique product/checkbox+reason on excess, aggregates shared CDC free stock across confirmed sheets in batch and uses CDC row lock, with test DB guard; confirmed doc locks against edits. No stock.picking, stock.move, reservation, PO or MO mutation from confirmation. GitHub now updated to **`19.0.4.1.0`** including optional Special reference field, corrected manifest label, extended safety script, updated README and views.

**NOT installed/tested at server for new release**. Last verified user action is successful PDF output from v19.0.3.0.0. Next: Feri preflight `python3 script/check_material_requirement_source_readonly_ya.py`, test DB GUI backup, `git pull`, copy updated addon, `-u ya_material_requirement` exact `erp-yussyakmal-mrp-test`, then restart if safe and test per-dapur LIST→FORM confirmation. Avoid direct stock changes before user confirms. User's agreed Special Transfer allowance does NOT authorize double execution of an existing separate Special Transfer: during later native transfer, detect/link existing transfer and only move Qty once; recheck shared CDC stock, lot/FEFO, actual warehouse route, reservations.

Format dates always `YYYY-Mon-DD`. UI Menu→List→existing Packing Form→button→child List→child Form→button.

## 16. Source v19.0.5.0.0 — Confirmed CDC Picking → Native Odoo Internal Transfer DRAFT (2026-Nov-23)

Feri asked why confirmed physical picking was not in standard Odoo Internal Transfer list; prior v19.0.4.1.0 has NO stock.picking creation by design. He agreed `okey lanjut` for the explicit integration: **confirmed kitchen picking form → button `Buat Internal Transfer (Draft)` → creates `stock.picking` with `stock.move` lines in Odoo native Inventory only, opens native form; no auto-reservation/validation.**

Implementation GitHub:
- `addons/ya_material_requirement/models/cdc_pick_confirmation.py` adds `internal_transfer_id` native stock.picking link, action `action_create_internal_transfer` plus `action_open_internal_transfer`. Must be confirmed, warehouse same-company, CDC code=CDC with internal source location, kitchen internal destination, `cdc.int_type_id.code='internal'`, correct warehouse/company, and Stock Manager + existing YA role. Only DB `erp-yussyakmal-mrp-test`.
- Action creates **one stock.picking per confirmed kitchen document** (single destination), with actual `picked_qty` per SKU once (not plus Special again); notes separate MO portion and approved Special amount and reference. Zero qty skipped; original MO demand unchanged. Origin unique deterministic `YA-CDC-PICK-<doc id> / Packing YYYY-Mon-DD SLOT`.
- Row-level PostgreSQL lock on confirmation, check linked `internal_transfer_id` and existing stock.picking origin, and related explicit Special reference against non-cancelled native picking `name` or `origin`; block if existing to avoid double execution. Existing same-doc link opens existing transfer.
- CDC free stock vs outstanding physical confirmed documents checked conservatively; does not reserve. WARNING external transfers may require reconciliation; FEFO/lot and transit routes not auto-selected; pending confirmation stock checks can overcount assigned drafts and block conservatively, not overship.
- No `stock.picking.action_confirm`, `action_assign`, `button_validate`, `stock.quant` mutation, MO/WO/PO creation. Only stock.picking/stock.move created in DRAFT, do not call Done. Transfers should appear in standard Inventory internal transfers list depending filters. After actual delivery, warehouse route/transit and kitchen receipt still to be tested separately.
- `views/cdc_pick_confirmation_views.xml`: header buttons visible based on `state` and link; list displays linked native transfer, form displays link.
- `__manifest__.py` bumped 19.0.5.0.0; `script/check_material_requirement_source_readonly_ya.py` updated with source guard checks, README documentation.
- Odoo 19 stock.warehouse `int_type_id` and stock.move `product_uom_qty`, `product_uom`, `location_id`/`location_dest_id` fields confirmed against official open-source 19.0 implementation, but **actual server Odoo registry/install/GUI testing NOT YET DONE**. No source code from user-server accessed.
- User next: `git pull`, source preflight, backup DB TEST, deploy addon to active custom-addons, `-u ya_material_requirement` test DB, restart only if safe, in browser open CONFIRMED dapur → `Buat Internal Transfer (Draft)`, verify stock.picking draft, Qty physical including Special, duplicate-click not duplicated. Do not confirm/reserve/validate transfer yet.

Business invariant: menu→list→form→buttons; display dates `YYYY-Mon-DD`. No changes to purchasing/premik/WIP or main DB.

## 17. FIX atas RPC_ERROR Odoo 19 di Buat Internal Transfer Draft — PATCH 19.0.5.0.1 (2026-Nov-23)

Feri mencoba tombol `Buat Internal Transfer (Draft)` di model `ya.cdc.pick.confirmation` dan memberi traceback riil dari Odoo 19 pada `2026-Nov-23`: `ValueError: Invalid field 'name' in 'stock.move'`, terjadi di `Move.create([...])` `addons/ya_material_requirement/models/cdc_pick_confirmation.py`. Ini **bug kode native stock.move field**, BUKAN warning docutils sebelumnya. Terjadi karena versi 19.0.5.0.0 mengirim `'name': line.product_id.display_name` sedangkan registry stock.move Odoo 19 di server tidak memiliki field `name`.

GitHub hotfix **`19.0.5.0.1`**: hapus key `name` dari stock.move create payload, tetap pakai `product_id`, notes transfer tetap menyimpan rincian Qty MO vs Special. Sebelum `Picking.create`, cek semua move keys terhadap `Move._fields` dan raise UserError yang dapat dibaca bila schema masih berbeda. Ubah preflight `script/check_material_requirement_source_readonly_ya.py` agar AST menolak key `name` pada `move_values.append({...})` dan mewajibkan runtime guard. README diperbarui. Tidak mengubah alur bisnis/RO/MO atau stok. User harus `git pull`, cek source, backup DB test, deploy, `-u ya_material_requirement` pada DB **erp-yussyakmal-mrp-test saja**, restart aman, lalu retry dari **dokumen konfirmasi yang sudah Confirmed**; **JANGAN membuat konfirmasi ulang atau MO ulang**. RPC exception biasanya me-rollback seluruh create attempt, tetapi cek field `internal_transfer_id` / Odoo standard Transfers sebelum retry, jangan mengasumsikan otomatis tidak ada duplicate sukses dari klik lain. Draft saja—jangan validate/reserve sebelum FEFO/route dan stok diperiksa.

Status: patch GitHub SOURCE committed; deployment Odoo/test GUI belum dibuktikan, masih menunggu hasil user.

## 18. 100-SKU Internal Transfer: Prefill Demand = Qty from Picked Actual (2026-Nov-23)

Feri requested bulk operator efficiency: when creating draft standard Internal Transfer after physical picking, initially populate **Demand AND Qty with the same confirmed picked actual**; then staff edits only discrepant SKUs instead of filling perhaps 100 Qty columns manually. The extra Special Transfer part is already included in picked actual; must never double-add. This is applied to **NEW** transfers, not retroactive existing drafts.

Verified from official Odoo 19 `stock.move.py`: `product_uom_qty`=Demand; `quantity` computed/inverse of `stock.move.line.quantity`, writing it can create move lines and reserve stock in `stock.quant`. Thus unlike simply pre-filling display, this is a *stock reservation side effect* (not physical transfer/validation); requires strict safeguards.

Source changed in GitHub **`ya_material_requirement` v19.0.5.1.0**, not yet installed/GUI tested:
- after `stock.move` creation, link rows by SKU ID, `move.write({'quantity': picked_qty})` only for **untracked** products with adequate **strict free quants directly in CDC/Stock** at unowned/unpackaged/unlotted quant. Validate Qty equals Demand and move still Draft; errors roll back.
- tracked LOT/SERIAL, stock located in child bins, other ownership/package or insufficient strict bin free **stay Demand-only**; Native Odoo warehouse operator must supply correct lot, FEFO, bin and Qty. Never fabricate a lot/serial, never auto-pick a wrong source bin.
- Odoo native reservation during Draft may occur. Changes to `stock.quant.reserved_quantity` are **not validation/Done**, but reflect operational claims. No automatic `action_confirm`, `action_assign`, `button_validate`, MO/PO changes.
- fix CDC shared-stock double-count: `_outstanding_unreserved_qty` helper discounts quantities already represented/reserved by other linked native transfers, because free quant already excludes them; confirmed-not-linked claims still counted. Works at both confirm-qty and draft-creation stages.
- New Draft from confirmed document retains idempotency (one linked picking per document), source CDC, dest same kitchen, one move Qty actual per SKU incl. Special once.
- User action: backup TEST DB, `git pull`, `python3 script/check_material_requirement_source_readonly_ya.py`, `python3 script/test_material_requirement_rules_ya.py`, deploy active addon, `-u ya_material_requirement` on TEST `erp-yussyakmal-mrp-test`, service restart only if safe. Test on **new confirmed picking with no existing linked transfer**, verify Demand/Qty on the same native Form, qty reservation, no unwanted Done, check lot/FEFO and special difference manually. Never retroactively create a duplicate for already-linked Draft. User evidence of this feature: NONE YET.

## 19. FEFO / LOT BELUM DIAKTIFKAN — KOREKSI KEPUTUSAN (2026-Nov-23)

Feri menegaskan: **"sejak kapan FEFO diaktifkan? saya tidak mengaktifkan lot saat penerimaan"**. Assistant sebelumnya terlalu sering menyebut FEFO/lot sebagai syarat seolah sudah aktif. **KOREKSI: BELUM ADA BUKTI lot/serial tracking diaktifkan saat receipt maupun removal strategy FEFO pada warehouse/location/product. JANGAN berasumsi sudah aktif; JANGAN paksa operator mengisi lot saat konfirmasi/pemindahan barang tanpa konfigurasi yang benar dan persetujuan Feri.** Mengusulkan FEFO sebagai target/ide bukan bukti konfigurasi aktual.

Source v19.0.5.1.0 **tidak mengaktifkan FEFO atau lot**. Di `cdc_pick_confirmation.action_create_internal_transfer`, hanya ada pemeriksaan `product.tracking != 'none'`: untuk barang yang master-nya memang tidak memakai tracking, prefill Qty=Demand jika stok tersedia di `CDC/Stock` persis; `lot_id=False` pada quants bermakna mencari stok tanpa lot, **bukan mengharuskan lot**. Jika item ternyata tracked atau stock ada di sublokasi, fungsi berhenti prefill Qty dan meminta pemeriksaan manual. Jangan ubah product tracking atau automatic FEFO sebagai side effect pengembangan Internal Transfer.

Langkah berikut bila butuh kepastian: audit **READ ONLY** pada `erp-yussyakmal-mrp-test` untuk `product.product.tracking`, `stock.location.removal_strategy_id` / product category settings terkait, dan konfigurasi lot pada operation type CDC. Jika mayoritas `tracking='none'`, bukan alasan lot/FEFO untuk mencegah pengisian Qty; lihat stok free pada lokasi sumber dan reservasi. Harus membedakan policy FEFO yang pernah tertulis dalam rencana vs fitur aktif dalam Odoo.

## 20. Hotfix 19.0.5.1.1 — Garam Dolphin Draft Demand=Qty error (2026-Nov-23)

Feri encountered **Invalid Operation: Odoo did not preserve Draft Demand=Qty for [10278] Garam Dolphin 12x1Kg. Transaction rolled back; check stock configuration** while clicking create native Internal Transfer. This is user-provided evidence, NOT caused by FEFO/lot. Actual root: v19.0.5.1.0 post-write check insisted `move.state == 'draft'` after `move.write({'quantity': qty})`. Verified exact source from official public `odoo/odoo` branch 19.0: `stock.move._recompute_state` makes `move.state = 'assigned'` when `quantity >= product_uom_qty`; `stock.picking._compute_state` may then show **Ready**. This is native reservation, NOT validated/Done/physical stock movement.

Source patch 19.0.5.1.1:
- Removes erroneous move.state Draft-only condition. Keeps native Demand=Qty prefill for untracked available materials, exact CDC source check, no forced FEFO.
- After write, invalidates cached move Quantity/State; requires actual Qty matches confirmed Qty, raises explicit diagnostic including real Qty/state if mismatch. Rejects any `move.state` or `picking.state` Done/Cancelled.
- UI `Buat Internal Transfer Odoo` (removed Draft-only promise), explanatory text warns reservation can yield Ready without Validate.
- Static preflight guard added to prevent reintroducing `move.state != 'draft'`.
- No auto Odoo stock validation. Native status may be Ready or Draft depending allocation; staff still must review and validate manually.

**Deployment status**: patch committed on GitHub only; NOT upgraded/tested on Feri's server. User action: backup test DB, `git pull`, `python3 script/check_material_requirement_source_readonly_ya.py` and `python3 script/test_material_requirement_rules_ya.py`, copy addon to active custom-addons, `-u ya_material_requirement` **erp-yussyakmal-mrp-test**, safe service restart, Ctrl+Shift+R, retry from same already CONFIRMED kitchen picking. RPC failed as Odoo UserError normally causes rollback, so no stock.picking should have been saved by that attempt, but inspect existing linked picking and native inventory to avoid double. Do not Validate. Check Garam Dolphin Demand vs Qty, status and CDC stock. Date format YYYY-Mon-DD.

## 21. Operator question: Does Validate actually transfer? What if Qty differs from Demand? (2026-Nov-23)

Feri confirms draft-created standard Odoo Internal Transfer now has prefilled quantities. Asked: **"sudah terisi, ini kalau validate di tekan otomatis stock pindah ya ?, kalau qty tidak sesuai gimana"**. Answer: native stock.picking Validate, once successfully Done, moves **actual Qty** from source CDC/Stock to destination kitchen Stock in currently designed direct internal route; if a Transit route is explicitly selected, movement applies to its actual immediate destination and may require a separate receipt leg. No stock move solely from creation or state Ready/Assigned; those reflect reservation.

**Important verified Odoo 19 native behavior (official `odoo/odoo` branch 19.0 `addons/stock/models/stock_picking.py`):** `button_validate` confirms draft pickings and for **draft move lines with `quantity==0` and demand nonzero, can assign `quantity = product_uom_qty` during validation**. Thus a zero/unfilled Qty is unsafe to assume no transfer; review all zeros/untouched untracked/bin products before pressing Validate. With Qty less than Demand, Odoo may prompt backorder depending operation type `create_backorder` config (`ask`, `always`, `never`); our YA policy requires no backorder, and any residual must be explicitly reconciled. Native backorder wizard supports not creating backorder, but cannot guarantee prompt unless picking operation type is checked. Do not blindly default Done on short shipment. No requirement to auto-validate in custom addon; manual operator edits Qty actual and uses native Odoo workflow.

**Current user GUI is successful creation + prefill, not yet evidence stock transfer Done or receipt.** Follow up inspect Actual Qty vs Demand, Special Transfer extra once, CDC/dapur locations, zero lines, and configured backorder behavior. Avoid recommending blind Validate for 100-SKU transfer. If necessary, add explicit pre-validation guard as a future coded requirement only on approval.

## 22. 2026-Nov-23 — Native Odoo Internal Transfer YA Validate Safety (Source v19.0.5.2.0)

Feri agreed `ok lanjut` to implementing **pre-Validate Qty zero protection and NO BACKORDER** for CDC→Dapur Internal Transfers generated from already-confirmed physical picking. Required because Odoo 19 standard `stock.picking.button_validate` can populate a Draft move `Quantity=0` with full Demand before validation, and user wants only physical Qty sent while preserving recorded MO/Special approval.

**GitHub SOURCE v19.0.5.2.0; deployment/GUI tests not done yet**:
- New source `addons/ya_material_requirement/models/stock_picking_validation.py` loaded from `models/__init__.py`, inherits standard `stock.picking`, overrides `button_validate` and `_action_done`. Strict branch: runs safeguards only when `ya.cdc.pick.confirmation.internal_transfer_id` explicitly links this native picking; all **other** standard Odoo pickings use `super()` normally. Test DB only `erp-yussyakmal-mrp-test`. No production DB use.
- Native Validate guard prevents positive Demand with Qty=0 (explicit SKU list; do not let Odoo auto-copy Demand). Operator may remove a wholly unshipped SKU from native transfer with admin review but NOT change original confirmed picking. Guards negative Qty/Demand, Qty>Demand, unauthorized SKU, total Qty/Demand above approved physical picked_qty incl. Special exactly once, and any changed CDC→Dapur source/destination/operation type/company.
- Native transfer Qty<Demand ALLOWED. `button_validate` uses context `skip_backorder=True` for linked YA pickings only (skips backorder wizard but retains normal Odoo sanity). `_action_done` forcibly uses `cancel_backorder=True` even if standard operation type configured `always`; does not globally change Odoo configuration. Short Qty detail written to native picking chatter after successful Done. No new MO, PO, or backorder.
- Conservative CDC stock guard: under CDC source `lot_stock_id` subtree, compare Qty sending plus outstanding other Odoo move-line claims (excluding this picking) against physical `stock.quant` on-hand for every product; block knowingly insufficient physical CDC stock rather than knowingly allow negative. No auto inventory mutations other than user's native Validate.
- Native `stock.picking.button_validate` ultimately performs actual stock moves only when user clicks **Validate**; Odoo standard receipt/transit route behavior remains to be audited before wider use. No custom buttons/menus added. UI existing list→form preserved.
- Static checker `script/check_material_requirement_source_readonly_ya.py` updated; README documented. After backup of MRP TEST GUI, user must `git pull`, run Python static/rules scripts, deploy addon, `-u ya_material_requirement` exactly on `erp-yussyakmal-mrp-test`, restart when safe. Existing YA-linked native transfer **does not need recreation**; the guard covers it immediately after upgrade/restart.
- Test in TEST only: Qty full (should Done, CDC down kitchen up), Qty smaller than Demand (Done actual, NO backorder, discrepancy log), Qty zero (blocked before stock movement), Qty greater than Demand (blocked), unrelated standard Odoo transfer unaffected. Validate only deliberately, as it performs irreversible-in-UI stock moves. **No actual runtime proof yet.**

## 23. Simplify: Confirmed MO → native stock.picking → print → Validate (2026-Nov-23)

Feri explicitly challenged the prior workflow as **overengineering** and approved implementing the simple alternative: **Confirmed MO grouped by date/slot/kitchen → native Odoo Internal Transfer Draft → Print Picking Operations and Delivery Slip on native stock.picking → edit physical Qty → Validate.** There is NO separate custom CDC confirmation step or custom PDF needed in the primary new flow.

**GitHub SOURCE v19.0.6.0.0, not installed or tested on server yet**:
- New `addons/ya_material_requirement/models/material_requirement_direct_transfer.py` extends existing `ya.packing.batch` and native `stock.picking`. New native link fields `ya_mr_batch_id` and `ya_mr_kitchen_id`; SQL unique one native picking per batch+destination. Action `action_mr_generate_native_transfers` locks selected existing Packing batch, reuses existing `_mr_calculate_wizard()` confirmed MO calculation (same date/slot, 1 SKU/MO), net per-kitchen shortage from stock, refuses uncertain kitchen reservations and inadequate shared CDC stock, creates standard `stock.picking` CDC/Stock → Dapur/Stock and native `stock.move` per SKU. Demand = material shortage, Quantity initially equals Demand for free untracked exact-bin stock; writing Quantity may reserve stock and show Ready, never automatically Validate or physically transfer. All-or-nothing transaction. Button duplicate returns already-linked transfers instead of recreating; check deterministic origin and SQL unique.
- Existing legacy `ya.cdc.pick.confirmation` data and its linked standard transfers remain, with NO deletion or data migration. When a batch has an existing linked old transfer, Generate opens its existing native list. When old physical confirmation exists but no transfer link, new generation is BLOCKED for reconciliation rather than duplicate dispatch. Fresh batches without old docs use new path. No changes to production or purchasing.
- Existing Material Requirement `LIST → batch FORM`: header new `Buat Internal Transfers Odoo` and `Buka Internal Transfers`. Keep `Hitung / Refresh Kebutuhan` and displayed net requirements as diagnostic. REMOVE old custom `Cetak Picking List CDC (Draft)` and `Konfirmasi Qty Picking CDC` header buttons from normal batch Form; leave historic models/reports installed because used data may exist. Native stock.picking List→selected Form→Print.
- Native standard Odoo 19 report actions confirmed in official `odoo/odoo` 19.0 `addons/stock/report/stock_report_views.xml`: `stock.action_report_picking` labelled `Picking Operations`, `stock.action_report_delivery` labelled `Delivery Slip`. No new custom print report.
- Existing `models/stock_picking_validation.py` retains historical old linking guards, adds smaller branch for NEW `ya_mr_batch_id` transfers: block zero Qty with positive Demand (Odoo auto-fills Draft Qty zero on Validate), Qty>Demand, misrouted products, negative Qty, insufficient physical CDC stock; allow partial Qty with no backorder using Odoo native `cancel_backorder=True`. Save shortage details to native picking chatter; ordinary Odoo Internal Transfers unaffected. Test DB only.
- Future Special Transfer to SAME kitchen: operator adjusts **native Demand + Qty** or adds a native move line and records reason in `stock.picking.note` (no extra MO demand/consumption). The original physical confirmation model no longer a prerequisite.
- Test procedure: backup `erp-yussyakmal-mrp-test`, `git pull`, `python3 script/check_material_requirement_source_readonly_ya.py` and `python3 script/test_material_requirement_rules_ya.py`, copy addon to active addons, `-u ya_material_requirement` on exact test DB, restart when safe. Fresh Produksi OK batch without prior old confirmations for generation; current `Packing 2026-Nov-27 S1` likely has old documents so opens existing transfer rather than regenerating. Verify one per kitchen, Qty, print outputs, no duplicate, then a controlled stock Validate and no backorder. No production deploy.
- **No server-runtime validation performed yet; source is GitHub only**. Do not claim feature works before Feri tests and provides error/output. Keep labels `YYYY-Mon-DD`.
