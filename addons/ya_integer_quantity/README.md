# YA Integer Quantity Policy (Odoo 19)

Tahap awal: validasi **backend** seluruh nilai kuantitas operasional dalam
bilangan bulat tanpa mengganti tipe penyimpanan Float atau memodifikasi
perhitungan harga/akuntansi. Nilai negatif bulat diperbolehkan (refund POS),
nilai pecahan ditolak. Field internal Odoo yang dihitung otomatis **tidak
diubah definisi/precision-nya**.

Model: purchase.order.line, stock.move, stock.move.line, stock.quant
(inventory_quantity), stock.scrap, sale.order.line, pos.order.line,
mrp.production, mrp.bom.line.

`views/integer_quantity_views.xml` menambahkan format tampilan tanpa digit
pecahan pada sejumlah form/list inti. **BELUM LENGKAP:** view embedded lain,
widget khusus Stock Adjustment, dan pembatasan input di aplikasi POS browser
masih membutuhkan pemeriksaan UI. Odoo bisa membulatkan tampilan; jangan
menganggap format ini sendiri menjamin penolakan input pecahan. Validator
backend adalah pengaman penyimpanan utamanya.
Jangan menganggap instalasi addon ini sudah menyelesaikan seluruh SOP.

Risiko: Odoo atau modul pihak ketiga dapat menghasilkan kuantitas pecahan
secara otomatis pada alur tertentu. Uji dahulu pada database duplikat dengan
PO, transfer, scrap, SO, MO, BoM, dan retur POS sebelum mengaktifkan operasi.

Skrip `script/test_integer_quantity_ya.py` menguji fungsi validasi dengan
record in-memory dan tidak menyimpan transaksi.
