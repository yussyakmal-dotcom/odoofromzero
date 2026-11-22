# YA Production Planning — Odoo 19 Community

**Status checkpoint 22 November 2026:** addon **installed** di `erp-yussyakmal-mrp-test` menurut hasil pemeriksaan Odoo shell; flow Upload Planning telah dicoba di GUI dan dinyatakan sesuai oleh pengguna. **Belum dipromosikan ke database utama**. Kosmetik UI pending. RO toko belum ada.

**Dokumen wajib sesi baru:**
- [Handover operasional](../../doc/HANDOVER_ODOO_FROM_ZERO.md)
- [Status MRP](../../doc/STATUS_PENGEMBANGAN_MRP.md)
- [SKILL praktis deploy/install/upgrade](../../doc/SKILL_ODOO19_ADDON_WORKFLOW.md)

## Tujuan dan input

Upload **XLSX multi-sheet setiap jadwal**, **bukan** master capacity template permanen.

- `info` = `NO | Sheet | Code Dapur`.
- Setiap dapur = `DAPUR | Product | Max | Unit`.
- `Product` = `[Reference] Nama Produk`; SOP tim menentukan SKU yang masuk sheet.
- Max adalah **kapasitas maksimal per SKU/jadwal**, bukan qty BoM atau qty pesanan RO. Max 0 tidak boleh muncul sebagai opsi pesanan toko ketika RO dibuat.
- `Unit` berasal dari satuan hasil di **BoM Header** untuk produk dan dapur/warehouse sesuai; tidak harus sama dengan stock UoM produk. Tidak membuat konversi ke stok/MO otomatis.
- Sheet `info` pada contoh yang disetujui: 10 dapur; Premik, Dahlia 5, Trial bukan dapur produksi barang jadi reguler; Packing adalah perakitan paket, bukan salah satu 10 sheet tersebut.

## Workflow GUI terbaru

**Menu `Upload Planning` → daftar Planning (Draft dan Published) → tombol toolbar `Upload Baru` → XLSX wizard → Validate & Preview → Save Draft.**

- S1 = 05.00 WIB; S2 = 09.00 WIB; S3 = 11.00 WIB.
- Upload satu tanggal kirim + slot; identitas masing-masing dokumen **tanggal + slot + kode dapur**.
- Jika belum ada: **CREATE Draft**.
- Jika sudah Draft: **REPLACE** SKU dan Max untuk dapur itu.
- Jika Published: **SKIP**, tetap utuh. Sheet/dapur yang tak ada di workbook tidak diubah.
- Preview menunjukkan CREATE/REPLACE/SKIP. Save Draft menjalankan semua write dalam satu transaksi Odoo dan memberi notifikasi hasil.
- Admin Produksi/operator Manufacturing User boleh mengedit **Max** ketika Draft; identity SKU, Reference, UoM tetap readonly; Published readonly.
- **Publish This Kitchen** hanya untuk satu dokumen dapur, oleh Manufacturing Manager. Dapur lain tetap Draft.
- Daftar Planning menampilkan **Draft + Published**, tersedia filter untuk masing-masing; **tidak** membuka wizard langsung dari menu Upload Planning.
- **Perbaikan kosmetik UI/UX pending** berdasarkan keputusan pengguna setelah flow disetujui.

## Status pengujian: bedakan bukti dengan rencana

**Terbukti:** `openpyxl 3.1.2` di Odoo venv, source preflight PASS, 10 kode dapur cocok, manifest dan addons_path terverifikasi, addon installed dan keempat model terdaftar; pengguna memperlihatkan Draft per dapur, daftar SKU, dan notifikasi Created Draft dari upload file. Pengguna menyatakan flow akhir sudah sesuai keinginan.

**Belum dinyatakan lulus menyeluruh:** otomatisasi pengujian create/replace/skip untuk kasus Published + Draft campuran, semua kombinasi permission operator, publish per dapur pada seluruh skenario, integrasi RO toko, reservasi kapasitas SO, MO/stock move, costing/accounting end-to-end. Jangan menganggap “Published” otomatis menghasilkan RO.

**Masalah lama dan tindakan:** jika view `line_row` menghasilkan OwlError undefined, cek deploy field Python/upgrade/restart service; kalau Save Draft memunculkan Created Draft lalu JavaScript `reading 'map'`, data mungkin tersimpan dan error terjadi pada navigasi action `views`. Perbaikan itu sudah ada di kode; lihat skill untuk prosedur.

## Cara deploy versi berikutnya

Lihat [SKILL_ODOO19_ADDON_WORKFLOW.md](../../doc/SKILL_ODOO19_ADDON_WORKFLOW.md), jangan melakukan install ulang secara membabi buta. Ringkasnya:

```bash
cd ~/odoofromzero
git pull
python3 script/check_production_planning_source_readonly_ya.py
sudo cp -a addons/ya_production_planning/. /opt/odoo19/custom-addons/ya_production_planning/
sudo chown -R odoo19:odoo19 /opt/odoo19/custom-addons/ya_production_planning
# Jika model/XML/ACL berubah: backup GUI dahulu, lalu upgrade hanya DB MRP test
sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin \
  -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test \
  -u ya_production_planning --stop-after-init --no-http
echo "UPGRADE_EXIT_CODE=$?"
# Hanya jika EXIT_CODE=0:
sudo systemctl restart odoo19
sudo systemctl is-active odoo19
```

**Next feature:** RO toko yang mengambil SKU dari **Published Planning dengan Max > 0**, satu RO per toko + dapur + tanggal pengiriman + slot, Qty Pesan oleh toko melalui Excel. Jangan mengulang audit BoM 955 hanya untuk memulai RO.
