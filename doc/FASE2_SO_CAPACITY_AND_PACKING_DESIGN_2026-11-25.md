# Fase 2 — Custom Sales Order YA / Pengadaan Produk Jadi
Tanggal: 2026-11-25. Status: DESAIN DISETUJUI OWNER; BELUM IMPLEMENTASI/TEST ODOO.
Acuan: doc/HANDOVER_ODOO_FROM_ZERO_2026-11-23_RO_TO_STORE_PASS.md dan doc/SKILL_ODOO19_ADDON_WORKFLOW.md.
Fase 1 RO biasa + Paket sampai store receipt dan surplus native transfer telah PASS rollback TEST; jangan ulangi happy path atau ubah addon stabil tanpa regresi.

## Scope
- Jalur **Custom SO** di menu YA Production Capacity → SEBELUM PRODUKSI, menggunakan model `sale.order` standar beserta penanda workflow YA yang dilindungi backend.
- Custom SO **tidak boleh dibuat tanpa delivery date + slot yang tersedia di Published Planning**. Tidak boleh Confirm jika validasi kapasitas gagal. Produk jadi biasa dan Paket lintas dapur didukung.
- Sales Order **biasa** dari Sales → Orders tetap dapat dibuat tanpa slot YA, tidak memesan kapasitas YA, tidak otomatis masuk alokasi YA. Jalur SOP native/manual **di luar scope addon**.
- SO Confirm mengikat prioritas kapasitas produksi; RO Confirm **tidak** mereservasi kapasitas yang terlindungi dari SO belakangan.
- Setiap SO yang dikonfirmasi mencadangkan kapasitas per SKU/BoM keluaran dapur di delivery date+slot; kebutuhan Paket harus diekspansi ke komponen produksi dapur tanpa menghitung ganda. Reservasi SO berikutnya atomik per slot, cegah race.
- Published Planning XLSX Admin Produksi adalah SATU sumber kapasitas; tidak membuat master kapasitas baru.

## Batas kuantitas dan logika
- Per SKU dapur tanggal slot, `MO1_output + MO2_output <= Published_Max`, dengan kuantitas MO mengikuti kelipatan output BoM.
- Per SKU sumber daya yang sama, kebutuhan semua SO Confirm harus dapat ditampung kapasitas Published Planning (untuk Paket berdasarkan kapasitas komponen nyata, bukan Paket SKU sebagai dapur palsu).
- Jangan hitung kapasitas MO1 yang semula dipicu RO dan kemudian diprioritaskan untuk SO dua kali. SO belakangan boleh menggunakan output MO1; MO2 hanya tambahan produksi yang dibutuhkan, bukan selalu sebesar Qty SO baru.
- MO1 saat Pre Produksi pukul 08.00 (berdasarkan RO + SO yang telah Confirm); MO2 opsional dikunci pukul 15.30 sesudah SO cut-off pukul 15.00. Satu SKU boleh memiliki hingga dua MO bertahap dalam slot, satu batas kapasitas gabungan.
- Alokasi hasil untuk penerima **BELUM FINAL** saat Pre Produksi/MO; Packing melakukan alokasi final berdasarkan stok produk jadi aktual dan prioritas SO terlebih dahulu, lalu RO toko, sebelum membuat DO.
- Permintaan RO asli dan histori tetap utuh; jatah akhir RO boleh nol. DO toko tetap berasal dari alokasi Packing final; SO fulfillment sendiri harus dikaitkan ke jalur native Sales/Delivery yang tepat (verifikasi schema/routing dahulu).
- Kelebihan di Packing diselesaikan petugas memakai native Internal Transfer ke toko sesuai SOP, **tidak** membuat SO/RO fiktif atau memilih toko otomatis.
- Pembulatan BoM/kapasitas serta prorata RO menggunakan aturan Fase 1; jangan mengabaikan Paket component protection atau mengubah kelipatan output.

## SOP contoh: delivery 2026-11-27 S1 05.00 WIB
- 2026-11-25 08.00: Pre Produksi + MO1 dan kebutuhan material awal.
- Sampai 2026-11-26 15.00: Custom SO boleh Confirm dan reservarsi kapasitas; dapat menggantikan prioritas RO yang lebih dahulu Confirm.
- 2026-11-26 15.30: MO2 tambahan FINAL/LOCK.
- 2026-11-26 18.00: batas CDC → dapur transfer tambahan untuk kekurangan bahan; bahan lebih menetap sebagai buffer dapur.
- 2026-11-26 20.00: produksi mulai.
- 2026-11-27 05.00: dispatch S1.
Cut-off relatif ke slot perlu dimodelkan berbasis jadwal kebijakan; jangan hardcode seluruh delivery date/slot menggunakan contoh S1.

## Batas pekerjaan vs SOP luar addon
- Native Odoo MO manual yang diotorisasi dapat menambah stok Packing melalui transfer sah; tidak mengubah angka Published Planning atau MO1+MO2.
- Native Internal Transfer toko→Packing berdasarkan SOP dapat menambah stok Packing yang telah benar-benar diterima; bukan proses reservasi kapasitas SO.
- Keduanya INFORMASI OPERASIONAL, bukan permintaan membangun fitur custom atau pengecualian kapasitas.
- Accounting/HPP/closing dan POS negatif terpisah; jangan menggeser checkpoint Fase 2.

