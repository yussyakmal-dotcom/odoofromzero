"""Tambah kategori YA versi C tanpa menghapus kategori yang telah ada.

Odoo 19 shell, root repository. Default PREVIEW; KATEGORI_V2_APPLY=YES untuk simpan.
Sumber: MASTER CONFIG/C_Kategori_Produk_Import.csv (64 baris).
"""

import csv
import os
import traceback
from pathlib import Path


def main():
    odoo_env = globals().get("env")
    if odoo_env is None or odoo_env.cr.dbname != "erp-yussyakmal":
        raise RuntimeError("Jalankan lewat odoo-bin shell pada erp-yussyakmal")
    apply_mode = os.environ.get("KATEGORI_V2_APPLY") == "YES"
    companies = odoo_env["res.company"].sudo().search([])
    if len(companies) != 1:
        raise RuntimeError("Harus ada tepat satu perusahaan")
    company = companies[0]
    cats = odoo_env["product.category"].sudo().with_company(company)
    accounts = odoo_env["account.account"].sudo().with_company(company)
    if accounts.search_count([]) != 486:
        raise RuntimeError("Jumlah akun COA tidak sesuai dengan tahap sebelumnya (486)")

    source = Path(os.environ.get("KATEGORI_V2_FILE", "MASTER CONFIG/C_Kategori_Produk_Import.csv"))
    with source.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if len(rows) != 64:
        raise RuntimeError("Master revisi C semestinya 64 baris; ditemukan %s" % len(rows))

    field_map = {
        "Income Account": "property_account_income_categ_id",
        "Expense Account": "property_account_expense_categ_id",
        "Stock Valuation Account": "property_stock_valuation_account_id",
    }
    needed_fields = ["property_cost_method", "property_valuation", "parent_id"] + list(field_map.values())
    missing_fields = [key for key in needed_fields if key not in cats._fields]
    if missing_fields:
        raise RuntimeError("Field Odoo yang diperlukan tidak ada: %s" % missing_fields)

    by_code = {str(a.code): a for a in accounts.search([])}
    if len(by_code) != accounts.search_count([]):
        raise RuntimeError("Ada kode COA duplikat")
    all_cats = cats.search([])
    roots = all_cats.filtered(lambda c: c.name == "All" and not c.parent_id)
    roots_ya = roots.filtered(lambda c: any(ch.name == "Bahan Baku" for ch in c.child_id)
                                     and any(ch.name == "Produk Jadi" for ch in c.child_id))
    if len(roots_ya) != 1:
        raise RuntimeError("Tidak dapat menemukan satu induk All hasil impor YA; kandidat: %s" % len(roots_ya))
    root = roots_ya[0]

    def existing_path(cat):
        segments = []
        node = cat
        while node:
            segments.append(node.name)
            node = node.parent_id
        return " / ".join(reversed(segments))

    existing = {}
    for cat in all_cats:
        ancestor = cat
        while ancestor.parent_id:
            ancestor = ancestor.parent_id
        if ancestor != root:
            continue
        key = existing_path(cat)
        if key in existing:
            raise RuntimeError("Path kategori tidak unik: " + key)
        existing[key] = cat

    parsed = []
    paths = set()
    for line, row in enumerate(rows, start=2):
        name = row["Name"].strip()
        parent = row["Parent Category"].strip()
        path = parent + " / " + name
        if not name or not parent.startswith("All") or path in paths:
            raise RuntimeError("Induk/nama ganda atau kosong di baris %s" % line)
        paths.add(path)
        costing = row["Costing Method"].strip()
        valuation = row["Inventory Valuation"].strip()
        valid_costs = {"Average Cost (AVCO)": "average", "Standard Price": "standard", "First In First Out (FIFO)": "fifo"}
        valid_valuations = {"Automated": "real_time", "Manual": "manual_periodic"}
        if costing not in valid_costs or valuation not in valid_valuations:
            raise RuntimeError("Metode costing/valuation tidak dikenal: " + path)
        vals = {"name": name, "property_cost_method": valid_costs[costing], "property_valuation": valid_valuations[valuation]}
        for col, field in field_map.items():
            label = row[col].strip()
            if label:
                code = label.split(" ", 1)[0]
                if code not in by_code:
                    raise RuntimeError("Akun %s tidak ditemukan pada %s" % (code, path))
                vals[field] = by_code[code].id
        # Atas keputusan Feri, kolom Force Removal Strategy sengaja diabaikan.
        # FIFO/FEFO akan dibahas setelah seluruh master kategori dan gudang siap.
        parsed.append((path, parent, vals))

    expected = {p for p, _, _ in parsed}
    additions = [(p, parent, vals) for p, parent, vals in parsed if p not in existing]
    retained = ["All / Produk Jadi / " + name for name in ("Cake Loyang Sudirman", "Roti Sudirman", "Dahlia 5")]
    if not all(p in existing and p not in expected for p in retained):
        raise RuntimeError("Tiga kategori lama yang harus ditahan tidak sesuai kondisi sebelumnya")
    for path, parent, _ in additions:
        if parent not in existing and parent not in expected:
            raise RuntimeError("Induk kategori tidak ditemukan: " + parent)

    variation = None
    if "account_stock_variation_id" in cats._fields:
        reference = existing.get("All / Bahan Baku")
        variation = reference.account_stock_variation_id if reference else None
        if not variation:
            raise RuntimeError("Akun variasi stok kategori Bahan Baku belum ada")

    print("DATABASE:", odoo_env.cr.dbname)
    print("MODE:", "APPLY" if apply_mode else "PREVIEW (tanpa perubahan)")
    print("SUMBER:", source)
    print("KATEGORI BARU:", len(additions), "(29 subkategori Bahan Baku + 16 kategori lain)")
    print("FIFO/FEFO: dilewati; tidak ada pengaturan removal strategy yang diubah")
    print("KATEGORI LAMA DITAHAN (tidak dihapus):", ", ".join(retained))
    print("AKUN VARIASI STOK:", variation.code if variation else "tidak ada field")
    print("FIELD STOCK INPUT: tidak dipetakan (Odoo 19)")
    if not apply_mode:
        print("KATEGORI_V2_PREVIEW_OK: tidak ada perubahan.")
        return

    try:
        for path, parent, values in sorted(additions, key=lambda item: (item[0].count(" / "), item[0])):
            if path in existing:
                raise RuntimeError("Kategori sudah ada saat APPLY: " + path)
            vals = dict(values, parent_id=existing[parent].id)
            if variation:
                vals["account_stock_variation_id"] = variation.id
            created = cats.create(vals)
            existing[path] = created
        odoo_env.flush_all()
        for path in expected:
            if path not in existing:
                raise RuntimeError("Kategori belum terbentuk: " + path)
        odoo_env.cr.commit()
        print("KATEGORI_V2_IMPORT_SUCCESS: %s kategori ditambah; FIFO/FEFO tidak diubah; tidak ada penghapusan." % len(additions))
    except Exception:
        odoo_env.cr.rollback()
        print("KATEGORI_V2_IMPORT_FAILED: seluruh perubahan dibatalkan.")
        traceback.print_exc()
        raise


main()
