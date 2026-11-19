"""Impor 30 master warehouse YA ke Odoo 19, preview dulu.

Jalankan melalui Odoo shell dari root repository. Mode awal read-only.
Untuk apply secara atomik, set GUDANG_APPLY=YES.
"""

import csv
import os
import traceback
from pathlib import Path


def main():
    odoo_env = globals().get("env")
    if odoo_env is None:
        raise RuntimeError("Jalankan melalui Odoo shell")
    if odoo_env.cr.dbname != "erp-yussyakmal":
        raise RuntimeError("Database tidak sesuai")
    apply_mode = os.environ.get("GUDANG_APPLY", "NO") == "YES"
    companies = odoo_env["res.company"].sudo().search([])
    if len(companies) != 1:
        raise RuntimeError("Skrip untuk satu perusahaan")
    company = companies[0]
    wh_model = odoo_env["stock.warehouse"].sudo().with_company(company)
    existing = wh_model.search([])
    if len(existing) != 1 or existing.code != "WH":
        raise RuntimeError("Harus ada tepat 1 gudang bawaan berkode WH; jalankan audit ulang")
    if odoo_env["stock.move"].sudo().search_count([]):
        raise RuntimeError("Sudah ada pergerakan stok; tidak aman melakukan rename otomatis")
    with Path(os.environ.get("GUDANG_YA_FILE", "MASTER CONFIG/Master_Gudang_Import.csv")).open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if len(rows) != 30:
        raise RuntimeError("Master harus berisi 30 gudang, ditemukan %d" % len(rows))
    codes = set()
    names = set()
    for row in rows:
        code = row["Short Name"].strip()
        name = row["Warehouse"].strip()
        if not code or not name or len(code) > 5:
            raise RuntimeError("Nama kosong atau kode lebih dari 5 karakter: " + repr(row))
        if code.casefold() in codes or name.casefold() in names:
            raise RuntimeError("Duplikasi kode/nama: " + repr(row))
        codes.add(code.casefold()); names.add(name.casefold())
    if rows[0]["Short Name"] != "CDC" or rows[0]["Warehouse"] != "Gudang Central":
        raise RuntimeError("Baris pertama harus Gudang Central / CDC")

    print("DATABASE:", odoo_env.cr.dbname)
    print("MODE:", "APPLY" if apply_mode else "PREVIEW (tanpa perubahan)")
    print("TOTAL MASTER:", len(rows))
    print("TAHAP 1: ubah warehouse bawaan WH menjadi Gudang Central / CDC")
    print("TAHAP 2: buat 29 warehouse YA lainnya")
    print("CATATAN: Odoo membuat lokasi, rute, dan Operation Types standar secara otomatis.")
    if not apply_mode:
        print("GUDANG_PREVIEW_OK: tidak ada perubahan.")
        return

    try:
        existing.write({"name": rows[0]["Warehouse"], "code": rows[0]["Short Name"]})
        for row in rows[1:]:
            wh_model.create({"name": row["Warehouse"], "code": row["Short Name"], "company_id": company.id})
        odoo_env.flush_all()
        final = wh_model.search([])
        final_codes = {w.code.casefold() for w in final}
        if len(final) != 30 or final_codes != codes:
            raise RuntimeError("Verifikasi jumlah/kode gagal: %d record" % len(final))
        odoo_env.cr.commit()
        print("GUDANG_IMPORT_SUCCESS: 30 warehouse YA tersedia, termasuk CDC.")
    except Exception:
        odoo_env.cr.rollback()
        print("GUDANG_IMPORT_FAILED: seluruh perubahan dibatalkan.")
        traceback.print_exc()
        raise


main()
