"""Audit read-only hasil impor Master Mitra YA terhadap CSV review Feri.

Jalankan Odoo shell di erp-yussyakmal-integer-test dengan MITRA_YA_FILE.
Tidak melakukan create/write/commit maupun perbaikan data.
"""

import csv
import hashlib
import os
import re
from collections import Counter
from pathlib import Path


DB = "erp-yussyakmal-integer-test"
MODULE = "ya_master_mitra"
TAG = "YA / Konsinyasi (CS)"


def norm(value):
    return " ".join((value or "").casefold().split())


def xml_name(name):
    return "mitra_" + hashlib.sha256(norm(name).encode("utf-8")).hexdigest()[:24]


def main():
    e = globals().get("env")
    if e is None or e.cr.dbname != DB:
        raise RuntimeError("Audit ini hanya untuk %s" % DB)
    source = Path(os.environ.get("MITRA_YA_FILE", ""))
    if not source.is_file():
        raise RuntimeError("MITRA_YA_FILE tidak tersedia")
    with source.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"Display Name", "Email", "Contact Address Complete",
                    "Telepon 1 (usulan)", "Telepon 2 (usulan)", "Nomor asli perlu review"}
        if not required.issubset(reader.fieldnames or []):
            raise RuntimeError("CSV review tidak sesuai")
        rows = list(reader)

    Partners = e["res.partner"].sudo().with_context(active_test=False)
    ModelData = e["ir.model.data"].sudo()
    expected_names = Counter(norm(r["Display Name"]) for r in rows)
    issues = []
    counts = Counter()
    if any(n != 1 for n in expected_names.values()):
        issues.append("CSV masih memiliki nama duplikat")

    xmlids = ModelData.search([("module", "=", MODULE), ("model", "=", "res.partner")])
    if len(xmlids) != len(rows):
        issues.append("Jumlah External ID %s != CSV %s" % (len(xmlids), len(rows)))
    imported_ids = set(xmlids.mapped("res_id"))
    if len(imported_ids) != len(xmlids):
        issues.append("External ID menunjuk mitra yang sama lebih dari sekali")

    for line_no, row in enumerate(rows, start=2):
        name = (row["Display Name"] or "").strip()
        xid = ModelData.search([("module", "=", MODULE), ("name", "=", xml_name(name))])
        if len(xid) != 1 or xid.model != "res.partner":
            issues.append("Baris %s: External ID tidak unik/tidak ditemukan: %s" % (line_no, name))
            continue
        partner = Partners.browse(xid.res_id)
        if not partner.exists():
            issues.append("Baris %s: res.partner hilang" % line_no)
            continue
        counts["matched"] += 1
        fields = {
            "name": name,
            "phone": (row["Telepon 1 (usulan)"] or "").strip(),
            "ya_phone2": (row["Telepon 2 (usulan)"] or "").strip(),
            "email": (row["Email"] or "").strip(),
            "street": (row["Contact Address Complete"] or "").strip(),
        }
        for field, expected in fields.items():
            actual = (getattr(partner, field) or "").strip()
            if actual != expected:
                issues.append("Baris %s: %s berbeda (%s)" % (line_no, field, name))
        if partner.supplier_rank < 1:
            issues.append("Baris %s: supplier_rank belum aktif" % line_no)
        is_cs = bool(re.search(r"\bCS\s*$", name, re.I))
        tagged = TAG in partner.category_id.mapped("name")
        if tagged != is_cs:
            issues.append("Baris %s: tag CS tidak cocok" % line_no)
        counts["cs"] += int(is_cs)
        counts["phone2"] += int(bool(fields["ya_phone2"]))
        note = (row["Nomor asli perlu review"] or "").strip()
        if note:
            counts["notes"] += 1
            if note not in (partner.comment or ""):
                issues.append("Baris %s: catatan telepon asli tidak ada" % line_no)

    print("DATABASE:", e.cr.dbname)
    print("MODE: AUDIT READ-ONLY; tanpa CREATE/WRITE/COMMIT")
    print("CSV:", len(rows), "| EXTERNAL ID:", len(xmlids), "| RECORD COCOK:", counts["matched"])
    print("TAG CS:", counts["cs"], "| TELEPON 2:", counts["phone2"], "| CATATAN NOMOR:", counts["notes"])
    print("JUMLAH TEMUAN:", len(issues))
    for issue in issues[:40]:
        print("TEMUAN:", issue)
    if issues:
        print("MITRA_AUDIT_FAILED: periksa temuan; database tidak berubah")
        raise RuntimeError("Audit mitra menemukan %s masalah" % len(issues))
    print("MITRA_AUDIT_OK: seluruh data sesuai CSV review; database tidak diubah")


main()
