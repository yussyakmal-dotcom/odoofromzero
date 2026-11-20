# YA Integer Quantity Policy (Odoo 19)

Tahap awal: validasi **backend** seluruh nilai kuantitas operasional dalam
bilangan bulat tanpa mengganti tipe penyimpanan Float atau memodifikasi
perhitungan harga/akuntansi. Nilai negatif bulat diperbolehkan (refund POS),
nilai pecahan ditolak. Field internal Odoo yang dihitung otomatis **tidak
diubah definisi/precision-nya**.

Model: purchase.order.line, stock.move, stock.move.line, stock.quant
(inventory_quantity), stock.scrap, sale.order.line, pos.order.line,
mrp.production, mrp.bom.line.

**BELUM LENGKAP:** tampilan integer semua form dan pembatas input pada
aplikasi POS di browser membutuhkan tahap terpisah dan pengujian UI Odoo 19.
Jangan menganggap instalasi addon ini sudah menyelesaikan seluruh SOP.

Risiko: Odoo atau modul pihak ketiga dapat menghasilkan kuantitas pecahan
secara otomatis pada alur tertentu. Uji dahulu pada database duplikat dengan
PO, transfer, scrap, SO, MO, BoM, dan retur POS sebelum mengaktifkan operasi.

Skrip `script/test_integer_quantity_ya.py` menguji fungsi validasi dengan
record in-memory dan tidak menyimpan transaksi.
