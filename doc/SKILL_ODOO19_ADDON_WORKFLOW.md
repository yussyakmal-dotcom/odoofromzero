> **KEPUTUSAN OWNER 26 NOV 2026 — SATU ODOO, PORT 8069:** Semua pengembangan kembali ke `main` dan `~/odoofromzero`. Branch Fase 2 digabung ke main pada `96f7585` (PR #1); source sebelum penggabungan `b56e056`. Source runtime tetap `/opt/odoo19/custom-addons`, config `/etc/odoo19.conf`, service `odoo19.service`. Jangan gunakan port 8072 atau isolated addons untuk pekerjaan berikutnya. Jalankan `script/deploy_fase2_single_odoo8069.sh` dari main setelah menghentikan proses sementara 8072; script memeriksa kompatibilitas database lain, menyimpan backup source aktif dan dump RO_SO, deploy enam modul yang berubah, upgrade hanya database `erp-yussyakmal-mrp-test-RO_SO`, lalu start service existing. Jika STOP, baca pesan sebelum melanjutkan. Backup source+DB harus berpasangan untuk rollback; jangan reset main atau menghapus database/folder lama secara sembarangan. Deploy server belum dikonfirmasi. Fase 2 belum go-live; cron tidak diaktifkan, pengujian fence v1.15.0 belum dilaporkan. **GUI-first UAT melalui port 8069 menjadi prioritas berikutnya, bukan tambahan pengujian backend.** Instruksi di bawah bersifat historis jika bertentangan dengan keputusan ini.

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