## Temuan audit source GitHub sebelum implementasi
1. `addons/ya_production_planning/models/planning.py`: `ya.production.planning` unik per (delivery_date, slot, kitchen_code), memiliki state draft/published. `ya.production.planning.line` unik (planning_id, product_id), `max_capacity`, `bom_id`, `uom_id`.
2. `addons/ya_store_ro/models/packing_batch.py`: `ya.packing.batch.line` memiliki UNIQUE(batch_id, planning_id, product_id) dan `mo_id` tunggal. `action_generate_selected_mo()` saat ini melepaskan semua baris dalam satu batch menjadi MO dan mengunci state `production_ok`. **Ini belum mendukung MO2.**
3. `addons/ya_store_ro/models/packing_lock.py` tersedia lock transaksi per delivery_date+slot: `lock_ro_slot`. Evaluasi reuse untuk reservasi SO dan release MO2; tidak boleh ada race antara Confirm, MO2, dan Packing.
4. `addons/ya_store_ro/models/packing_batch.py`: `ya.packing.batch.allocation` merekam alokasi RO frozen; harus dipisahkan sebagai planning snapshot versus alokasi DO final. Jangan menulis ulang audit/source RO.
5. `addons/ya_package_store_ro` sudah memiliki Paket expansion dan native PCK assembly. Integrasi SO Paket harus reuse mekanisme/source prioritas, bukan membuat BOM/routing baru.
6. `addons/ya_workflow_navigation/views/workflow_navigation_menus.xml`: menu sebelum produksi sudah ada; tempatkan Custom SO di sini melalui addon terpisah dengan dependency eksplisit. Native Sales menu jangan diganti.

## Gate implementasi
A. Read-only schema audit originally completed on `erp-yussyakmal-mrp-test` (sale.order, sale.order.line, published planning, material/packing links; no writes).
B. Pure capacity math regression: SO after RO, MO1 already full, incremental SO→MO2, BoM round-up overflow, Paket cross-kitchen, concurrency policy, SO cancel/amend and cut-off exception boundaries.
C. Isolated addon `ya_sale_production_capacity` SOURCE CREATED; NOT INSTALLED/TESTED. Mandatory slot on custom SO, backend route marker, confirm reservation; native SO unaffected.
D. Extend Pre Produksi/MO model minimally to record MO1 vs MO2, enforce aggregated cap, **without** weakening existing RO-only uniqueness/idempotence behavior.
E. Add Packing final allocation and SO delivery linking only after reservation/MO2 tests; native stock guard and actual receipt unchanged.
F. Fase 2 source → rollback Odoo shell ONLY on cloned `erp-yussyakmal-mrp-test-RO_SO` → GUI owner UAT; never touch live DB or original Fase 1 test DB.

## Pending policy details, not automatic assumptions
- Whether user may reduce/cancel Confirmed YA SO and reclaim capacity after MO1/MO2 lock; treat as not yet approved.
- For cases SO quantity demands more than physically finished stock (production failure), leave visible exception and use authorized native SOP, never invent stock.
- Cut-off timing for S2/S3 if different from S1; derive from approved schedule instead of guessing.

## Checkpoint source Fase 2 Stage 1 — 2026-11-25
- Feri actual `script/audit_fase2_sale_capacity_schema_readonly_ya.py` on `erp-yussyakmal-mrp-test`: `FASE2_READ_ONLY_SCHEMA_AUDIT_PASS`. Installed sale 19.0.1.2; sale_stock 19.0.1.0; mrp 19.0.2.0; ya_production_planning 19.0.1.4.0; ya_store_ro 19.0.8.1.3; ya_package_store_ro 19.0.1.3.0; ya_workflow_navigation 19.0.1.0.1. Published Planning 21, published lines 788, 6 distinct date+slot samples; 1 standard draft SO, zero confirmed SO. `sale.order.line.product_uom` absent on Odoo19; do not reference this removed/renamed field in implementation.
- **GitHub source-only created:** isolated addon `addons/ya_sale_production_capacity` version 19.0.1.0.0 and `script/check_fase2_ya_sale_stage1_source_ya.py`.
- Stage 1 behavior: native `sale.order` with readonly `ya_is_capacity_so` marker; only YA action sets marker default; date+slot mandatory & Published Planning exists, validated server-side on create/write. Dedicated menu YA Production Capacity → SEBELUM PRODUKSI → Sales Order filters YA orders. Native Sales SO unchanged.
- **Safety:** Custom YA SO `action_confirm` intentionally fail-closed until actual capacity reservation and package component validation exist; do not tell operator it is live. No MO2, reserving, changes to RO/Paket/PCK/stock, or posting. Not installed/GUI-tested at documentation time.
- Next gate Feri: git pull, run `python3 script/check_fase2_ya_sale_stage1_source_ya.py` and `python3 -m compileall -q addons/ya_sale_production_capacity`. Only on preflight PASS, verify backup/restore point of CLONE `erp-yussyakmal-mrp-test-RO_SO`, stage only new addon and install with `-i ya_sale_production_capacity` (not `-u`). Verify module state, form, mandatory schedule, standard SO remains normal; no test in primary DB. Next step implement reservation with atomic slot-level capacity and Paket component BoM; then unlock custom Confirm.
