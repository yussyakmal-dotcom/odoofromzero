# CHECKPOINT — ODOO FROM ZERO / Fase 2 RO + SO
**Tanggal:** 25 November 2026 (WIB)
**Status:** checkpoint perpindahan environment dan dokumentasi; **belum ada install addon Fase 2**
**Repository:** `yussyakmal-dotcom/odoofromzero`, `main`

> **START HERE untuk pekerjaan Fase 2 berikutnya.** Baca juga `doc/HANDOVER_ODOO_FROM_ZERO_2026-11-23_RO_TO_STORE_PASS.md` (histori Fase 1) dan `doc/FASE2_SO_CAPACITY_AND_PACKING_DESIGN_2026-11-25.md` (keputusan owner). Jangan membaca checkpoint ini secara terpisah dari gambaran besar RO → produksi → PCK → toko.

## 1. Database Fase 2 — keputusan OWNER terbaru, mengesampingkan instruksi DB lama
- **DB aktif Fase 2 (satu-satunya target write/install/upgrade/test):** `erp-yussyakmal-mrp-test-RO_SO`.
- User melaporkan DB ini dibuat sebagai **clone** dari `erp-yussyakmal-mrp-test`, dan memberikan UI:
  `http://192.168.202.197:8069/odoo?db=erp-yussyakmal-mrp-test-RO_SO`.
- `erp-yussyakmal-mrp-test`: **referensi Fase 1; jangan diubah/di-install Fase 2**.
- `erp-yussyakmal`: **DB utama; jangan disentuh**.
- `erp-yussyakmal-integer-test`: **Purchasing test; jangan disentuh**.
- Ini laporan dari user bahwa clone sudah dibuat; **belum ada output server verifikasi clone/backup terpisah setelah pergantian target**. Jangan mengklaim clone sudah diaudit atau telah dibuat backup GUI baru bila belum ada bukti.
- Semua skrip ORM Fase 2 yang menulis data atau menjalankan rollback wajib menolak DB selain `erp-yussyakmal-mrp-test-RO_SO`. Read-only audit yang dibuat sebelumnya telah disesuaikan agar mengunci clone; historis audit lama pada Fase 1 tetap dicatat sebagai bukti awal **bukan** hasil audit clone.
- Odoo 19 Community pada Ubuntu 24. Feri mengoperasikan server; source GitHub-first; repo server `~/odoofromzero`, addon aktif `/opt/odoo19/custom-addons/`, Python `/opt/odoo19/venv/bin/python3`, bin `/opt/odoo19/odoo/odoo-bin`, conf `/etc/odoo19.conf`, service `odoo19`.

## 2. Fase 1 — SUDAH PASS, jangan rusak atau mengulangnya sebagai tugas utama
- Planning XLSX per dapur dan Publish; RO Toko; RO Konsolidasi; Pre Produksi; native dapur MO; Material Requirement dan CDC → dapur; MO Done; FG ke Packing; Paket cross-kitchen native assembly dan ordinary; DO store, stock baru masuk toko ketika store receipt; penanganan sisa melalui native Internal Transfer petugas.
- RO biasa → stok toko dinyatakan **GOOD** oleh owner, dan E2E paket+ordinary serta residual transfer lulus rollback TEST; lihat handover utama untuk batas bukti tiap pengujian. Tidak mengklaim accounting/HPP/POS termasuk scope.
- Operator menangani volume besar; SOP bisnis dan mengurangi pekerjaan manual lebih penting daripada menambah pembatas yang tidak perlu. **Jangan implement SO dengan mengubah addon RO stabil secara tidak sengaja.**

