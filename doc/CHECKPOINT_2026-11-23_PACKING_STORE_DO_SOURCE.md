# ODOO FROM ZERO — Packing → DO Toko → Penerimaan Toko

Tanggal: 2026-Nov-23. **SOURCE-ONLY; BELUM TERINSTAL ATAU LULUS UJI ODOO.**

## Owner-approved business scope
- DO per toko berasal dari alokasi RO yang sudah dibuat dan dikunci di Pre Produksi; tidak input ulang.
- Pengiriman dari PCK/Stock → Inter-warehouse transit harus terpisah dari penerimaan di gudang toko.
- Stok toko baru bertambah sesudah validasi penerimaan. Dapur → Packing tetap mutasi satu langkah karena satu lokasi fisik.
- Tidak ada stok minus atau pengiriman SKU kosong fiktif.
- Rakit Paket di Packing **ditunda sampai sesudah penerimaan toko selesai**.

## Bukti audit server
- `PCK/Stock`, `Inter-warehouse transit`, `T_MET/Stock`, `T_KD/Stock`, `T_SD/Stock` ada dan aktif. Native type PCK outgoing dan toko incoming tersedia, seperti rule pair PCK→Transit→Toko. Audit `script/audit_packing_store_receipt_route_readonly_ya.py` menghasilkan `READ_ONLY_PACKING_STORE_RECEIPT_ROUTE_OK`.
- Batch 2026-Nov-25 S3 belum punya FG handoff linked; batch 2026-Nov-27 S1 punya ASN dan GRG transfers Done.
- SKU 10031 (MO cancel) dan 11076 (WIP yang sengaja tidak dikirim ke Packing) masih ada pada alokasi RO tetapi stok PCK 0. **Jangan menganggap keduanya terkirim; perlu penanganan eksplisit menurut SOP.**

## Modul baru
`addons/ya_packing_store_delivery`
- Menambah menu `SESUDAH PRODUKSI → DO Toko` dan tombol `Generate DO Toko` pada batch form (menu membuka LIST dulu).
- Setiap RO batch menghasilkan satu native `stock.picking` outgoing per toko. Demand berasal dari `ya.packing.batch.allocation.qty_allocated`; Qty otomatis hanya bila tersedia penuh dan SKU tidak memerlukan lot/serial. Baris demand yang kosong stoknya tetap ada dengan Qty=0 **bukan otomatis dikirim**.
- Membuat DO **tidak** memindahkan stok. Saat packing memvalidasi pengiriman nyata, native stock moves beralih PCK → transit. Setelah dispatch benar-benar Done, modul membuat native incoming receipt dari Qty aktual dikirim, per toko. Store operator memvalidasi receipt transit → toko saat menerima barang.
- Menerapkan check_qty native untuk SKU tidak kosong, Qty <= Demand, stok PCK cukup, incoming Qty <= shipped dan <= transit fisik; no-backorder untuk dokumen linked. Tidak auto-validate di tombol Generate; do not short-circuit native inventory accounting.
- Pencegahan klik dua kali pada batch dan unique SQL (batch, store, stage). Scope DB test `erp-yussyakmal-mrp-test`.

## Pengujian berikutnya — wajib sebelum menganggap lulus
1. GUI backup database test.
2. `git pull`, `python3 script/check_ya_packing_store_delivery_source_readonly.py`.
3. Salin addon custom ke active path, instal di **test only** lalu restart aman.
4. `sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test --no-http < script/test_ya_store_do_generate_rollback.py`.
5. Periksa seluruh result; **jangan validasi DO GUI** sampai hasil lulus dan penanganan SKU 10031/11076 selesai/disepakati.
6. Uji pengiriman→penerimaan dengan rollback dan state + stock deltas secara tersendiri sebelum penggunaan riil.

## Perlu perhatian
- `10031` dan `11076` Qty nol pada DO. Native Odoo dapat mengisi Qty nol otomatis pada Validate; custom guard mencegah pengiriman fiktif. Jika benar-benar tidak dikirim, baris harus diproses mengikuti SOP dengan jejak alokasi RO tetap ada, bukan membuat stok palsu.
- Pemakaian stock route internal Odoo tidak membuktikan semua rule otomatis memicu. Modul sengaja membuat dokumen native sendiri tanpa memanggil procurement trigger.
- Belum ada implementasi rakit paket.

## Tambahan keputusan — Picking List sebelum pengiriman
- Setelah native DO per toko dibuat dari alokasi RO, petugas Packing **harus dapat mencetak Picking List** sebelum stok dipindahkan ke transit.
- Tombol `Cetak Picking List` pada DO Packing membuka laporan QWeb PDF `report_ya_store_picking_list`, memuat batch/slot, toko, SKU, Qty Alokasi RO, Qty Kirim, alasan tidak dikirim, checklist fisik, dan tanda petugas.
- Laporan adalah instruksi penyiapan barang; **bukan** bukti stok sudah berpindah atau bukti toko menerima barang.
- Jika Qty Kirim 0 karena MO Cancel/tidak tersedia, SKU tetap terlihat beserta alasan operator; ini tidak boleh menjadi pengiriman fiktif.
- Implementasi source GitHub **belum diuji instalasi, render PDF, maupun klik UI**. Sebelum dipakai operator, wajib pemeriksaan source, instalasi database test, cetak laporan, verifikasi konten dan stok tidak berubah.
