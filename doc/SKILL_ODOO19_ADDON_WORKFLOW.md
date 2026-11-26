> **KEPUTUSAN DESAIN OWNER — CLOSING PP1 / PP2 (2026-Nov-27):** Owner menyetujui kedua tahap mendukung Scheduled Closing dan Manual Closing, dengan default berbeda: **PP1 = Scheduled Closing (alternatif Manual Closing); PP2 = Manual Closing (alternatif Scheduled Closing).** PP1 menutup penerimaan RO Toko dan RO Paket per tanggal kirim/slot agar CDC dapat menyiapkan bahan. SO Konsolidasi tetap dapat diterima setelah PP1 selama kapasitas dan status mengizinkan. PP2 menutup penerimaan SO Konsolidasi untuk tanggal kirim/slot yang sama sebelum produksi dimulai, lalu PP2 menggunakan SO kumulatif dan menerbitkan MO2 hanya jika diperlukan. Manual Closing oleh operator berwenang harus mencatat penutupan nyata, bukan bypass cutoff; Scheduled Closing mengikuti cutoff aktual (Default/Special Cutoff), bukan jam simulasi. Tidak ada jeda PP2 wajib dalam desain yang diusulkan sebelumnya; waktu mengendalikan penerimaan pesanan, status mengendalikan kelanjutan pekerjaan; keterlambatan penyelesaian merupakan peringatan, bukan alasan membatalkan kewajiban yang telah diterima. Jangan membuka kembali penerimaan yang sudah ditutup secara diam-diam; tidak boleh membuat MO berulang atau mengubah jumlah/algoritma konsolidasi yang telah disetujui. Pertahankan tanggal/slot pengiriman, SO Normal di luar konsolidasi, dan Special Cutoff untuk kebutuhan bisnis. Untuk UAT gunakan Manual Closing kedua tahap pada tanggal/slot uji yang masih terbuka, tanpa mengubah jam server dan tanpa mode testing khusus. Uji juga Scheduled Closing dengan Special Cutoff dan batas waktu nyata. **Status: keputusan desain diterima, implementasi belum dilakukan.** Prioritas implementasi berikutnya adalah Closing PP1/PP2 end-to-end dan GUI acceptance sebelum mengubah Material Requirement. Detail teknis yang masih harus ditentukan secara terbuka sebelum implementasi: konfigurasi metode per tanggal/slot dan kapan pilihan boleh berubah, akses role closing, penyimpanan status/audit penutupan atomik dengan transaksi Confirm, penanganan data yang telah ditutup menurut kebijakan lama saat migrasi, serta pemisahan peringatan keterlambatan release dari larangan penerimaan pesanan baru setelah dispatch. Jangan mengaktifkan cron, mengubah metode untuk data lama atau membuat fitur reopen tanpa persetujuan owner. Ikuti main/8069/RO_SO dan GUI backup/restore existing.

> **ATURAN WAJIB OWNER — BUSINESS-FIRST DESIGN & CONFIGURATION (2026-Nov-27):** Kebutuhan bisnis dan SOP lapangan menjadi dasar desain, bukan efisiensi algoritma semata. Jangan diam-diam mengubah flow, aturan bisnis, default, metode kalkulasi, timing, sumber stok, konfigurasi atau arsitektur karena dinilai lebih efisien secara teknis. Sebelum perubahan yang memengaruhi operasional, jelaskan alasan bisnis, dampak pada tahapan sebelum/sesudah, skenario normal dan pengecualian, konfigurasi, metode testing dan rollback; dapatkan persetujuan owner terlebih dahulu. Bila asumsi belum jelas, tandai sebagai usulan, bukan keputusan. Konfigurasi yang fleksibel harus berangkat dari kebutuhan bisnis nyata, bukan bypass testing. Pertahankan satu flow/GUI/mesin kalkulasi Material Requirement untuk MO1 dan MO2. **Default PP1 = Full Requirement (kebutuhan penuh MO); default PP2 = Shortage Requirement (kekurangan setelah memperhitungkan persediaan dan kewajiban yang relevan).** Operator berwenang dapat memilih metode sebaliknya sebelum Internal Transfer diterbitkan. Full+Full untuk mempertahankan buffer saat high season; Full+Shortage untuk memanfaatkan buffer bertahap; Shortage pada PP1 juga tersedia untuk pengurangan stok. Jangan menghitung stok yang sudah dialokasikan dua kali, jangan menganggap transfer belum diterima sebagai stok fisik, dan jangan meminta ulang demand yang sudah tercakup dalam transfer outstanding. Transfer terbit tidak otomatis diubah oleh kalkulasi ulang. Full tidak otomatis menambah buffer; Shortage dapat menghabiskan buffer. Tidak ada target buffer otomatis atau modul baru yang disetujui. Kesepakatan ini menggantikan aturan lama yang mewajibkan Full untuk setiap MO, **pada tingkat desain saja**; implementasi source dan GUI belum dilakukan/diterima. Detail kalkulasi reservasi, outstanding dan scope transaksi harus divalidasi dengan contoh bisnis sebelum coding; jangan mengubah mekanisme cutoff/PP2 atau proses lain sebagai bagian dari keputusan ini tanpa persetujuan terpisah.

