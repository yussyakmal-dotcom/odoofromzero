# Catatan keberhasilan dan replikasi Odoo 19 YA

**Tanggal:** 20 November 2026. **Penanggung jawab server:** Feri.

## Identitas lingkungan

| Peran | Database | Kebijakan |
|---|---|---|
| Utama | `erp-yussyakmal` | Tidak boleh APPLY sebelum audit, backup, dan persetujuan. |
| Test | `erp-yussyakmal-integer-test` | Tempat uji modul dan master saat ini. |

Odoo 19 CE: `/opt/odoo19/venv/bin/python3`,
`/opt/odoo19/odoo/odoo-bin`, konfigurasi `/etc/odoo19.conf`,
service `odoo19.service`, user `odoo19`, addon di
`/opt/odoo19/custom-addons/`.

## Hasil yang sudah terbukti

| Komponen | Bukti dari sesi pengujian | Status |
|---|---|---|
| COA | 489 akun setelah tambahan 3 BOP | Impor terdahulu sukses |
| Kategori | 76 kategori, termasuk Paket dan Gas | Impor terdahulu sukses |
| Gudang | 30 warehouse, 90 operation type, audit issues 0 | Audit terdahulu sukses |
| Produk | 2.543 SKU dan 26 satuan dasar | Audit master terdahulu sukses |
| `ya_purchase_multi_uom` v19.0.1.3.0 | Uji tiga satuan pembelian dan harga pada PO | Lulus pada clone |
| `ya_integer_quantity` v19.0.1.0.0 | Uji validasi PO, stok, Sales, BoM, MO | Lulus sebagian besar alur ORM pada clone; POS masih terbatas |
| `ya_purchase_discount` v19.0.1.1.0 | 8 tes matematika, uji virtual, 5 tes ORM wizard | Lulus pada clone |
| Popup Discount | Mengikuti Sales: tombol, popup radio, Apply/Discard | Setelah perbaikan ACL, Feri menyatakan sudah bisa dibuka |

**Belum dinyatakan lulus untuk operasional:** PO sampai penerimaan dan
vendor bill, skenario kombinasi pajak, pembulatan diskon, koreksi kuantitas
atau harga setelah diskon, serta UI POS. Keberhasilan upgrade tidak
berarti pengujian end-to-end sudah selesai.

## Perbedaan test dan utama yang penting

1. **2.543 aturan pilihan satuan dasar** (`factor=1`) ditambahkan **di test**
   lewat `script/seed_uom_dasar_po_test_ya.py`. Skrip ini sengaja menolak
   database utama; jangan hapus pengaman tersebut.
2. **SKU 10840 Cabe Jengki** memiliki aturan test tambahan `1 Kg = 1.000
   Gram` dari `script/tambah_konversi_cabe_jengki_test_ya.py`.
3. **683 produk Bahan Baku** diaktifkan untuk pembelian **di test** melalui
   `script/aktifkan_pembelian_bahan_baku_test_ya.py`.
4. **608 aturan awal** pernah diimpor pada utama; jumlah saat ini di
   masing-masing database **wajib diperiksa**, tidak diasumsikan sama.
5. `ya_integer_quantity` dan `ya_purchase_discount` diuji pada clone;
   **belum ada bukti keduanya terpasang pada utama**.
6. Produk teknis `TIPS` dan `Down Payment (POS)` tidak termasuk master YA.
7. File staging produk dan sumber Excel konversi adalah **privat**. Jangan
   unggah sumbernya ke repository publik.

## Pemeriksaan READ-ONLY sebelum promosi

Di server, catat versi kode yang diuji:

```bash
cd ~/odoofromzero
git pull
git rev-parse HEAD
```

Jalankan audit yang sama dua kali, **tanpa APPLY**:

```bash
sudo -u odoo19 /opt/odoo19/venv/bin/python3 \
  /opt/odoo19/odoo/odoo-bin shell \
  -c /etc/odoo19.conf -d erp-yussyakmal-integer-test --no-http \
  < script/audit_kesiapan_promosi_ya.py \
  > audit_promosi_test.txt 2>&1

sudo -u odoo19 /opt/odoo19/venv/bin/python3 \
  /opt/odoo19/odoo/odoo-bin shell \
  -c /etc/odoo19.conf -d erp-yussyakmal --no-http \
  < script/audit_kesiapan_promosi_ya.py \
  > audit_promosi_utama.txt 2>&1
```

Bandingkan status/versi modul, 2.543 master SKU, aktif pembelian,
aturan per SKU dan satuan dasar, jumlah produk teknis, kategori,
warehouse, PO, stock.move, dan stok tersimpan. Simpan dua hasil audit
beserta SHA commit. Selisih **harus dijelaskan sebelum mutasi data**.

## Urutan promosi nanti (bukan izin APPLY)

1. Tuntaskan uji UI, pajak, pembatalan, stok, dan vendor bill pada clone.
2. Bekukan SHA commit yang lulus dan audit kedua database.
3. **Duplikasi/backup database utama terbaru** (termasuk filestore bila
   relevan). Clone lama bukan pengganti backup terbaru.
4. Siapkan migrasi **khusus database utama** dengan PREVIEW → APPLY,
   idempotent, pemeriksaan per-SKU, satu COMMIT dan rollback jika gagal.
5. Pastikan dependensi modul terpasang, lalu promosikan aturan dasar
   Multi-UoM dan aktivasi Bahan Baku sesuai hasil audit.
6. Deploy kode addon dari SHA yang sama, berurutan:
   `ya_purchase_multi_uom` → `ya_integer_quantity` →
   `ya_purchase_discount`.
7. Uji ulang PO tiga satuan, diskon %/Rp, akses wizard, perpajakan,
   penerimaan, dan vendor bill pada database utama sebelum operasional.
8. Simpan audit sesudah promosi dan keputusan go/no-go.

**Dokumen ini adalah rekaman konfigurasi dan rencana replikasi, bukan
perintah untuk langsung memasang modul di `erp-yussyakmal`.**