## 3. Keputusan bisnis Fase 2 (baseline final)
- Custom Sales Order YA menggunakan model Odoo `sale.order`, di menu **YA Production Capacity → SEBELUM PRODUKSI → Sales Order**; **tanggal pengiriman dan slot Published Planning wajib sejak create**. Confirm hanya boleh jika kapasitas tersedia serta reservasi berhasil.
- Native SO biasa dari menu Sales tetap bisa dibuat **tanpa slot YA**, tidak ikut reservasi kapasitas/otomasi YO. Dua jalur dibedakan backend, bukan sekadar tampilan.
- Kapasitas per (delivery date, slot, kitchen, SKU) hanya dari **Published Production Planning**. **Total keluaran MO1+MO2 <= Planning Max**; **seluruh SO Confirm juga <= Planning Max**, termasuk kebutuhan komponen Paket lintas dapur. Perhatikan kelipatan batch BoM dan jangan double-count produksi MO1 sebagai tambahan beban SO.
- RO Confirm tidak memegang kapasitas yang tak bisa dialihkan; SO Confirm mengambil prioritas dan dapat mengurangi alokasi RO bahkan hingga nol. **Alokasi final SO → RO dilakukan di Packing** dari stok aktual, bukan membekukan tujuan sejak Pre Produksi.
- MO1 saat Pre Produksi, MO2 opsional sebagai kekurangan incremental yang masih muat di batas gabungan; satu SKU di satu slot boleh dua MO terencana. Sampel SOP **delivery 27 Nov S1 05.00**: 25 Nov 08.00 MO1, 26 Nov 15.00 SO cutoff, 15.30 MO2 final, 18.00 transfer bahan tambahan CDC→dapur, 20.00 produksi, 27 Nov 05.00 dispatch. Contoh tersebut tidak otomatis merupakan konfigurasi jadwal S2/S3.
- Sisa barang PCK ditangani manual via native Internal Transfer ke toko sesuai SOP, **bukan RO/SO fiktif**.
- Operasional out-of-band **hanya informasi kontekstual, BUKAN perubahan desain atau scope Fase 2**: authorized native MO manual untuk antisipasi kekurangan PCK dan native internal transfer toko→PCK untuk kebutuhan SO. Jangan jadikan jalur ini logika khusus reservasi kapasitas.

## 4. Audit yang SUDAH DILAKUKAN sebelum clone
Pada `erp-yussyakmal-mrp-test`, Feri menjalankan `script/audit_fase2_sale_capacity_schema_readonly_ya.py` dan memberikan **FASE2_READ_ONLY_SCHEMA_AUDIT_PASS**.
Modul terpasang: sale 19.0.1.2; sale_stock 19.0.1.0; mrp 19.0.2.0; ya_production_planning 19.0.1.4.0; ya_store_ro 19.0.8.1.3; ya_package_store_ro 19.0.1.3.0; ya_workflow_navigation 19.0.1.0.1; ya_material_requirement 19.0.6.1.0; ya_packing_store_delivery 19.0.1.4.0.
Published Planning 21, lines 788. 1 Draft SO, 0 Confirmed SO. `sale.order.line.product_uom` **absent** on Odoo 19 installed; inspect actual names before custom code.
**Audit asal bukan bukti schema/status clone sesudah cloning.**

## 5. Source yang sudah dibuat Fase 2; **BELUM INSTALLED/TESTED**
- `addons/ya_sale_production_capacity/`: addon isolasi tahap awal, v19.0.1.0.0; inherit sale.order, penanda `ya_is_capacity_so`, `ya_delivery_date`, `ya_slot`, backend create/write validation Published date+slot; menu YA terpisah, native Sales tetap normal. **Custom YA action_confirm fail-closed** karena reservasi kapasitas belum dibangun.
- `script/check_fase2_ya_sale_stage1_source_ya.py`: source AST/XML static preflight. Hasil PASS belum dilaporkan oleh Feri.
- `script/audit_fase2_sale_capacity_schema_readonly_ya.py`: read-only ORM audit, **database guard sudah dipindahkan ke clone `erp-yussyakmal-mrp-test-RO_SO`**.
- `doc/FASE2_SO_CAPACITY_AND_PACKING_DESIGN_2026-11-25.md`: spesifikasi baseline penuh.
- **Belum diimplementasikan:** reservasi atomik capacity untuk Custom SO dan Paket, confirm yang nyata, MO2 dan budget gabungan MO, alokasi final Packing serta DO SO, link procurement stock; jangan klaim SO siap transaksi.
- Source Fase 1 `addons/ya_store_ro/models/packing_batch.py` masih unik satu MO per (batch,planning,SKU) dan frozen RO allocation; dua titik ini memerlukan desain migrasi yang minimal dan regresi.

## 6. Next action untuk Feri — tidak perlu ulang audit original
**A. Source-only preflight (tidak menyentuh DB):**
```bash
cd ~/odoofromzero
git pull
python3 script/check_fase2_ya_sale_stage1_source_ya.py
python3 -m compileall -q addons/ya_sale_production_capacity
```
Syarat lanjut: `FASE2_YA_SALE_SOURCE_PREFLIGHT_PASS` dan compile exit 0.