> **STANDAR GUI WAJIB OWNER — TANGGAL LENGKAP (26 Nov 2026):** Semua field tanggal pada form/list/wizard custom, termasuk Expiration dan YA Tanggal Kirim, harus tampil YYYY-Mon-DD (contoh 2026-Nov-30), bulan singkatan English, tanpa menghilangkan tahun. Datetime tetap menampilkan jam jika dibutuhkan (contoh 2026-Nov-30 15:00). Gunakan field Date/Datetime native dengan options `{'numeric': True}` pada Odoo 19 agar mengikuti format bahasa `%Y-%b-%d`, bukan short locale display; admin menetapkan Date Format bahasa English yang dipakai operator melalui Settings → Translations → Languages di database RO_SO, bukan script update atau pengaturan diam-diam. Pengaturan bahasa berlaku bagi pengguna bahasa itu di database tersebut; tidak mengubah tanggal tersimpan. Tidak perlu field label tanggal kedua jika field native sudah sesuai. Gunakan format_ymondd untuk label teks custom. Source v1.19.0 sudah disesuaikan untuk explicit custom date/datetime fields dan native dates pada dedicated YA Sales form; actual browser verification dan language setup masih pending. Lima modul terdampak (planning, RO, Paket, MR, Sales capacity); tidak menambah addon/port, backup GUI saja. Jangan mengklaim semua tanggal native di seluruh Odoo sudah berubah; native views yang tidak disentuh masih bisa memakai format pendek.

> **STANDAR GUI WAJIB OWNER — REFERENCE/SKU + NAMA PRODUK (26 Nov 2026):** Di seluruh form, list, tabel detail, wizard dan review operasional Odoo yang menampilkan Reference/SKU produk, wajib tampilkan juga nama produk yang sesuai (bukan kode saja). Gunakan field produk existing bila tersedia, atau display name `[Reference] Nama Produk` bila kode dan nama digabung. Nama produk harus terlihat secara default, bukan kolom tersembunyi/opsional; jangan mengubah identitas produk, data master, kuantitas atau algoritma hanya untuk tampilan. Berlaku untuk semua modul, termasuk Planning, RO/RO Paket, SO, Pre Produksi 1/2, MO, MR, transfer, Packing, alokasi dan DO. Review source dan validasi GUI setiap fungsi secara bertahap sesuai aturan incremental acceptance; jangan melakukan perubahan massal lintas modul tanpa validasi. Standar dicatat sekarang, bukan klaim semua form telah diperbaiki atau diuji.

> **ATURAN TEGAS OWNER — BACKUP DAN RESTORE DATABASE VIA GUI:** Backup dan restore hanya melalui Database Manager GUI Odoo port 8069, menggunakan ZIP termasuk filestore. Jangan memasukkan pg_dump, pg_restore, backup database otomatis, atau backup tersembunyi ke perintah/script deployment tanpa persetujuan eksplisit owner. Sebelum upgrade, owner/Feri menyelesaikan backup GUI terlebih dahulu. Riwayat source menggunakan GitHub. Script deployment integrasi 8069 lama sudah dijalankan dan tidak boleh dipakai sebagai pola backup berikutnya. Jangan mengubah metode diam-diam. Aturan ini mengalahkan instruksi historis yang bertentangan.

