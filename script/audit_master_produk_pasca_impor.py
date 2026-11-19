"""Audit READ-ONLY master produk YA setelah impor, untuk Odoo 19 shell.

Jalankan dengan PRODUK_YA_FILE menunjuk CSV staging PRIVAT (di luar repo).
Skrip tidak menulis database, tidak membuat file, dan tidak mencetak nilai harga
atau biaya per SKU. Status AUDIT_PRODUK_LULUS hanya jika seluruh cek lulus.
"""

import csv
import os
from collections import Counter
from decimal import Decimal, InvalidOperation
from pathlib import Path


def audit():
    odoo_env = globals().get("env")
    if odoo_env is None or odoo_env.cr.dbname != "erp-yussyakmal":
        raise RuntimeError("Database harus erp-yussyakmal")

    companies = odoo_env["res.company"].sudo().search([])
    if len(companies) != 1:
        raise RuntimeError("Audit membutuhkan tepat satu perusahaan")
    company = companies[0]
    Product = odoo_env["product.template"].sudo().with_company(company)
    Variant = odoo_env["product.product"].sudo().with_company(company)
    Category = odoo_env["product.category"].sudo().with_company(company)

    source = os.environ.get("PRODUK_YA_FILE")
    if not source:
        raise RuntimeError("Set PRODUK_YA_FILE ke lokasi CSV staging privat")
    with Path(source).open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"Internal Reference", "Name", "Sales Price", "Cost", "Product Category",
                    "Product Type", "Track Inventory", "UoM Decision", "Import Decision"}
        if not required.issubset(reader.fieldnames or []):
            raise RuntimeError("Kolom CSV wajib tidak lengkap")
        source_rows = list(reader)

    expected = {}
    problems = []

    def issue(message):
        if len(problems) < 30:
            problems.append(message)

    for number, row in enumerate(source_rows, 2):
        sku = row["Internal Reference"].strip()
        if not sku or sku in expected:
            issue("CSV: SKU kosong/duplikat di baris %s" % number)
            continue
        expected[sku] = row

    products = Product.search([])
    variants = Variant.search([])
    categories = Category.search([])
    print("DATABASE:", odoo_env.cr.dbname)
    print("MODE: AUDIT READ-ONLY (tanpa perubahan)")
    print("SUMBER: CSV privat dari PRODUK_YA_FILE")
    print("CSV:", len(source_rows), "baris | SKU unik:", len(expected))
    print("ODOO: template=%s | varian=%s | kategori=%s" % (len(products), len(variants), len(categories)))

    if len(source_rows) != 2543 or len(expected) != 2543:
        issue("Jumlah/keunikan SKU CSV bukan 2543")
    if len(products) != 2543 or len(variants) != 2543:
        issue("Jumlah template/varian Odoo bukan 2543")
    if len(categories) != 76:
        issue("Jumlah kategori Odoo bukan 76")

    # Rekonstruksi lokasi kategori dari parent_id, tidak mengandalkan nama kategori saja.
    def category_path(category):
        names = []
        seen = set()
        while category:
            if category.id in seen:
                raise RuntimeError("Siklus parent_id kategori")
            seen.add(category.id)
            names.append(category.name)
            category = category.parent_id
        return " / ".join(reversed(names))

    actual = {}
    duplicate_skus = set()
    mismatch_counts = Counter()

    for product in products:
        sku = (product.default_code or "").strip()
        if not sku:
            mismatch_counts["SKU kosong"] += 1
            continue
        if sku in actual:
            duplicate_skus.add(sku)
        actual[sku] = product

    if duplicate_skus:
        issue("Ada %s SKU duplikat pada template" % len(duplicate_skus))
    missing = set(expected) - set(actual)
    extra = set(actual) - set(expected)
    print("KECOCOKAN SKU: tidak ditemukan=%s | tambahan=%s | duplikat=%s" %
          (len(missing), len(extra), len(duplicate_skus)))
    if missing or extra:
        issue("Daftar SKU database tidak identik dengan staging")

    for sku in set(expected) & set(actual):
        product = actual[sku]
        row = expected[sku]
        if product.name != row["Name"].strip():
            mismatch_counts["nama"] += 1
        if category_path(product.categ_id) != row["Product Category"].strip():
            mismatch_counts["kategori"] += 1
        if product.type != "consu" or not product.is_storable or product.tracking != "none":
            mismatch_counts["tipe/pelacakan"] += 1
        if product.sale_ok or product.purchase_ok:
            mismatch_counts["izin jual/beli aktif"] += 1
        if not product.uom_id or product.uom_id.name != "Units":
            mismatch_counts["UoM bukan Units"] += 1
        if not product.active:
            mismatch_counts["nonaktif"] += 1
        if (row["Product Type"], row["Track Inventory"], row["UoM Decision"],
                row["Import Decision"]) != ("Goods", "YES", "PENDING_CUSTOM_UOM", "STAGING_ONLY"):
            mismatch_counts["kebijakan staging"] += 1
        try:
            expected_sale = Decimal(row["Sales Price"])
            expected_cost = Decimal(row["Cost"])
            # Toleransi representasi float, lebih kecil dari sen/rupiah terkecil.
            if abs(Decimal(str(product.list_price)) - expected_sale) > Decimal("0.001"):
                mismatch_counts["harga jual"] += 1
            if abs(Decimal(str(product.standard_price)) - expected_cost) > Decimal("0.001"):
                mismatch_counts["harga biaya"] += 1
        except (InvalidOperation, TypeError):
            mismatch_counts["angka CSV tidak valid"] += 1

    var_counts = Counter(variant.product_tmpl_id.id for variant in variants)
    wrong_variant = sum(1 for product in products if var_counts[product.id] != 1)
    if wrong_variant:
        mismatch_counts["jumlah varian per template"] = wrong_variant

    move_count = odoo_env["stock.move"].sudo().search_count([])
    quant_nonzero = odoo_env["stock.quant"].sudo().search_count([("quantity", "!=", 0)])
    print("PERGERAKAN STOK: stock.move=%s | quant dengan qty != 0=%s" % (move_count, quant_nonzero))
    if move_count or quant_nonzero:
        issue("Terdapat pergerakan stok atau kuantitas stok tidak nol")

    print("SELISIH PER FIELD:", dict(sorted(mismatch_counts.items())))
    if mismatch_counts:
        issue("Ditemukan ketidaksesuaian atribut produk")
    print("TEMUAN:", len(problems), "jenis (maksimum 30 ditampilkan)")
    for problem in problems:
        print("  -", problem)
    if problems:
        print("AUDIT_PRODUK_GAGAL: jangan duplikasi dulu; periksa temuan")
        raise RuntimeError("Audit produk belum lulus")
    print("AUDIT_PRODUK_LULUS: 2543 SKU sesuai CSV, tanpa stok/transaksi; database tidak diubah")
    print("SELANJUTNYA: duplikasi database menggunakan Database Manager Odoo")


audit()
