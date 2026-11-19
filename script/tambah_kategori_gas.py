"""Tambah kategori All / Bahan Penolong / Gas (khusus isi gas LPG).

PREVIEW default; set GAS_KATEGORI_APPLY=YES untuk menyimpan.
Tidak membuat stok tabung gas atau mengatur FIFO/FEFO, UoM dan rute.
"""

import os
import traceback


def main():
    odoo_env = globals().get("env")
    if odoo_env is None or odoo_env.cr.dbname != "erp-yussyakmal":
        raise RuntimeError("Jalankan dalam Odoo shell erp-yussyakmal")
    apply_mode = os.environ.get("GAS_KATEGORI_APPLY") == "YES"
    companies = odoo_env["res.company"].sudo().search([])
    if len(companies) != 1:
        raise RuntimeError("Diharapkan tepat satu perusahaan")
    cats = odoo_env["product.category"].sudo().with_company(companies[0])
    roots = cats.search([("name", "=", "All"), ("parent_id", "=", False)])
    roots_ya = roots.filtered(lambda c: any(x.name == "Bahan Baku" for x in c.child_id)
                                      and any(x.name == "Produk Jadi" for x in c.child_id))
    if len(roots_ya) != 1:
        raise RuntimeError("Induk All YA tidak unik")
    root = roots_ya[0]
    parent = root.child_id.filtered(lambda c: c.name == "Bahan Penolong")
    if len(parent) != 1:
        raise RuntimeError("Kategori induk Bahan Penolong belum tersedia atau duplikat")
    parent = parent[0]
    existing = parent.child_id.filtered(lambda c: c.name == "Gas")
    if len(existing) > 1:
        raise RuntimeError("Subkategori Gas sudah duplikat")
    current_count = cats.search_count([])
    if current_count not in (75, 76):
        raise RuntimeError("Jumlah kategori di luar kondisi awal/akhir (75/76): %s" % current_count)

    values = {"name": "Gas", "parent_id": parent.id}
    copy_fields = (
        "property_cost_method", "property_valuation", "property_account_income_categ_id",
        "property_account_expense_categ_id", "property_stock_valuation_account_id",
    )
    for field in copy_fields:
        if field not in cats._fields:
            raise RuntimeError("Field kategori tidak tersedia: " + field)
        value = parent[field]
        values[field] = value.id if field.endswith("_id") else value
    if "account_stock_variation_id" in cats._fields:
        values["account_stock_variation_id"] = parent.account_stock_variation_id.id or False

    print("DATABASE:", odoo_env.cr.dbname)
    print("MODE:", "APPLY" if apply_mode else "PREVIEW (tanpa perubahan)")
    print("TARGET: All / Bahan Penolong / Gas |", "SUDAH ADA" if existing else "TAMBAH")
    print("SUMBER: 5 SKU kategori lama BT-Gas (isi gas; bukan tabung)")
    print("PENGATURAN: mengikuti Bahan Penolong | COST=%s | VALUATION=%s" %
          (values["property_cost_method"], values["property_valuation"]))
    print("STOCK VALUATION ACCOUNT:", parent.property_stock_valuation_account_id.code if parent.property_stock_valuation_account_id else "tidak disetel")
    print("FIFO/FEFO, UoM, rute, stok tabung: tidak diubah")
    if not apply_mode:
        print("GAS_KATEGORI_PREVIEW_OK: database tidak diubah.")
        return

    try:
        if not existing:
            cats.create(values)
        odoo_env.flush_all()
        if len(parent.child_id.filtered(lambda c: c.name == "Gas")) != 1 or cats.search_count([]) != 76:
            raise RuntimeError("Verifikasi subkategori Gas gagal")
        odoo_env.cr.commit()
        print("GAS_KATEGORI_IMPORT_SUCCESS: kategori Gas tersedia; total 76 kategori.")
    except Exception:
        odoo_env.cr.rollback()
        print("GAS_KATEGORI_IMPORT_FAILED: seluruh perubahan dibatalkan.")
        traceback.print_exc()
        raise


main()