> **ATURAN WAJIB OWNER — INCREMENTAL DEVELOPMENT + GUI ACCEPTANCE (26 Nov 2026):** Kerjakan satu fungsi operasional utuh dalam satu siklus, bukan banyak modul/fitur backend sekaligus lalu membebankan pemeriksaan GUI seluruhnya kepada owner. Urutan wajib: (1) sepakati kebutuhan bisnis dan posisi fungsi dalam alur besar; (2) develop satu fungsi melalui GitHub main; (3) uji backend secukupnya untuk fungsi tersebut; (4) deploy ke instalasi existing port 8069, database uji RO_SO saja sesuai workflow aman; (5) verifikasi GUI aktual, menu, akses peran, tombol, kolom, nama SKU/produk, format, status, navigasi, kemudahan operator; (6) jalankan transaksi representatif melalui GUI, pastikan handoff ke tahap berikutnya dan tidak merusak tahap sebelumnya; (7) owner menyetujui fungsi melalui GUI, checkpoint commit dan hasil nyata, baru lanjut fungsi berikutnya. Backend PASS tidak sama dengan selesai; XML/source/ORM get_view bukan bukti browser PASS. Assistant bertanggung jawab meninjau desain dan menyiapkan skenario penerimaan, bukan meminta owner menjadi pemeriksa seluruh detail dari nol; jika tidak punya akses browser server, akui keterbatasan dan minta bukti GUI yang terfokus. Jangan mengubah metode, port, database, folder runtime, atau arsitektur diam-diam. Jangan mulai fitur baru atau mengulang tes PASS tanpa perubahan relevan. Status Fase 2 saat ini: source terintegrasi ke 8069; backend banyak yang PASS tetapi GUI acceptance belum selesai. Prioritas tutup satu fungsi GUI yang sedang diperiksa, termasuk kolom Nama Produk Alokasi Final Toko, sebelum lanjut. Aturan ini mengikat sesi berikutnya dan mengalahkan petunjuk historis yang bertentangan.

