# CHECKPOINT — 2026-Nov-23 — Rakit Paket di Packing (DITUNDA, TIDAK DIHAPUS)

## Keputusan owner — wajib dibaca saat melanjutkan ODOO FROM ZERO

Sesudah MO Done, barang jadi dipindahkan dari gudang dapur ke PCK/Stock melalui native Internal Transfer satu langkah (tanpa serah-terima fisik terpisah karena satu lokasi).

**Prioritas pengerjaan saat ini:**
1. Selesaikan pembuktian GUI Produk Jadi → Packing di database test `erp-yussyakmal-mrp-test`.
2. Gunakan alokasi RO toko yang SUDAH dihitung sebelum produksi untuk menyiapkan Delivery Order / Internal Transfer Packing → Toko (hindari input ulang).
3. Selesaikan flow toko menerima barang, stok toko bertambah sesuai transaksi Odoo.
4. **SETELAH FLOW PENERIMAAN TOKO SELESAI, KEMBALI KERJAKAN FLOW \"RAKIT PAKET DI PACKING\".** Ini adalah pekerjaan tertunda yang harus diingat, bukan dibatalkan.

## Batas scope sekarang
- **JANGAN** memasukkan implementasi perakitan paket sebagai penghalang alokasi RO → DO Toko → penerimaan toko.
- **JANGAN** menganggap SKU paket sudah memiliki stok atau otomatis dapat didistribusikan hanya karena terdaftar dalam RO; perlakuan sementara terhadap item paket perlu dipastikan sebelum DO, jangan mengarang stok.
- Ketika tiba gilirannya, rancang aturan SKU komponen, SKU paket hasil rakitan, konsumsi komponen, pembentukan stok barang paket, traceability dan hubungan dengan alokasi RO. Keputusan rinci belum dibuat owner.
- Untuk sementara, hanya distribusikan SKU yang stoknya memang tersedia di Packing dan memenuhi alur yang disetujui.
- Jangan mengganti sistem dengan alur rumit; optimalkan jumlah klik operator dan gunakan native stock transaction + SOP.

## Status pembuktian
- E2E rollback `script/test_finished_packing_transfer_rollback_ya.py` untuk `Packing 2026-Nov-25 S3`: 12 SKU dipindahkan, 1 picking, WIP 11076 dikecualikan, stock deltas PASS, double-click PASS, rollback PASS berdasarkan log Feri.
- Pengujian klik GUI / transfer permanen **belum dikonfirmasi**.
- DO dan penerimaan toko **belum diimplementasikan atau diuji pada checkpoint ini**.

## Update hasil user test — 2026-Nov-23
Owner melaporkan: **"sudah di test RO TOKO ---- > STOCK TOKO good"**.
Status: alur RO Toko sampai stok toko dinyatakan **lulus uji operasional oleh owner**. Ini adalah laporan uji pengguna, bukan audit otomatis tambahan; catatan tidak memuat bukti nomor dokumen/detail kuantitas tiap tahap.

**Tindak lanjut:** Buka kembali pekerjaan yang sebelumnya sengaja ditunda, **Rakit Paket di Packing**. Sebelum membuat kode, petakan SKU paket, komponen per paket, trigger perakitan, lokasi stok input-output, pencatatan qty aktual dan kaitan dengan RO/DO. Jangan mengubah workflow RO→stok toko yang sudah lolos tanpa alasan dan pengujian regresi. Gunakan addon terpisah dan DB test `erp-yussyakmal-mrp-test`.
