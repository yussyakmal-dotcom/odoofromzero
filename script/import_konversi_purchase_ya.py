"""Impor aturan Multi-UoM purchasing YA dari XLSX PRIVAT.

Jalankan melalui `odoo-bin shell` pada erp-yussyakmal. Default PREVIEW.
APPLY hanya bila UOM_KONVERSI_APPLY=YES; seluruh operasi satu COMMIT.
Tidak mengaktifkan purchase_ok, tidak membuat PO, stock move, atau UoM global.
"""

import os
import re
import xml.etree.ElementTree as ET
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zipfile import ZipFile


NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
HEADERS = ("Baris Asli", "SKU", "Nama Resmi (Dipakai)", "Kategori Produk",
           "Nama Sebelumnya", "Satuan Asal", "Faktor", "Satuan Tujuan File",
           "Satuan Dasar Master", "Status", "Nama Cocok", "Catatan")
ACCEPTED = {"KANDIDAT PURCHASE", "MENUNGGU KOREKSI UOM"}


def spreadsheet_rows(path):
    with ZipFile(path) as archive:
        strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            strings = ["".join(t.text or "" for t in item.iter(NS + "t"))
                       for item in root.findall(NS + "si")]
        sheets = sorted(name for name in archive.namelist()
                        if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", name))
        if len(sheets) < 2:
            raise RuntimeError("XLSX harus memiliki sheet Ringkasan dan Seluruh Baris")
        output = []
        for row in ET.fromstring(archive.read(sheets[1])).iter(NS + "row"):
            values = [""] * len(HEADERS)
            for cell in row.findall(NS + "c"):
                match = re.match(r"([A-Z]+)", cell.attrib.get("r", ""))
                if not match:
                    continue
                pos = 0
                for letter in match.group(1):
                    pos = pos * 26 + ord(letter) - ord("A") + 1
                pos -= 1
                if pos >= len(values):
                    continue
                raw = cell.find(NS + "v")
                if cell.attrib.get("t") == "inlineStr":
                    inline = cell.find(NS + "is")
                    value = ("".join(t.text or "" for t in inline.iter(NS + "t"))
                             if inline is not None else "")
                elif raw is None:
                    value = ""
                elif cell.attrib.get("t") == "s":
                    value = strings[int(raw.text)]
                else:
                    value = raw.text or ""
                values[pos] = value.strip()
            if any(values):
                output.append(values)
        return output


def category_path(category):
    names = []
    while category:
        names.append(category.name)
        category = category.parent_id
    return " / ".join(reversed(names))


def main():
    e = globals().get("env")
    if e is None or e.cr.dbname != "erp-yussyakmal":
        raise RuntimeError("Database wajib erp-yussyakmal")
    apply = os.environ.get("UOM_KONVERSI_APPLY") == "YES"
    source = os.environ.get("UOM_KONVERSI_FILE")
    if not source:
        raise RuntimeError("UOM_KONVERSI_FILE harus menunjuk XLSX privat")
    if "ya.purchase.uom.rule" not in e.registry.models:
        raise RuntimeError("Modul ya_purchase_multi_uom belum terpasang")

    print("DATABASE:", e.cr.dbname)
    print("MODE:", "APPLY" if apply else "PREVIEW (tanpa perubahan)")
    print("SUMBER: XLSX privat dari UOM_KONVERSI_FILE")

    rows = spreadsheet_rows(Path(source))
    if not rows or tuple(rows[0]) != HEADERS:
        raise RuntimeError("Header Excel review berbeda dari format yang disetujui")

    Products = e["product.product"].sudo()
    Rule = e["ya.purchase.uom.rule"].sudo().with_context(active_test=False)
    products = {}
    issues = []
    for product in Products.search([]):
        code = (product.default_code or "").strip()
        if code in products:
            issues.append("Duplikat SKU dalam Odoo: %s" % code)
        products[code] = product
    if len(products) != 2543:
        issues.append("Master produk bukan 2543 SKU unik (%s)" % len(products))
    if e["stock.move"].sudo().search_count([]) or e["purchase.order.line"].sudo().search_count([]):
        issues.append("Sudah ada stock move/PO line; proses impor harus ditinjau ulang")
    if e["stock.quant"].sudo().search_count([("quantity", "!=", 0)]):
        issues.append("Ada stok tidak nol; proses impor harus ditinjau ulang")

    candidates = []
    held = Counter()
    seen = set()
    for line_number, record in enumerate(rows[1:], 2):
        (_, sku, name, category, _, label, raw_factor, source_target,
         base_unit, status, _, _) = record
        if status not in ACCEPTED:
            held[status or "TANPA STATUS"] += 1
            continue
        product = products.get(sku)
        if not product:
            issues.append("Baris %s: SKU %s tidak ditemukan" % (line_number, sku))
            continue
        if product.product_tmpl_id.name.strip() != name or category_path(product.categ_id) != category:
            issues.append("Baris %s SKU %s: nama/kategori tidak cocok" % (line_number, sku))
        current_unit = product.uom_id.name
        if current_unit.casefold() != base_unit.casefold():
            issues.append("Baris %s SKU %s: satuan Excel %s, Odoo %s" %
                          (line_number, sku, base_unit, current_unit))
        if source_target.casefold() != base_unit.casefold():
            issues.append("Baris %s SKU %s: tujuan Excel bukan satuan dasar" % (line_number, sku))
        label = label.strip()
        if not label:
            issues.append("Baris %s SKU %s: label pembelian kosong" % (line_number, sku))
        try:
            factor = Decimal(raw_factor)
            if not factor.is_finite() or factor < 1 or factor != factor.to_integral_value():
                raise ValueError("faktor bukan bilangan bulat positif")
            factor = int(factor)
            if factor > 2147483647:
                raise ValueError("faktor melewati batas integer Odoo")
        except (InvalidOperation, ValueError, TypeError):
            issues.append("Baris %s SKU %s: faktor tidak valid %r" %
                          (line_number, sku, raw_factor))
            continue
        key = (sku, label.casefold())
        if key in seen:
            issues.append("Baris %s: duplikat SKU+satuan pembelian %s/%s" %
                          (line_number, sku, label))
        seen.add(key)
        candidates.append((product, label, factor))

    if len(rows) - 1 != 754 or len(candidates) != 608:
        issues.append("Jumlah Excel/kandidat berubah: %s/%s (diharapkan 754/608)" %
                      (len(rows) - 1, len(candidates)))

    existing = {}
    for rule in Rule.search([]):
        key = (rule.product_id.id, (rule.purchase_label or "").strip().casefold())
        if key in existing:
            issues.append("Duplikat aturan tersimpan: produk id %s/%s" % key)
        existing[key] = rule

    pending = []
    unchanged = 0
    for product, label, factor in candidates:
        old = existing.get((product.id, label.casefold()))
        if old is None:
            pending.append({"product_id": product.id, "purchase_label": label,
                            "factor": factor, "company_id": e.company.id})
        elif old.factor == factor and old.active:
            unchanged += 1
        else:
            issues.append("Konflik aturan SKU %s/%s: existing faktor=%s aktif=%s, Excel=%s" %
                          (product.default_code, label, old.factor, old.active, factor))

    print("EXCEL: %s baris | KANDIDAT: %s | SKU UNIK: %s" %
          (len(rows) - 1, len(candidates), len({p.id for p, _, _ in candidates})))
    print("DITAHAN:", dict(sorted(held.items())))
    print("ATURAN: tambah=%s | sudah cocok=%s | existing total=%s" %
          (len(pending), unchanged, len(existing)))
    print("STATUS JUAL/BELI: tidak diubah | PO/STOK/HARGA: tidak diubah")
    print("MASALAH VALIDASI:", len(issues))
    for issue in issues[:40]:
        print(" -", issue)
    if issues:
        print("KONVERSI_IMPORT_BLOCKED: tidak ada COMMIT")
        raise RuntimeError("Validasi gagal; perbaiki sumber atau master sebelum APPLY")

    if not apply:
        print("KONVERSI_IMPORT_PREVIEW_OK: tidak ada data diubah; gunakan UOM_KONVERSI_APPLY=YES")
        return
    try:
        # Seluruh aturan disimpan dalam satu transaksi; error membatalkan semuanya.
        if pending:
            Rule.create(pending)
        e.cr.commit()
    except Exception:
        e.cr.rollback()
        print("KONVERSI_IMPORT_FAILED: ROLLBACK seluruh perubahan")
        raise
    print("KONVERSI_IMPORT_SUCCESS: %s aturan baru, %s sudah cocok; COMMIT selesai" %
          (len(pending), unchanged))


main()
