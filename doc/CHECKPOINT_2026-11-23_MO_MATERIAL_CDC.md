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