**B. Satu kali verifikasi *clone baru*, read-only, bila perlu sebelum install:**
```bash
sudo -u odoo19 /opt/odoo19/venv/bin/python3 \
  /opt/odoo19/odoo/odoo-bin shell \
  -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test-RO_SO --no-http \
  < script/audit_fase2_sale_capacity_schema_readonly_ya.py
```
Syarat: tepat nama DB clone tercetak dan audit PASS. Ini **bukan** mengulang pengujian Fase 1.

**C. Install pertama hanya setelah backup/restore point clone disetujui owner dan source preflight PASS:**
- Feri cek **belum installed** dulu. Jangan gunakan `-u` untuk install pertama.
- Deploy hanya `addons/ya_sale_production_capacity` ke `/opt/odoo19/custom-addons/ya_sale_production_capacity`; jangan deploy seluruh addons, jangan upgrade addon Fase 1.
- Instal `-i ya_sale_production_capacity` dengan **`-d erp-yussyakmal-mrp-test-RO_SO`**, `--stop-after-init --no-http`. Jika gagal, STOP dan baca error, jangan mengulang membabi buta.
- Restart Odoo di window sesuai pengelolaan server (restart service dipakai bersama database lain) setelah install exit 0; verifikasi module state `installed`, view/menu, mandatory Published schedule, standar Sales Order unaffected. **Custom YA SO Confirm masih tertutup sengaja.**
- Sesudah itu lanjut mesin reservasi SO, Paket, MO2, dan re-alokasi Packing secara bertahap, dengan test rollback hanya pada clone.

## 7. Larangan status/interpretasi keliru
- **DO NOT** menyebut source committed sebagai sudah terinstal.
- **DO NOT** menganggap clone verified / preflight PASS / addon running sebelum bukti Feri.
- **DO NOT** memakai `erp-yussyakmal-mrp-test` untuk Fase 2 meski banyak dokumen sejarah mencantumkannya.
- **DO NOT** mengubah rancangan kapasitas karena informasi SOP out-of-band.
- **DO NOT** membuat backup privat, data pelanggan, token, atau URL intranet yang sensitif menjadi script command publik; URL internal di atas hanya untuk konteks operator.

## 8. Owner UI feedback — menu visible, input slot belum terlihat (25 Nov)
- Owner melaporkan menu `YA Production Capacity → Sales Order` **sudah muncul**, tetapi form masih terlihat standar, belum terlihat Tanggal Kirim dan Slot. Ini **belum** membuktikan seluruh modul berfungsi; jangan nyatakan UI PASS.
- Investigasi source: view tahap awal mewarisi form Sales secara global, lalu menambah group di **akhir** `//sheet`; layout dapat membuat input tidak terlihat di area utama dan pemakaian view native/default action tidak eksplisit. Perbaikan source: `view_ya_capacity_sale_order_form` dijadikan `mode=primary` untuk YA saja, wajib field tanggal+slot ditempatkan **sebelum tab order lines/notebook**, action YA mengikat **list + form** eksplisit dengan `ir.actions.act_window.view`. Native Sales form tidak diubah.
- Version `ya_sale_production_capacity` naik `19.0.1.0.1`. Update static source gate untuk memeriksa primary view dan action bindings.
- **Status: source fix committed, BUKAN server deployed/test PASS.** Next Feri `git pull`, source preflight, deploy hanya addon baru ke `/opt/odoo19/custom-addons/`, verifikasi module already installed pada clone, **`-u ya_sale_production_capacity` pada CLONE saja** (bukan `-i`), exit 0, restart terkoordinasi, refresh UI, periksa apakah Tanggal Kirim dan Slot muncul di atas detail produk saat New YA SO. Jika masih tidak muncul, audit `ir.actions.act_window.view` dan resolved `fields_view_get` pada clone read-only; jangan mengubah Fase1.
- **Custom SO Confirm tetap sengaja BLOKIR** sampai mesin reservasi kapasitas dibuat.

