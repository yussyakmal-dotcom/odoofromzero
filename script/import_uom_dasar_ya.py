"""Impor satuan dasar 2543 SKU YA dari XLSX privat untuk Odoo 19.

Default PREVIEW. UOM_DASAR_APPLY=YES untuk satu transaksi atomik.
Tidak membuat faktor konversi kemasan, tidak menyentuh stok atau harga.
"""

import os
import re
import traceback
import xml.etree.ElementTree as ET
from collections import Counter
from decimal import Decimal
from pathlib import Path
from zipfile import ZipFile


NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def read_xlsx(path):
    with ZipFile(path) as workbook:
        shared = []
        if "xl/sharedStrings.xml" in workbook.namelist():
            root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
            for item in root.findall(NS + "si"):
                shared.append("".join(t.text or "" for t in item.iter(NS + "t")))
        sheets = sorted(k for k in workbook.namelist()
                        if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", k))
        if not sheets:
            raise RuntimeError("Worksheet XLSX tidak ditemukan")
        root = ET.fromstring(workbook.read(sheets[0]))
        result = []
        for row in root.iter(NS + "row"):
            values = ["", "", ""]
            for cell in row.findall(NS + "c"):
                match = re.match(r"([A-Z]+)", cell.attrib.get("r", ""))
                if not match or match.group(1) not in ("A", "B", "C"):
                    continue
                idx = ord(match.group(1)) - ord("A")
                node = cell.find(NS + "v")
                if cell.attrib.get("t") == "inlineStr":
                    inline = cell.find(NS + "is")
                    value = "".join(t.text or "" for t in inline.iter(NS + "t")) if inline is not None else ""
                elif node is None:
                    value = ""
                elif cell.attrib.get("t") == "s":
                    value = shared[int(node.text)]
                else:
                    value = node.text or ""
                values[idx] = value.strip()
            if any(values):
                result.append(values)
        return result


def main():
    env19 = globals().get("env")
    if env19 is None or env19.cr.dbname != "erp-yussyakmal":
        raise RuntimeError("Database harus erp-yussyakmal")
    applying = os.environ.get("UOM_DASAR_APPLY") == "YES"
    source = os.environ.get("UOM_YA_FILE")
    if not source:
        raise RuntimeError("Set UOM_YA_FILE ke XLSX privat")
    rows = read_xlsx(Path(source))
    if not rows or rows[0] != ["Internal Reference", "Name", "Unit"]:
        raise RuntimeError("Header XLSX tidak sesuai")
    mappings = {}
    ignored = set()
    for sku, name, unit in rows[1:]:
        if not sku or not name or not unit or sku in mappings or sku in ignored:
            raise RuntimeError("Baris Excel memiliki SKU/nama/satuan kosong atau duplikat")
        if sku in ("DISC", "TIPS"):
            ignored.add(sku)
        else:
            mappings[sku] = (name, unit)
    if len(rows) != 2546 or len(mappings) != 2543 or ignored != {"DISC", "TIPS"}:
        raise RuntimeError("Sumber tidak sesuai 2543 produk + DISC/TIPS")

    companies = env19["res.company"].sudo().search([])
    if len(companies) != 1:
        raise RuntimeError("Diharapkan tepat satu perusahaan")
    Product = env19["product.template"].sudo().with_company(companies[0])
    Uom = env19["uom.uom"].sudo()
    products = Product.search([])
    by_sku = {p.default_code: p for p in products}
    if len(products) != 2543 or len(by_sku) != 2543 or set(by_sku) != set(mappings):
        raise RuntimeError("Daftar SKU database tidak identik dengan XLSX")
    for sku, (name, _) in mappings.items():
        if by_sku[sku].name.strip() != name:
            raise RuntimeError("Nama produk berbeda dari XLSX; hentikan APPLY")
    if env19["stock.move"].sudo().search_count([]) or env19["stock.quant"].sudo().search_count([("quantity", "!=", 0)]):
        raise RuntimeError("Sudah ada transaksi atau stok; perubahan UoM ditolak")
    if env19["purchase.order.line"].sudo().search_count([]):
        raise RuntimeError("Sudah ada baris PO; perubahan UoM ditolak")
    if "relative_factor" not in Uom._fields or "rounding" not in Uom._fields:
        raise RuntimeError("Struktur uom.uom tidak cocok dengan audit Odoo 19")

    unit_count = Counter(unit for _, unit in mappings.values())
    if len(unit_count) != 26:
        raise RuntimeError("Diharapkan 26 satuan dasar pada 2543 produk")
    names = {}
    # Audit termasuk UoM arsip: jangan membuat nama yang sudah ada tetapi nonaktif.
    for u in Uom.with_context(active_test=False).search([]):
        names.setdefault(u.name.strip().casefold(), []).append(u)
    existing = {}
    create_names = []
    for label in sorted(unit_count, key=str.casefold):
        same = names.get(label.casefold(), [])
        if len(same) > 1:
            raise RuntimeError("Nama UoM ambigu: " + label)
        if same:
            if not same[0].active:
                raise RuntimeError("UoM '%s' sudah ada tetapi nonaktif/arsip; tinjau terlebih dahulu" % label)
            existing[label] = same[0]
        else:
            create_names.append(label)

    print("DATABASE:", env19.cr.dbname)
    print("MODE:", "APPLY" if applying else "PREVIEW (tanpa perubahan)")
    print("SUMBER: XLSX privat UOM_YA_FILE")
    print("PRODUK:", len(products), "| SATUAN:", len(unit_count))
    print("UOM SUDAH ADA:", [(name, round(existing[name].rounding, 6)) for name in sorted(existing)])
    print("UOM BARU:", create_names)
    print("RENCANA: buat %s UoM dasar mandiri; perbarui 2543 product.template.uom_id" % len(create_names))
    print("TETAP: nama, SKU, kategori, harga jual, standard_price, status jual/beli, stock=0")
    print("ROUNDING: UoM baru=1.0; UoM bawaan Kg/ML tidak diubah")
    print("CATATAN: validasi quantity bilangan bulat pada PO/BoM adalah tahap modul berikutnya")
    if not applying:
        print("UOM_DASAR_PREVIEW_OK: database tidak diubah")
        return

    # Data minimal untuk pemeriksaan invariansi harga yang tidak ditampilkan di log.
    before = {sku: (Decimal(str(p.list_price)), Decimal(str(p.standard_price)),
                    p.sale_ok, p.purchase_ok, p.is_storable)
              for sku, p in by_sku.items()}
    try:
        mapped = dict(existing)
        for label in create_names:
            # Tidak ada relative_uom_id: UoM baru sebagai satuan dasar independen.
            mapped[label] = Uom.create({"name": label, "relative_factor": 1.0, "rounding": 1.0})
        for label in unit_count:
            group_ids = [by_sku[sku].id for sku, (_, u) in mappings.items() if u == label]
            Product.browse(group_ids).write({"uom_id": mapped[label].id})
        env19.flush_all()
        for sku, (name, unit) in mappings.items():
            p = by_sku[sku]
            if p.uom_id.id != mapped[unit].id or p.name.strip() != name:
                raise RuntimeError("Verifikasi SKU/UoM gagal")
            old = before[sku]
            now = (Decimal(str(p.list_price)), Decimal(str(p.standard_price)),
                   p.sale_ok, p.purchase_ok, p.is_storable)
            if old != now:
                raise RuntimeError("Harga atau kebijakan produk berubah saat migrasi UoM")
        if env19["stock.move"].sudo().search_count([]) or env19["stock.quant"].sudo().search_count([("quantity", "!=", 0)]):
            raise RuntimeError("Stok/transaksi berubah saat migrasi")
        env19.cr.commit()
        print("UOM_DASAR_IMPORT_SUCCESS: 2543 produk dipetakan ke 26 satuan dasar; %s UoM baru dibuat" % len(create_names))
        print("COMMIT selesai. Belum ada aturan konversi pembelian atau aktivasi transaksi")
    except Exception:
        env19.cr.rollback()
        print("UOM_DASAR_IMPORT_FAILED: semua perubahan dalam transaksi dibatalkan")
        traceback.print_exc()
        raise


main()
