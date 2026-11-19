"""Impor kategori produk YA untuk Odoo 19: preview atau apply satu transaksi.

Jalankan dari root repository melalui Odoo shell.
Mode standar hanya membaca; set KATEGORI_APPLY=YES untuk menyimpan.
"""

import csv
import os
import traceback
from pathlib import Path


def main():
    odoo_env = globals().get("env")
    if odoo_env is None:
        raise RuntimeError("Jalankan melalui odoo-bin shell")
    if odoo_env.cr.dbname != "erp-yussyakmal":
        raise RuntimeError("Database harus erp-yussyakmal")
    apply_mode = os.environ.get("KATEGORI_APPLY", "NO") == "YES"
    company = odoo_env["res.company"].sudo().search([])
    if len(company) != 1:
        raise RuntimeError("Skrip hanya untuk satu perusahaan")
    company = company[0]
    cats = odoo_env["product.category"].sudo().with_company(company)
    accounts = odoo_env["account.account"].sudo().with_company(company)

    file_path = Path(os.environ.get("KATEGORI_YA_FILE", "MASTER CONFIG/Kategori_Produk_Import.csv"))
    with file_path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if len(rows) != 22:
        raise RuntimeError("Master kategori harus berisi 22 baris, ditemukan %s" % len(rows))
    if cats.search_count([]) != 3:
        raise RuntimeError("Kategori awal bukan 3; kemungkinan sudah diimpor sebagian")
    if accounts.search_count([]) != 486:
        raise RuntimeError("COA belum sesuai hasil impor (diharapkan 486 akun)")
    if odoo_env["stock.move"].sudo().search_count([]):
        raise RuntimeError("Sudah ada pergerakan stok; hentikan impor otomatis")

    required = ["property_cost_method", "property_valuation", "property_stock_valuation_account_id",
                "property_account_income_categ_id", "property_account_expense_categ_id"]
    missing_fields = [f for f in required if f not in cats._fields]
    if missing_fields:
        raise RuntimeError("Field kategori Odoo 19 tidak tersedia: " + repr(missing_fields))
    for field_name, expected in (("property_cost_method", "average"), ("property_valuation", "real_time")):
        choices = cats._fields[field_name].selection
        if isinstance(choices, (list, tuple)) and expected not in [value for value, label in choices]:
            raise RuntimeError("Pilihan %s tidak tersedia pada Odoo ini: %s" % (expected, field_name))
    # Odoo 19's stock input account column is intentionally not applied.
    old_input_field = "property_stock_account_input_categ_id" in cats._fields
    available = {str(a.code): a for a in accounts.search([])}
    all_names = set()
    parsed = []
    for row in rows:
        name = row["Name"].strip()
        parent = row["Parent Category"].strip()
        if not name or parent not in ("All", "All / Produk Jadi"):
            raise RuntimeError("Nama atau induk tidak dikenal: " + repr(row))
        if (parent, name) in all_names:
            raise RuntimeError("Kategori ganda: " + parent + " / " + name)
        all_names.add((parent, name))
        if row["Costing Method"] != "Average Cost (AVCO)" or row["Inventory Valuation"] != "Automated":
            raise RuntimeError("Costing/valuation master tidak sesuai: " + name)
        vals = {"name": name, "property_cost_method": "average", "property_valuation": "real_time"}
        mapping = {
            "Income Account": "property_account_income_categ_id",
            "Expense Account": "property_account_expense_categ_id",
            "Stock Valuation Account": "property_stock_valuation_account_id",
        }
        for source, field in mapping.items():
            raw = row[source].strip()
            if raw:
                code = raw.split(" ", 1)[0]
                if code not in available:
                    raise RuntimeError("Akun tidak ditemukan untuk %s: %s" % (name, code))
                vals[field] = available[code].id
        parsed.append((parent, vals, row))
    if (sum(p == "All" for p, _, _ in parsed), sum(p == "All / Produk Jadi" for p, _, _ in parsed)) != (9, 13):
        raise RuntimeError("Struktur induk berbeda dari master: harus 9 + 13")

    # Use the default Odoo 19 variation account, not the obsolete Stock Input field.
    variation = None
    if "account_stock_variation_id" in cats._fields:
        goods = cats.search([("name", "=", "Goods")], limit=1)
        variation = goods.account_stock_variation_id if goods else None
        if not variation:
            raise RuntimeError("Akun perubahan persediaan Odoo belum terkonfigurasi")

    print("DATABASE:", odoo_env.cr.dbname)
    print("MODE:", "APPLY" if apply_mode else "PREVIEW (tanpa perubahan)")
    print("KATEGORI: 1 induk All + 9 utama + 13 subkategori = 23 record baru")
    print("METODE: Average Cost (AVCO) + Perpetual Valuation Odoo 19")
    print("STOCK INPUT: tidak dipetakan; field Odoo 19 tersedia:", old_input_field)
    print("AKUN PERUBAHAN STOK:", variation.code if variation else "tidak ada field")
    if not apply_mode:
        print("KATEGORI_PREVIEW_OK: tidak ada perubahan.")
        return

    try:
        root = cats.create({"name": "All"})
        parent_by_path = {"All": root}
        for parent, vals, row in parsed:
            if parent != "All":
                continue
            vals = dict(vals, parent_id=root.id)
            if variation:
                vals["account_stock_variation_id"] = variation.id
            cat = cats.create(vals)
            parent_by_path["All / " + vals["name"]] = cat
        if "All / Produk Jadi" not in parent_by_path:
            raise RuntimeError("Induk Produk Jadi tidak terbentuk")
        for parent, vals, row in parsed:
            if parent == "All":
                continue
            vals = dict(vals, parent_id=parent_by_path[parent].id)
            if variation:
                vals["account_stock_variation_id"] = variation.id
            cats.create(vals)
        odoo_env.flush_all()
        if cats.search_count([]) != 26:
            raise RuntimeError("Jumlah kategori tidak sesuai: " + str(cats.search_count([])))
        odoo_env.cr.commit()
        print("KATEGORI_IMPORT_SUCCESS: 22 kategori master + 1 induk All tersimpan.")
    except Exception:
        odoo_env.cr.rollback()
        print("KATEGORI_IMPORT_FAILED: perubahan dibatalkan seluruhnya.")
        traceback.print_exc()
        raise


main()