> **KEPUTUSAN OWNER 26 NOV 2026 — SATU ODOO, PORT 8069:** Semua pengembangan kembali ke `main` dan `~/odoofromzero`. Branch Fase 2 digabung ke main pada `96f7585` (PR #1); source sebelum penggabungan `b56e056`. Source runtime tetap `/opt/odoo19/custom-addons`, config `/etc/odoo19.conf`, service `odoo19.service`. Jangan gunakan port 8072 atau isolated addons untuk pekerjaan berikutnya. Jalankan `script/deploy_fase2_single_odoo8069.sh` dari main setelah menghentikan proses sementara 8072; script memeriksa kompatibilitas database lain, menyimpan backup source aktif dan dump RO_SO, deploy enam modul yang berubah, upgrade hanya database `erp-yussyakmal-mrp-test-RO_SO`, lalu start service existing. Jika STOP, baca pesan sebelum melanjutkan. Backup source+DB harus berpasangan untuk rollback; jangan reset main atau menghapus database/folder lama secara sembarangan. Deploy server CONFIRMED 26 Nov 2026: BACKUP_VERIFIED_LISTABLE, RO_SO_UPGRADE_SUCCESS, service active, SINGLE_ODOO_8069_SOURCE_DEPLOYED. Backup source aktif dan RO_SO: /home/feri/odoo8069_before_integration_20261126_112740. Port 8072 dihentikan oleh owner sebelum deployment. Tidak ada upgrade database lain. GUI dan transaksi operator belum diverifikasi setelah deployment. Fase 2 belum go-live; cron tidak diaktifkan, pengujian fence v1.15.0 belum dilaporkan. **GUI-first UAT melalui port 8069 menjadi prioritas berikutnya, bukan tambahan pengujian backend.** Instruksi di bawah bersifat historis jika bertentangan dengan keputusan ini.

> **ATURAN TERBARU BUFFER DAPUR (2026-Nov-23):** Baca [CHECKPOINT_2026-11-23_KITCHEN_BUFFER.md](CHECKPOINT_2026-11-23_KITCHEN_BUFFER.md). Gudang bahan tiap dapur adalah buffer permanen untuk produksi malam/hari libur CDC. Perhitungan harus memperhitungkan semua kewajiban MO terbuka, stok fisik yang sudah dimiliki dapur, outstanding incoming yang valid, dan target buffer per SKU/dapur. Reservasi MO tidak boleh dikurangkan dua kali. Fungsi matematis baru saat ini **source-only, belum terintegrasi ke pembuat Internal Transfer**; jangan klaim runtime PASS.

> **CHECKPOINT AKTIF / START HERE (23 Nov 2026):** [doc/CHECKPOINT_2026-11-23_MO_MATERIAL_CDC.md](CHECKPOINT_2026-11-23_MO_MATERIAL_CDC.md). Resume MO→Material Requirement→CDC di DB test. 20 MO Confirmed, 247 raw moves, 97 kombinasi dapur-bahan; source `ya_material_requirement` 19.0.1.1.0 belum dibuktikan terinstal; replenishment CDC via standar Purchase oleh Admin Gudang **DI LUAR** workflow. Catatan bawah adalah sejarah, bukan status terbaru.

# SKILL — Workflow Odoo 19 Addon: GitHub → Feri Server → MRP Test

**Tujuan:** panduan praktik untuk sesi ChatGPT berikutnya agar tidak mengulang trial-and-error deploy/install addon. **Baca file ini bersama [HANDOVER_ODOO_FROM_ZERO.md](HANDOVER_ODOO_FROM_ZERO.md) sebelum menulis/memasang addon.** Ini petunjuk operasional proyek, bukan konfigurasi skill otomatis pada ChatGPT.

**Status terakhir (22 Nov 2026):** `ya_production_planning` sudah terinstal di `erp-yussyakmal-mrp-test`. Flow Upload Planning (menu) → list Draft/Published → Upload Baru → XLSX → Validate/Preview → Save Draft, lalu Publish per dapur sudah dinyatakan sesuai alur oleh pengguna. Kosmetik UI pending. RO toko belum dibuat.

## 0. Jangan salah database

- DB pengembangan **hanya**: `erp-yussyakmal-mrp-test`.
- **JANGAN SENTUH**: `erp-yussyakmal` (utama), `erp-yussyakmal-integer-test` (Purchasing test).
- Ubuntu/Odoo: user layanan `odoo19`, service `odoo19.service`, Odoo Python `/opt/odoo19/venv/bin/python3`, binary `/opt/odoo19/odoo/odoo-bin`, config `/etc/odoo19.conf`.
- Addon aktif: `/opt/odoo19/custom-addons/`; Git repo user Feri: `~/odoofromzero`. `addons_path` pada `/etc/odoo19.conf` sudah terverifikasi mencakup custom-addons.
- Backup menggunakan **GUI Odoo**, pilihan pengguna; pastikan selesai/valid sebelum instalasi/upgrade yang menyentuh DB. Jangan mengganti preferensi ini dengan `pg_dump` kecuali diminta.
- Jangan menyimpan data customer/vendor, password, token, atau file sumber master privat di GitHub publik.

## 1. Selalu GitHub-first; jangan beri ZIP/copas manual

1. Assistant **buat/update** `addons/<module>/...` dan `script/...py` langsung pada `yussyakmal-dotcom/odoofromzero` (Gunakan GitHub connector).
2. Sertakan tautan repo, commit SHA, dan instruksi terminal yang bisa di-copy.
3. Feri:
   ```bash
   cd ~/odoofromzero
   git pull
   ```
4. **`git pull` saja belum mengganti addon yang sedang dipakai server.** Selalu deploy folder repo ke `/opt/odoo19/custom-addons/<module>/` untuk perubahan kode.
5. Hanya nyatakan “terinstal” setelah `ir.module.module.state=installed` dan model diperiksa. Jangan menyamakan “source preflight PASS” dengan “instalasi PASS”.

## 2. Jalankan skrip sesuai jenisnya (INI PENTING)

**A. Skrip static/source yang hanya membaca repo dan tidak perlu env Odoo:** jalankan sebagai `feri`, **bukan** `odoo19` di folder `/home/feri`, karena ownership/parent permission menutup akses untuk service user.

```bash
cd ~/odoofromzero
python3 script/check_production_planning_source_readonly_ya.py
# Target: ERROR_COUNT: 0, SOURCE_PREFLIGHT_OK
```

**B. Skrip ORM read-only/rollback yang perlu Odoo `env`:** jalankan dengan Odoo shell sebagai `odoo19` dan **stdin redirection oleh shell Feri**, jangan meminta odoo19 membuka file privat secara path.

```bash
cd ~/odoofromzero
sudo -u odoo19 /opt/odoo19/venv/bin/python3 \
  /opt/odoo19/odoo/odoo-bin shell \
  -c /etc/odoo19.conf \
  -d erp-yussyakmal-mrp-test \
  --no-http \
  < script/NAMA_SKRIP_ORM.py
```

**Kesalahan yang pernah terjadi:**
- `/opt/odoo19/venv/bin/python3: Permission denied` bila Feri langsung menjalankan executable yang tak diizinkan untuk user itu.
- `can't open file /home/feri/... Permission denied` bila `odoo19` disuruh membaca skrip dari home Feri.
- `sudo -u odoo19 python3 - < script/source.py` **tidak menyelesaikan** source preflight, karena skrip memakai `Path.cwd()` dan `odoo19` tetap tidak boleh membaca folder repo. Gunakan **`python3` sebagai Feri**.
- Jangan `chmod -R 777` atau membuka permission seluruh home untuk mengatasi ini.

## 3. Deploy addon ke custom-addons

**Sebelum menyalin:** source preflight PASS, review diff/perubahan, backup GUI jika meng-upgrade DB. Untuk addon baru cek apakah direktori aktif sudah ada sebelum overwrite.

```bash
cd ~/odoofromzero
git pull
python3 script/check_production_planning_source_readonly_ya.py

# Contoh untuk ya_production_planning; sesuaikan nama jika addon lain.
sudo cp -a addons/ya_production_planning/. \
  /opt/odoo19/custom-addons/ya_production_planning/
sudo chown -R odoo19:odoo19 \
  /opt/odoo19/custom-addons/ya_production_planning
```

**Addon BARU:** jika direktori belum ada, salin folder pertama kali dengan `sudo cp -a addons/<module> /opt/odoo19/custom-addons/`. **Addon existing:** salin isi dengan `cp -a .../. .../`. Cek `/etc/odoo19.conf` bila ada error addon tak ditemukan.

**Jangan deploy sekaligus semua addon** ketika hanya satu yang berubah.

## 4. Instalasi pertama vs upgrade

Setelah backup GUI MRP test siap:

**Instalasi pertama (belum installed):**
```bash
sudo -u odoo19 /opt/odoo19/venv/bin/python3 \
  /opt/odoo19/odoo/odoo-bin \
  -c /etc/odoo19.conf \
  -d erp-yussyakmal-mrp-test \
  -i ya_production_planning \
  --stop-after-init --no-http
echo "INSTALL_EXIT_CODE=$?"
```

**Upgrade addon yang sudah installed:** terutama bila **model/field, XML view, menu, ACL, manifest** berubah:
```bash
sudo -u odoo19 /opt/odoo19/venv/bin/python3 \
  /opt/odoo19/odoo/odoo-bin \
  -c /etc/odoo19.conf \
  -d erp-yussyakmal-mrp-test \
  -u ya_production_planning \
  --stop-after-init --no-http
echo "UPGRADE_EXIT_CODE=$?"
```

**Upgrade harus diikuti restart** setelah exit code `0`:
```bash
sudo systemctl restart odoo19
sudo systemctl is-active odoo19
```

Jika hanya Python method berubah tanpa XML/model/ACL, biasanya **deploy + restart** cukup. Bila XML/data record berubah, restart **saja tidak cukup**: harus `-u`. Restart `odoo19.service` bisa mengganggu semua database yang memakai service, jadi koordinasikan bila diperlukan.

**Jika exit code bukan 0:** jangan lanjut restart/publish atau klaim PASS; baca output terminal, `/var/log/odoo19/odoo19.log` (bila relevan), atau `sudo journalctl -u odoo19 --since "5 minutes ago" --no-pager -l | tail -n 150`. Jangan mengulang `-u` tanpa membaca error.

## 5. Verifikasi registry/model & UI

Instalasi CLI yang tidak mengeluarkan output **bukan** bukti terinstal. Cek via Odoo shell `env`:

```bash
sudo -u odoo19 /opt/odoo19/venv/bin/python3 \
  /opt/odoo19/odoo/odoo-bin shell \
  -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test --no-http <<'PY'
m = env['ir.module.module'].search([('name','=','ya_production_planning')], limit=1)
print('DATABASE:', env.cr.dbname)
print('MODULE_STATE:', m.state if m else 'NOT FOUND')
print('PLANNING_MODEL:', 'ya.production.planning' in env)
print('LINE_ROW_FIELD:', 'line_row' in env['ya.production.planning.line']._fields)
PY
```

Jika field `line_row` ada di XML view tetapi Odoo browser memberi OwlError `field is undefined`, kemungkinan view sudah berubah tetapi worker web masih menggunakan kode Python lama. **Deploy terbaru → upgrade module untuk XML/model/ACL → restart → refresh browser**, kemudian periksa registry. **Jangan mengubah data master untuk error UI**.

Jika upload memunculkan notifikasi `Created Draft` tetapi popup `Cannot read properties of undefined (reading 'map')`, operasi Save Draft bisa **sudah tersimpan**; error sebelumnya disebabkan `ir.actions.act_window` dinamis tanpa `views`. Kode navigasi ditambah `'views': [(False, 'list'), (False, 'form')]`. Periksa list dahulu sebelum reupload untuk menghindari REPLACE tak disengaja.

## 6. Aturan dan tes YA Production Planning yang sudah disepakati

- Sumber: XLSX per jadwal; `info: NO | Sheet | Code Dapur`; sheet dapur `DAPUR | Product | Max | Unit`; SOP menentukan SKU per sheet.
- S1 05.00, S2 09.00, S3 11.00 WIB. **Kunci record: tanggal kirim + slot + kode dapur**.
- `Product` = `[Reference] Nama Produk`; `Unit` mengacu **BoM output UoM**, bukan otomatis stock UoM master. Jumlah Max adalah kapasitas per jadwal, bukan BoM output qty.
- **CREATE** Draft jika kunci tidak ada; **REPLACE** Draft jika kunci ada dan masih Draft; **SKIP** Published tanpa menimpanya. Tidak ada efek pada dapur yang tidak disebut file.
- **Publish per dapur** (tombol `Publish This Kitchen`), bukan publish seluruh hasil upload. List satu halaman menampilkan Draft + Published dan filter status.
- **UI final:** menu `Upload Planning` masuk ke **list**, tombol `Upload Baru` di toolbar membuka wizard XLSX. Draft Max editable, Published read-only. User meminta kosmetik UI minor di-PENDING.
- **Status RO:** belum ada. Published + Max > 0 baru menjadi **sumber template RO toko pada tahap berikut**, bukan berarti toko sekarang dapat mengisi RO di sistem.
- Tes realistis berikutnya: UI upload hari/slot baru, REPLACE Draft, SKIP Published tanpa kehilangan data, Publish satu dapur saja, verifikasi Read-only setelah publish; cek user operator vs manager. **Jangan mengklaim semua tes PASS bila baru alur GUI umum yang dinyatakan OK**.
- Kode ada di `addons/ya_production_planning`; status sumber di `doc/HANDOVER_ODOO_FROM_ZERO.md` dan `doc/STATUS_PENGEMBANGAN_MRP.md`.

## 7. Cara memulai sesi baru (prompt handover singkat)

> Buka dan baca `doc/HANDOVER_ODOO_FROM_ZERO.md`, `doc/STATUS_PENGEMBANGAN_MRP.md`, dan **`doc/SKILL_ODOO19_ADDON_WORKFLOW.md`** di GitHub `yussyakmal-dotcom/odoofromzero` sebelum mengubah apa pun. Mulai dari checkpoint terakhir, jangan audit ulang BoM/Work Center. Gunakan GitHub-first, `git pull`, deploy custom-addons, `-i` pertama kali / `-u` upgrade, restart service dan cek status. DB hanya `erp-yussyakmal-mrp-test`; GUI backup sesuai pilihan user. Modul Planning sudah terinstal dan flow disetujui; kosmetik pending; pekerjaan berikutnya RO toko dari Published Planning.

## 8. Selalu perbarui dokumentasi setelah milestone

Setelah hasil tes nyata, tulis **apa yang diuji, perintah, database, commit, output PASS/FAIL, batas yang belum diuji** pada handover & status. Jangan mengganti status historis menjadi “lulus” hanya karena kodenya sudah di-commit. Hindari menyebarkan log yang berisi rahasia ke repo publik.

## 9. Aturan Max BoM (kode versi 19.0.1.4.0 — UJI BELUM PASS)

Sebelum mengerjakan RO Toko, validasi kapabilitas penyesuaian Max menjadi **kelipatan terdekat BoM output** dan peringatan asal→baru. Sumber `addons/ya_production_planning/models/capacity_rules.py` digunakan oleh importer dan Draft edit. `python3 script/test_planning_capacity_batch_pure_ya.py` adalah tes matematika **tanpa database**. Setelah source preflight PASS, deploy ke custom-addons, upgrade hanya `erp-yussyakmal-mrp-test` via `-u ya_production_planning`, restart `odoo19.service` dan cek UI. **Jangan upload ulang jadwal produksi sungguhan untuk tes**: gunakan tanggal/slot uji. Preview seharusnya menunjukkan `Excel Max | BoM Output | Adjusted Max`, kolom `Adjusted?` dan ringkasan warning, kemudian Save Draft menyimpan adjusted. Inline edit Draft perlu warning dan corrected qty. Publish ditolak jika ada Max lama non-kelipatan. Published tidak boleh berubah karena upload baru. Test edge case BoM 24: 50→48, 70→72, 36→24 (seri ke bawah), 0→0. Field Max Integer: BoM output fractional/invalid harus ditolak untuk review. **Jangan klaim PASS sebelum bukti server/GUI.**

## Keputusan final Packing — pembulatan Qty konsolidasi SELALU KE ATAS (22 November 2026)

**KEPUTUSAN PENGGUNA (final):** jumlah pesanan RO per toko **bebas, tidak dibulatkan**. Pada saat **Gudang Packing mengonsolidasikan** seluruh permintaan satu SKU untuk tanggal pengiriman + slot + dapur (ditambah SO sesuai prioritas yang sudah disepakati), **Qty Produksi/MO harus dibulatkan SELALU KE ATAS** ke kelipatan `mrp.bom.product_qty` (dalam UoM hasil BoM). **Tidak boleh dibulatkan ke bawah atau memakai kelipatan terdekat pada tahap konsolidasi**. Rumus untuk kebutuhan positif: `Qty Produksi = ceil(Total Kebutuhan / Qty Output BoM) * Qty Output BoM`; total nol → produksi nol. Contoh BoM 24 Pcs, total kebutuhan 49 Pcs → produksi 72 Pcs (bukan 48); total 70 → produksi 72.

**Kelebihan produksi setelah memenuhi kebutuhan asli akan dikirim/dialokasikan ke toko**, bukan hilang atau dipotong dari Qty Pesan. Kuantitas RO toko tetap utuh dan terlacak; alokasi Qty tambahan harus dicatat secara terpisah dari Qty RO asli agar audit jelas. Rincian algoritma pembagian antar-toko dan penanganan bila hasil pembulatan melebihi `Planning Max Capacity` belum diputuskan; jangan mengarang kebijakan kapasitas, kekurangan, atau distribusi sebelum implementasi.

**JANGAN SALAH TERAPKAN:** fungsi `closest_batch_multiple` saat ini **khusus normalisasi Planning Max Capacity (kelipatan terdekat)**. Untuk **Packing consolidation** nanti dibutuhkan fungsi pembulatan ke atas yang **berbeda**. Tidak ada implementasi modul RO/Packing baru pada checkpoint ini; ini dokumentasi aturan untuk desain berikutnya.

## 10. RO Toko addon fase pertama (source only)

`addons/ya_store_ro/` adalah **addon BARU**, tidak boleh menjalankan `-u` seperti Planning sebelum terinstal. Pertama kali setelah preflight `python3 script/check_ya_store_ro_source_readonly.py` PASS dan setelah persetujuan untuk uji, `sudo cp -a addons/ya_store_ro /opt/odoo19/custom-addons/`, backup GUI test, `-i ya_store_ro --stop-after-init --no-http` hanya pada `erp-yussyakmal-mrp-test`, kemudian restart service, cek modul installed, dan uji wizard. **Belum dilakukan** saat file dibuat. Ini hanya generator Excel Published Planning → Reference/Nama Produk + Qty Pesan kosong, tidak mengimpor RO dan belum ada izin toko. Lihat `addons/ya_store_ro/README.md`.
