# YA Multi-UoM Receiving — eksperimen khusus database test

**STATUS: BELUM TERUJI pada ORM Odoo 19. JANGAN install pada erp-yussyakmal utama.**

Fitur: tab `Penerimaan Multi-UoM YA` pada incoming picking. Tiap baris
memilih salah satu stock.move milik receipt, unit per-SKU dari aturan
`ya.purchase.uom.rule`, dan jumlah fisik integer. Beberapa baris boleh
memakai SKU/move sama dengan unit berbeda. Faktor dan label disalin saat
baris disimpan, agar laporan historis tidak berubah bila master berubah.

Tombol `Apply Satuan Fisik` menjumlahkan kuantitas dasar per move dan
mengisi `stock.move.quantity`. Tidak membuat stock move tambahan.
`Validate` akan memeriksa nilai tersebut telah sama dengan baris fisik,
dan operation type harus `create_backorder=never`. Kekurangan PO tidak
dibuatkan backorder; vendor bill mengikuti received quantity jika
`purchase_method=receive`.

**Batas versi pertama:**
- Hanya incoming receipts terhubung PO; belum untuk transfer internal, retur,
  POS, atau manufacturing.
- Kuantitas penerimaan di atas demand ditolak, tidak otomatis membuat
  penambahan PO.
- Unit berasal dari aturan SKU. Jika receipt memiliki dua move untuk SKU sama,
  pilih move tujuan yang benar pada masing-masing entri fisik.
- Tidak otomatis menekan Validate; kontrol tetap di tangan petugas.
- Sebelum menjalankan uji dengan record nyata, lakukan unit test, compile,
  upgrade modul di test, serta rollback ORM integration test terlebih dahulu.
- Pending: tes sinkronisasi `stock.move.quantity` dengan move lines dan
  efek `picked` pada Odoo 19, partial receipt, no-backorder, vendor bill.
  Jangan anggap berhasil hanya karena install exit 0.

## Pengujian awal

```bash
cd ~/odoofromzero
python3 -m unittest discover -s addons/ya_multi_uom_receiving/tests -v
sudo /opt/odoo19/venv/bin/python3 -m compileall -q addons/ya_multi_uom_receiving
```

Setelah lulus, pasang file addon ke custom-addons lalu install
`-i ya_multi_uom_receiving` **hanya** pada
`erp-yussyakmal-integer-test`, kemudian restart service.
Jangan ubah konfigurasi backorder global otomatis: untuk CDC incoming
set `Never` hanya setelah uji dan persetujuan.
