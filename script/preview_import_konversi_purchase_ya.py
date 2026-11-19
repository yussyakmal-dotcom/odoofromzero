"""PREVIEW read-only konversi pembelian YA dari Excel review PRIVAT.

Hanya baris 'KANDIDAT PURCHASE' dan 'MENUNGGU KOREKSI UOM' yang menjadi
kandidat. Tidak ada operasi APPLY di skrip ini: desain target ORM Multi-UoM
harus diperiksa dan diuji sebelum importer penulisan dibuat.

UOM_KONVERSI_FILE menunjuk XLSX privat di luar repository publik.
"""

import os
import re
import xml.etree.ElementTree as ET
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zipfile import ZipFile


NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
COLS = ("Baris Asli", "SKU", "Nama Resmi (Dipakai)", "Kategori Produk",
        "Nama Sebelumnya", "Satuan Asal", "Faktor", "Satuan Tujuan File",
        "Satuan Dasar Master", "Status", "Nama Cocok", "Catatan")
ACCEPTED = {"KANDIDAT PURCHASE", "MENUNGGU KOREKSI UOM"}


def get_rows(path):
    with ZipFile(path) as workbook:
        shared = []
        if "xl/sharedStrings.xml" in workbook.namelist():
            root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in si.iter(NS + "t"))
                      for si in root.findall(NS + "si")]
        sheets = sorted(k for k in workbook.namelist()
                        if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", k))
        if len(sheets) < 2:
            raise RuntimeError("Excel review harus memiliki sheet Ringkasan dan Seluruh Baris")
        result = []
        # Sheet kedua adalah 'Seluruh 754 Baris' dari workbook review saat ini.
        root = ET.fromstring(workbook.read(sheets[1]))
        for row in root.iter(NS + "row"):
            values = [""] * len(COLS)
            for cell in row.findall(NS + "c"):
                m = re.match(r"([A-Z]+)", cell.attrib.get("r", ""))
                if not m:
                    continue
                index = 0
                for ch in m.group(1):
                    index = index * 26 + ord(ch) - ord("A") + 1
                index -= 1
                if index >= len(COLS):
                    continue
                v = cell.find(NS + "v")
                if cell.attrib.get("t") == "inlineStr":
                    inline = cell.find(NS + "is")
                    value = "".join(t.text or "" for t in inline.iter(NS + "t")) if inline is not None else ""
                elif v is None:
                    value = ""
                elif cell.attrib.get("t") == "s":
                    value = shared[int(v.text)]
                else:
                    value = v.text or ""
                values[index] = value.strip()
            if any(values):
                result.append(values)
        return result


def category_path(cat):
    names = []
    while cat:
        names.append(cat.name)
        cat = cat.parent_id
    return " / ".join(reversed(names))


def main():
    e = globals().get("env")
    if e is None or e.cr.dbname != "erp-yussyakmal":
        raise RuntimeError("Database harus erp-yussyakmal")
    source = os.environ.get("UOM_KONVERSI_FILE")
    if not source:
        raise RuntimeError("Set UOM_KONVERSI_FILE ke Excel review privat")
    rows = get_rows(Path(source))
    if not rows or tuple(rows[0]) != COLS:
        raise RuntimeError("Header Excel review tidak cocok")

    Products = e["product.template"].sudo()
    Uom = e["uom.uom"].sudo().with_context(active_test=False)
    products = {p.default_code: p for p in Products.search([])}
    if len(products) != 2543:
        raise RuntimeError("Master produk bukan 2543 SKU unik")
    if e["stock.move"].sudo().search_count([]) or e["purchase.order.line"].sudo().search_count([]):
        raise RuntimeError("Sudah ada stock.move atau baris PO; evaluasi konversi ulang")

    candidates = []
    ignored = Counter()
    seen_pairs = set()
    issues = []
    for line_no, record in enumerate(rows[1:], 2):
        _, sku, name, category, _, purchase_uom, factor, source_target, base_uom, status, _, _ = record
        if not sku or sku not in products:
            issues.append("SKU kosong/tidak dikenal pada baris Excel %s" % line_no)
            continue
        if status not in ACCEPTED:
            ignored[status] += 1
            continue
        product = products[sku]
        if product.name.strip() != name or category_path(product.categ_id) != category:
            issues.append("Nama/kategori SKU tidak cocok pada baris %s" % line_no)
        if product.uom_id.name.casefold() != base_uom.casefold():
            issues.append("Satuan dasar SKU tidak cocok pada baris %s" % line_no)
        if source_target.casefold() != base_uom.casefold():
            issues.append("Satuan tujuan tidak sama dengan dasar pada baris %s" % line_no)
        try:
            ratio = Decimal(factor)
            if not ratio.is_finite() or ratio <= 0 or ratio != ratio.to_integral_value():
                issues.append("Faktor harus bilangan bulat positif pada baris %s" % line_no)
        except (InvalidOperation, TypeError):
            issues.append("Faktor tidak valid pada baris %s" % line_no)
        key = (sku, purchase_uom.casefold())
        if key in seen_pairs:
            issues.append("SKU+satuan pembelian duplikat pada baris %s" % line_no)
        seen_pairs.add(key)
        candidates.append((sku, purchase_uom, base_uom))

    if len(rows) - 1 != 754 or len(candidates) != 608:
        issues.append("Jumlah Excel/kandidat berubah; perlu audit klasifikasi ulang")
    existing_units = {u.name.casefold() for u in Uom.search([])}
    purchase_counts = Counter(u for _, u, _ in candidates)
    missing_units = sorted({u for u in purchase_counts if u.casefold() not in existing_units})
    print("DATABASE:", e.cr.dbname)
    print("MODE: PREVIEW READ-ONLY; TIDAK ADA APPLY")
    print("EXCEL: %s baris | KANDIDAT: %s | SKU UNIK: %s" %
          (len(rows) - 1, len(candidates), len(set(x[0] for x in candidates))))
    print("DITAHAN BERDASARKAN STATUS:", dict(sorted(ignored.items())))
    print("SATUAN PEMBELIAN:", dict(sorted(purchase_counts.items())))
    print("LABEL UOM PEMBELIAN BELUM ADA DI ODOO:", missing_units)
    for model_name in ("product.uom", "product.supplierinfo", "purchase.order.line", "uom.uom"):
        if model_name not in e.registry.models:
            print("MODEL:", model_name, "TIDAK TERSEDIA")
            continue
        Model = e[model_name]
        print("MODEL:", model_name, "| field penting:", [
            (f, Model._fields[f].type,
             Model._fields[f].comodel_name if Model._fields[f].type in ("many2one", "one2many", "many2many") else "")
            for f in ("product_id", "product_tmpl_id", "uom_id", "product_uom_id",
                      "relative_uom_id", "relative_factor", "name", "price")
            if f in Model._fields])
    print("MASALAH VALIDASI:", len(issues))
    for problem in issues[:30]:
        print("  -", problem)
    if issues:
        print("KONVERSI_PREVIEW_BLOCKED: database tidak diubah")
        raise RuntimeError("Ada masalah validasi; periksa hasil audit")
    print("KONVERSI_PREVIEW_OK: 608 kandidat konsisten; belum dibuat sebagai aturan per-SKU")
    print("TAHAP BERIKUT: tentukan model penyimpanan konversi dan integrasi PO/penerimaan")


main()
