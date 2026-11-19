"""Tambahkan 3 akun BOP YA; preview default, BOP_APPLY=YES untuk simpan.

Jalankan melalui Odoo 19 shell di database erp-yussyakmal.
"""

import os
import traceback


TARGETS = {
    "5121035": "BOP - Kebersihan dan Sanitasi",
    "5121036": "BOP - Perlengkapan dan Alat Kerja Kecil",
    "5121037": "BOP - APD dan Higiene",
}


def main():
    odoo_env = globals().get("env")
    if odoo_env is None or odoo_env.cr.dbname != "erp-yussyakmal":
        raise RuntimeError("Jalankan melalui Odoo shell pada database erp-yussyakmal")
    apply_mode = os.environ.get("BOP_APPLY") == "YES"
    companies = odoo_env["res.company"].sudo().search([])
    if len(companies) != 1:
        raise RuntimeError("Diharapkan tepat satu perusahaan")
    company = companies[0]
    accounts = odoo_env["account.account"].sudo().with_company(company).with_context(active_test=False)
    existing = {str(a.code): a for a in accounts.search([])}
    if len(existing) != accounts.search_count([]):
        raise RuntimeError("Ada kode akun duplikat; batalkan otomatis")
    if len(existing) not in (486, 489):
        raise RuntimeError("Jumlah akun tidak sesuai tahap sebelumnya: %s (harus 486 atau 489)" % len(existing))

    missing = []
    for code, name in TARGETS.items():
        if code in existing:
            acc = existing[code]
            if acc.name != name or acc.account_type != "expense_direct_cost" or acc.reconcile:
                raise RuntimeError("Akun %s sudah ada tetapi konfigurasi berbeda: %s" % (code, acc.name))
        else:
            missing.append(code)
    if len(existing) + len(missing) != 489:
        raise RuntimeError("Kondisi akun tidak sesuai target 489; perlu pemeriksaan manual")

    print("DATABASE:", odoo_env.cr.dbname)
    print("MODE:", "APPLY" if apply_mode else "PREVIEW (tanpa perubahan)")
    print("TIPE: Cost of Revenue (expense_direct_cost), reconcile=False")
    for code, name in TARGETS.items():
        print("  %s: %s — %s" % (code, name, "TAMBAH" if code in missing else "SUDAH ADA"))
    print("JUMLAH AKUN TARGET: 489")
    if not apply_mode:
        print("BOP_PREVIEW_OK: tidak ada perubahan.")
        return

    try:
        values = []
        for code in missing:
            item = {"code": code, "name": TARGETS[code], "account_type": "expense_direct_cost", "reconcile": False}
            if "company_ids" in accounts._fields:
                item["company_ids"] = [(6, 0, [company.id])]
            elif "company_id" in accounts._fields:
                item["company_id"] = company.id
            values.append(item)
        if values:
            accounts.create(values)
        odoo_env.flush_all()
        final = {str(a.code): a for a in accounts.search([])}
        if len(final) != 489:
            raise RuntimeError("Verifikasi jumlah akun gagal: %s" % len(final))
        for code, name in TARGETS.items():
            acc = final.get(code)
            if not acc or acc.name != name or acc.account_type != "expense_direct_cost" or acc.reconcile:
                raise RuntimeError("Verifikasi akun gagal: " + code)
        odoo_env.cr.commit()
        print("BOP_IMPORT_SUCCESS: 3 akun BOP tersedia; total 489 akun. COMMIT selesai.")
    except Exception:
        odoo_env.cr.rollback()
        print("BOP_IMPORT_FAILED: seluruh perubahan dibatalkan.")
        traceback.print_exc()
        raise


main()
