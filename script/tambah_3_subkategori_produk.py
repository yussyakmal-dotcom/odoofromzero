"""Tambahkan 3 subkategori produk YA yang disetujui Feri.

Mode default PREVIEW (read-only); set SUBKATEGORI_APPLY=YES untuk menyimpan.
Tidak mengatur FIFO/FEFO maupun satuan produk.
"""

import os
import traceback


TARGETS = (
    ("Produk Jadi", "Kue Kering"),
    ("Produk Jadi", "Frozen Food"),
    ("Bahan Baku", "Agar-agar"),
)


def main():
    odoo_env = globals().get("env")
    if odoo_env is None or odoo_env.cr.dbname != "erp-yussyakmal":
        raise RuntimeError("Jalankan dengan Odoo shell pada erp-yussyakmal")
    apply_mode = os.environ.get("SUBKATEGORI_APPLY") == "YES"
    companies = odoo_env["res.company"].sudo().search([])
    if len(companies) != 1:
        raise RuntimeError("Diharapkan satu perusahaan")
    cats = odoo_env["product.category"].sudo().with_company(companies[0])
    accounts = odoo_env["account.account"].sudo().with_company(companies[0])
    if accounts.search_count([]) != 489:
        raise RuntimeError("COA tidak sesuai hasil tahap sebelumnya (489 akun)")
    if cats.search_count([]) not in (71, 74):
        raise RuntimeError("Jumlah kategori di luar kondisi awal/akhir yang diharapkan (71/74)")

    roots = cats.search([("name", "=", "All"), ("parent_id", "=", False)])
    selected_roots = roots.filtered(lambda c: any(x.name == "Bahan Baku" for x in c.child_id)
                                          and any(x.name == "Produk Jadi" for x in c.child_id))
    if len(selected_roots) != 1:
        raise RuntimeError("Induk All YA tidak unik")
    root = selected_roots[0]
    required_fields = (
        "property_cost_method",
        "property_valuation",
        "property_account_income_categ_id",
        "property_account_expense_categ_id",
        "property_stock_valuation_account_id",
    )
    for field in required_fields:
        if field not in cats._fields:
            raise RuntimeError("Field Odoo hilang: " + field)

    plans = []
    for parent_name, name in TARGETS:
        parent = root.child_id.filtered(lambda c: c.name == parent_name)
        if len(parent) != 1:
            raise RuntimeError("Induk %s tidak unik" % parent_name)
        parent = parent[0]
        matched = parent.child_id.filtered(lambda c: c.name == name)
        if len(matched) > 1:
            raise RuntimeError("Subkategori ganda: %s / %s" % (parent_name, name))
        vals = {"name": name, "parent_id": parent.id}
        for field in required_fields:
            value = parent[field]
            vals[field] = value.id if field.endswith("_id") else value
        if "account_stock_variation_id" in cats._fields:
            vals["account_stock_variation_id"] = parent.account_stock_variation_id.id or False
        plans.append((parent_name, name, matched, vals))

    print("DATABASE:", odoo_env.cr.dbname)
    print("MODE:", "APPLY" if apply_mode else "PREVIEW (tanpa perubahan)")
    print("STRATEGI FIFO/FEFO: tidak diatur")
    print("SATUAN PRODUK: tidak diatur")
    for parent_name, name, matched, vals in plans:
        print("SUBKATEGORI: All / %s / %s | %s | COST=%s | VALUATION=%s" %
              (parent_name, name, "SUDAH ADA" if matched else "TAMBAH", vals["property_cost_method"], vals["property_valuation"]))
    if not apply_mode:
        print("SUBKATEGORI_PREVIEW_OK: database tidak diubah.")
        return

    try:
        for parent_name, name, matched, vals in plans:
            if not matched:
                cats.create(vals)
        odoo_env.flush_all()
        for parent_name, name, _, _ in plans:
            parent = root.child_id.filtered(lambda c: c.name == parent_name)
            if len(parent.child_id.filtered(lambda c: c.name == name)) != 1:
                raise RuntimeError("Verifikasi subkategori gagal: %s / %s" % (parent_name, name))
        if cats.search_count([]) != 74:
            raise RuntimeError("Jumlah kategori akhir bukan 74")
        odoo_env.cr.commit()
        print("SUBKATEGORI_IMPORT_SUCCESS: 3 subkategori tersedia; tanpa perubahan FIFO/FEFO.")
    except Exception:
        odoo_env.cr.rollback()
        print("SUBKATEGORI_IMPORT_FAILED: perubahan dibatalkan.")
        traceback.print_exc()
        raise


main()