## 9. Koreksi owner terhadap layout YA SO (25 Nov 2026)
- Owner mengklarifikasi: **field tanggal/slot sebenarnya sudah ada, hanya terlalu bawah**; tidak ada bukti field hilang. Tempatkan **YA Tanggal Kirim** dan **YA Slot Kirim** di bawah Payment Terms dalam bagian informasi utama SO. Rename label `YA Slot Produksi` → `YA Slot Kirim`, **nama field teknis `ya_slot` tetap**.
- Source diperbarui hanya pada addon `ya_sale_production_capacity`: dedicated primary view memakai XPath `//field[@name='payment_term_id']` dengan `position='after'`, dua field wajib YA ditempatkan tepat di situ; tidak ada group tambahan di bawah notebook. `__manifest__` versi `19.0.1.0.2`. Static source preflight diperbarui.
- **SOURCE ONLY, UI belum dibuktikan setelah perubahan.** Feri: `git pull`, `python3 script/check_fase2_ya_sale_stage1_source_ya.py`, deploy *hanya* addon YA SO, `-u ya_sale_production_capacity` *hanya* pada `erp-yussyakmal-mrp-test-RO_SO` setelah backup clone, lalu refresh form. Bila upgrade gagal pada XPath, hentikan dan inspeksi inherited view; jangan ubah Fase 1.
- Custom SO Confirm tetap fail-closed; logika produksi/kapasitas tidak berubah karena revisi layout ini.

## 10. Standar Tanggal Global untuk SEMUA Form YA — keputusan owner (25 Nov 2026)
- **Wajib** format tampilan tanggal operator **`YYYY-Mon-DD`**; contoh `2026-Nov-27` (bulan singkatan Inggris 3 huruf). Berlaku ke seluruh form/list/wizard/report **baru maupun modifikasi**, bukan hanya Custom SO.
- Implementasi reuse `addons/ya_store_ro/models/date_labels.py::format_ymondd` dan pola field computed display `addons/ya_store_ro/models/store_ro.py::delivery_date_yyyymmdd`. Jangan menciptakan standar baru di addon lain.
- Data yang tersimpan tetap `fields.Date` Odoo dan jadwal Planning tetap cocok; jika input harus menggunakan date picker asli, tampilkan label computed standar tanpa menjadikannya input Char. Jangan mengklaim form yang sedang terpasang otomatis berubah hanya karena dokumentasi diperbarui.
- Ketentuan ini telah ditambahkan di **bagian paling atas handover utama**, sehingga saat sesi baru semua perubahan UI mengikuti standardisasi tanggal sebelum menulis XML/Python.
- Khusus Custom SO saat ini: `YA Tanggal Kirim` dan `YA Slot Kirim` posisinya di bawah Payment Terms dalam source, tetapi perubahan format visible-date khusus SO masih perlu implementasi dan pengujian server clone tersendiri.

## 11. Implementasi source format tanggal SO — 25 Nov 2026
- Standar global `YYYY-Mon-DD` kini diimplementasikan **di SOURCE** addon SO versi `19.0.1.0.3` (belum diverifikasi deployed/UI).
- `sale.order.ya_delivery_date` tetap `fields.Date` yang editable dengan date-picker standar; `sale.order.ya_delivery_date_label` dihitung dari `odoo.addons.ya_store_ro.models.date_labels.format_ymondd`, tanpa menggandakan logika format dan tanpa mengubah ISO date di database.
- Form primary YA: di bawah Payment Terms terdapat input `YA Tanggal Kirim`, label baca-saja `Format YYYY-Mon-DD`, serta `YA Slot Kirim`. List custom SO menampilkan computed label `YA Tanggal Kirim` (bukan kolom native date) supaya konsisten dengan RO.
- Source preflight `script/check_fase2_ya_sale_stage1_source_ya.py` melindungi keberadaan label+reuse formatter. Tidak ada perubahan pada SO standar, RO/MO/DO, reservasi kapasitas maupun Paket.
- Next Feri: `git pull`, source preflight PASS, compileall, deploy hanya `ya_sale_production_capacity`, `-u ya_sale_production_capacity` **hanya** pada `erp-yussyakmal-mrp-test-RO_SO` sesudah backup, restart service pada waktu aman, refresh UI. Buktikan tanggal `2026-Nov-27` pada form/list dan date picker tetap bisa memilih tanggal; Custom SO Confirm masih sengaja diblokir.
