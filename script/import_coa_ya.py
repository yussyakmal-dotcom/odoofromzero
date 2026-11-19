"""Import YA COA in three ordered steps using the Odoo 19 ORM.

DEFAULT: preview only. Set COA_APPLY=YES to write/commit all steps atomically.
Run only in Odoo shell from the odoofromzero repository root.
"""

import csv
import os
import sys
import traceback
from pathlib import Path


TYPE_MAP = {
    "Bank and Cash": "asset_cash", "Receivable": "asset_receivable",
    "Current Assets": "asset_current", "Non-current Assets": "asset_non_current",
    "Prepayments": "asset_prepayments", "Fixed Assets": "asset_fixed",
    "Current Liabilities": "liability_current", "Non-current Liabilities": "liability_non_current",
    "Payable": "liability_payable", "Equity": "equity",
    "Current Year Earnings": "equity_unaffected", "Income": "income",
    "Other Income": "income_other", "Expenses": "expense",
    "Cost of Revenue": "expense_direct_cost",
}

# Target YA code -> existing Odoo code. Updating the record keeps journal links.
REUSE = {
    "11120004": "11120003",  # Incoming payments
    "11120005": "11120004",  # Outgoing payments, moved FIRST
    "1112006": "11120002",   # Bank suspense
    "1120010": "11210010",   # Receivable
    "1120012": "11210011",   # POS receivable
    "2110010": "21100010",   # Payable
}


def load_master():
    path = Path(os.environ.get("COA_YA_FILE", "MASTER CONFIG/COA_Bersih_Import.csv"))
    with path.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if len(rows) != 391:
        raise ValueError("Master harus berisi 391 akun, ditemukan %s" % len(rows))
    master = {}
    for row in rows:
        code = row["Code"].strip()
        if not code or code in master or row["Type"] not in TYPE_MAP:
            raise ValueError("Kode ganda/kosong atau tipe akun tidak dikenal: " + repr(row))
        master[code] = {
            "code": code,
            "name": row["Account Name"].strip(),
            "account_type": TYPE_MAP[row["Type"]],
            "reconcile": row["Allow Reconciliation"].strip().lower() == "true",
        }
    return master


def main():
    odoo_env = globals().get("env")
    if odoo_env is None:
        raise RuntimeError("Jalankan melalui Odoo shell, bukan python biasa")
    apply_mode = os.environ.get("COA_APPLY", "NO") == "YES"
    if odoo_env.cr.dbname != "erp-yussyakmal":
        raise RuntimeError("Database tidak sesuai: " + odoo_env.cr.dbname)

    # No mutation is authorized if transactions or a partial previous import exist.
    counters = {
        "account.move": odoo_env["account.move"].sudo().search_count([]),
        "account.move.line": odoo_env["account.move.line"].sudo().search_count([]),
        "stock.move": odoo_env["stock.move"].sudo().search_count([]),
    }
    if any(counters.values()):
        raise RuntimeError("Transaksi sudah ada, impor otomatis dibatalkan: " + str(counters))
    companies = odoo_env["res.company"].sudo().search([])
    if len(companies) != 1:
        raise RuntimeError("Skrip khusus database satu perusahaan")
    company = companies[0]
    account_model = odoo_env["account.account"].sudo().with_company(company).with_context(active_test=False)
    existing = {str(a.code): a for a in account_model.search([])}
    if len(existing) != 118:
        raise RuntimeError("Diharapkan 118 akun awal, ditemukan %s. Jalankan audit ulang." % len(existing))
    master = load_master()
    for target, source in REUSE.items():
        if source not in existing or target not in master:
            raise RuntimeError("Akun pemetaan hilang: %s -> %s" % (source, target))
        if target != "11120004" and target in existing and target != source:
            raise RuntimeError("Kode tujuan sudah dipakai: " + target)
    if "99999900" not in existing or existing["99999900"].account_type != "equity_unaffected":
        raise RuntimeError("Akun laba tahun berjalan bawaan tidak sesuai")

    release = [(existing["11120004"], master["11120005"])]
    update = []
    create = []
    for code, vals in master.items():
        if code in ("11120005", "99999900"):
            continue
        if code in REUSE:
            update.append((existing[REUSE[code]], vals))
        elif code in existing:
            update.append((existing[code], vals))
        else:
            create.append(vals)
    if (len(release), len(update), len(create)) != (1, 21, 368):
        raise RuntimeError("Jumlah tahap tidak sesuai: %s/%s/%s" % (len(release), len(update), len(create)))
    print("DATABASE:", odoo_env.cr.dbname)
    print("MODE:", "APPLY" if apply_mode else "PREVIEW (tanpa perubahan)")
    print("TAHAP 0: pindah kode Outstanding Payments 11120004 -> 11120005 (1 akun)")
    print("TAHAP 1: perbarui 21 akun bawaan berdasarkan identitas record")
    print("TAHAP 2: tambahkan 368 akun YA")
    print("KEEP: 99999900 tetap seperti bawaan Odoo")
    if not apply_mode:
        print("PREVIEW_OK: tidak ada data diubah. Gunakan COA_APPLY=YES untuk menjalankan.")
        return

    try:
        for account, vals in release:
            account.write(vals)
        print("TAHAP 0 SELESAI")
        for account, vals in update:
            account.write(vals)
        print("TAHAP 1 SELESAI")
        create_vals = []
        for vals in create:
            item = dict(vals)
            if "company_ids" in account_model._fields:
                item["company_ids"] = [(6, 0, [company.id])]
            elif "company_id" in account_model._fields:
                item["company_id"] = company.id
            create_vals.append(item)
        # Batch create is transactional; a failure aborts the entire migration.
        account_model.create(create_vals)
        print("TAHAP 2 SELESAI")
        odoo_env.flush_all()
        final = {str(a.code): a for a in account_model.search([])}
        missing = sorted(set(master) - set(final))
        wrong = [code for code, vals in master.items()
                 if code != "99999900" and code in final and
                 (final[code].account_type != vals["account_type"] or
                  final[code].reconcile != vals["reconcile"] or
                  final[code].name != vals["name"])]
        if missing or wrong:
            raise RuntimeError("Verifikasi gagal. Missing: %s. Mismatch: %s" % (missing, wrong))
        if len(final) != 486:
            raise RuntimeError("Jumlah total akun tidak sesuai: %s (seharusnya 486)" % len(final))
        odoo_env.cr.commit()
        print("COA_IMPORT_SUCCESS: 391 kode YA tersedia, 486 akun total termasuk bawaan Odoo.")
        print("Semua tahap disimpan bersama dalam satu COMMIT.")
    except Exception:
        odoo_env.cr.rollback()
        print("COA_IMPORT_FAILED: seluruh perubahan dibatalkan (ROLLBACK).")
        traceback.print_exc()
        raise


main()
