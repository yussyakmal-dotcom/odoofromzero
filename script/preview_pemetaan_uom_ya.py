"""PREVIEW read-only pemetaan satuan dasar 2.543 SKU dari XLSX privat.

Odoo shell 19, database erp-yussyakmal. Tidak membuat/mengubah UoM atau produk.
Set UOM_YA_FILE=/opt/odoo19/import_private/PRODUCT_UOM_SOURCE_PRIVATE.xlsx.
Hasil hanya berisi ringkasan nama satuan dan jumlah, tanpa daftar SKU.
"""

import os
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from zipfile import ZipFile


XML_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def read_xlsx(path):
    """Baca tiga kolom worksheet pertama XLSX, tanpa dependensi openpyxl."""
    with ZipFile(path) as workbook:
        shared = []
        if "xl/sharedStrings.xml" in workbook.namelist():
            root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
            for item in root.findall(XML_NS + "si"):
                shared.append("".join(t.text or "" for t in item.iter(XML_NS + "t")))
        sheets = sorted(k for k in workbook.namelist()
                        if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", k))
        if not sheets:
            raise RuntimeError("XLSX tidak memiliki worksheet")
        root = ET.fromstring(workbook.read(sheets[0]))
        output = []
        for row in root.iter(XML_NS + "row"):
            cells = ["", "", ""]
            for cell in row.findall(XML_NS + "c"):
                address = cell.attrib.get("r", "")
                match = re.match(r"([A-Z]+)", address)
                if not match or match.group(1) not in ("A", "B", "C"):
                    continue
                pos = ord(match.group(1)) - ord("A")
                value_node = cell.find(XML_NS + "v")
                if cell.attrib.get("t") == "inlineStr":
                    inline = cell.find(XML_NS + "is")
                    value = "".join(t.text or "" for t in inline.iter(XML_NS + "t")) if inline is not None else ""
                elif value_node is None:
                    value = ""
                elif cell.attrib.get("t") == "s":
                    value = shared[int(value_node.text)]
                else:
                    value = value_node.text or ""
                cells[pos] = value.strip()
            if any(cells):
                output.append(cells)
        return output


def main():
    odoo_env = globals().get("env")
    if odoo_env is None or odoo_env.cr.dbname != "erp-yussyakmal":
        raise RuntimeError("Jalankan di database erp-yussyakmal")
    path = os.environ.get("UOM_YA_FILE")
    if not path:
        raise RuntimeError("Set UOM_YA_FILE ke lokasi XLSX privat")
    rows = read_xlsx(Path(path))
    if not rows or rows[0] != ["Internal Reference", "Name", "Unit"]:
        raise RuntimeError("Header XLSX harus Internal Reference, Name, Unit")

    Product = odoo_env["product.template"].sudo()
    Uom = odoo_env["uom.uom"].sudo()
    db_products = Product.search([])
    by_sku = {}
    for p in db_products:
        if p.default_code in by_sku:
            raise RuntimeError("SKU duplikat di database")
        by_sku[p.default_code] = p

    source = {}
    excluded = set()
    for row in rows[1:]:
        sku, name, unit = row
        if not sku or not name or not unit or sku in source or sku in excluded:
            raise RuntimeError("SKU, nama atau satuan kosong/duplikat di XLSX")
        if sku in ("DISC", "TIPS"):
            excluded.add(sku)
        else:
            source[sku] = (name, unit)
    if set(source) != set(by_sku) or len(source) != 2543 or excluded != {"DISC", "TIPS"}:
        raise RuntimeError("SKU sumber dan database berbeda, atau DISC/TIPS belum benar")
    mismatched_names = sum(1 for sku, (name, _) in source.items()
                           if by_sku[sku].name.strip() != name)
    if mismatched_names:
        raise RuntimeError("Ada %s nama SKU berbeda dari database" % mismatched_names)
    if odoo_env["stock.move"].sudo().search_count([]):
        raise RuntimeError("Sudah ada stock.move; perubahan UoM harus dievaluasi ulang")
    if odoo_env["stock.quant"].sudo().search_count([("quantity", "!=", 0)]):
        raise RuntimeError("Sudah ada stok; perubahan UoM harus dievaluasi ulang")

    source_units = Counter(unit for _, unit in source.values())
    existing = Uom.search([])
    lookup = {}
    for uom in existing:
        lookup.setdefault(uom.name.strip().casefold(), []).append(uom)

    print("DATABASE:", odoo_env.cr.dbname)
    print("MODE: PREVIEW READ-ONLY; TIDAK ADA APPLY DALAM SKRIP INI")
    print("SUMBER: XLSX privat UOM_YA_FILE")
    print("EXCEL: %s baris | %s SKU produk | %s SKU teknis dikecualikan" %
          (len(rows) - 1, len(source), len(excluded)))
    print("UNIT: %s jenis pada 2543 produk; 1 jenis tambahan hanya untuk DISC/TIPS" % len(source_units))
    print("UOM ODOO SAAT INI:", len(existing))
    print("PEMETAAN:")
    missing = []
    ambiguous = []
    for label, count in sorted(source_units.items(), key=lambda pair: pair[0].casefold()):
        candidates = lookup.get(label.casefold(), [])
        if len(candidates) == 1:
            uom = candidates[0]
            print("  %s | %s SKU | SUDAH ADA id=%s rounding=%s" %
                  (label, count, uom.id, uom.rounding))
        elif not candidates:
            missing.append(label)
            print("  %s | %s SKU | PERLU UOM BARU (belum dibuat)" % (label, count))
        else:
            ambiguous.append(label)
            print("  %s | %s SKU | AMBIGU: %s UoM senama" % (label, count, len(candidates)))
    print("RINGKASAN: tersedia=%s | perlu baru=%s | ambigu=%s" %
          (len(source_units) - len(missing) - len(ambiguous), len(missing), len(ambiguous)))
    print("CATATAN: semua satuan pada Excel adalah satuan dasar SKU, bukan otomatis satuan kemasan")
    print("CATATAN: harga biaya dan stok tidak diubah; rounding integer akan ditinjau saat APPLY")
    print("UOM_MAPPING_PREVIEW_OK: database tidak diubah")


main()
