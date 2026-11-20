"""Impor satu master mitra dari CSV vendor YA (Odoo shell).

PREVIEW default; APPLY hanya pada database uji dengan YA_MITRA_APPLY=YES.
File CSV privat melalui MITRA_YA_FILE, tidak ikut repository.
Baris nama ambigu/duplikat ditahan; nama kontak bukan pembatas peran bisnis.
"""

import csv
import hashlib
import os
import re
from collections import Counter
from pathlib import Path


EXPECTED_HEADERS = ["Display Name", "Email", "Phone", "Contact Address Complete"]
REVIEW_HEADERS = EXPECTED_HEADERS + [
    "Telepon 1 (usulan)", "Telepon 2 (usulan)", "Nomor asli perlu review",
    "Status telepon", "Status impor", "Alasan review", "Tag konsinyasi",
    "Baris sumber CSV",
]
XML_MODULE = "ya_master_mitra"
TAG_NAME = "YA / Konsinyasi (CS)"
TEST_DATABASE = "erp-yussyakmal-integer-test"


def clean(value):
    return (value or "").strip()


def key_of(name):
    return " ".join(name.casefold().split())


def xml_name(key):
    return "mitra_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]


def phone_or_empty(raw):
    value = clean(raw)
    if not value or value in {"-", "#ERROR!"}:
        return ""
    digits = re.sub(r"\D", "", value)
    if not (9 <= len(digits) <= 15):
        return ""
    if not re.fullmatch(r"\+?[\d\s().-]+", value):
        return ""
    return value


def parse_phones(raw):
    """Kembalikan (phone, mobile, catatan) tanpa menebak nomor terpotong."""
    value = clean(raw)
    if not value:
        return "", "", ""
    if phone_or_empty(value):
        return value, "", ""
    # Pisahkan hanya pada pembatas antar-NOMOR, bukan tanda hubung di dalam nomor.
    pieces = [part.strip() for part in re.split(r"\s+[-–]\s+|\s*[,;/]\s*", value)]
    if len(pieces) == 2 and all(phone_or_empty(part) for part in pieces):
        return pieces[0], pieces[1], ""
    return "", "", value


def main():
    e = globals().get("env")
    if e is None or e.cr.dbname != TEST_DATABASE:
        raise RuntimeError("Skrip ini hanya untuk database uji %s" % TEST_DATABASE)

    applying = os.environ.get("YA_MITRA_APPLY") == "YES"
    source = Path(os.environ.get("MITRA_YA_FILE", ""))
    if not source.is_file():
        raise RuntimeError("MITRA_YA_FILE harus menunjuk CSV privat yang terbaca user odoo19")

    with source.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames not in (EXPECTED_HEADERS, REVIEW_HEADERS):
            raise RuntimeError("Header CSV berbeda: %r" % reader.fieldnames)
        reviewed_file = reader.fieldnames == REVIEW_HEADERS
        rows = list(reader)
    if not rows:
        raise RuntimeError("CSV kosong")

    counts = Counter(key_of(clean(row["Display Name"])) for row in rows)
    Partners = e["res.partner"].sudo().with_context(active_test=False)
    ModelData = e["ir.model.data"].sudo()
    Tag = e["res.partner.category"].sudo()
    for field in ("name", "phone", "ya_phone2", "email", "street", "supplier_rank", "category_id", "comment"):
        if field not in Partners._fields:
            raise RuntimeError("Field res.partner.%s tidak tersedia" % field)

    tag_matches = Tag.search([("name", "=", TAG_NAME)])
    if len(tag_matches) > 1:
        raise RuntimeError("Tag konsinyasi duplikat di Odoo")

    planned, existing, review, invalid_phone = [], [], [], []
    two_phones = []
    stale_review_labels = []
    for line_no, row in enumerate(rows, start=2):
        name = clean(row["Display Name"])
        key = key_of(name)
        if not key:
            review.append((line_no, name, "nama kosong"))
            continue
        if counts[key] != 1:
            review.append((line_no, name, "nama duplikat dalam CSV"))
            continue
        if len(name) > 255:
            review.append((line_no, name[:65], "nama terlalu panjang"))
            continue

        xid = ModelData.search([("module", "=", XML_MODULE), ("name", "=", xml_name(key))])
        if len(xid) > 1:
            review.append((line_no, name, "External ID ambigu"))
            continue
        if xid:
            if xid.model != "res.partner" or not Partners.browse(xid.res_id).exists():
                review.append((line_no, name, "External ID tidak menunjuk mitra valid"))
            else:
                partner = Partners.browse(xid.res_id)
                if key_of(partner.name) != key:
                    review.append((line_no, name, "nama mitra di Odoo telah berubah"))
                else:
                    existing.append((line_no, name))
            continue

        # Jangan otomatis menggabungkan mitra beridentitas sama hanya dari nama.
        same_name = Partners.search([("name", "=", name)], limit=2)
        if same_name:
            review.append((line_no, name, "nama telah ada di Odoo; perlu mapping"))
            continue

        if reviewed_file:
            # Koreksi Feri di kolom hasil review lebih berwenang dari Phone asli.
            phone = clean(row["Telepon 1 (usulan)"])
            mobile = clean(row["Telepon 2 (usulan)"])
            unresolved = clean(row["Nomor asli perlu review"])
            if (phone and not phone_or_empty(phone)) or (mobile and not phone_or_empty(mobile)):
                review.append((line_no, name, "nomor usulan belum valid; perbaiki CSV"))
                continue
            if mobile and not phone:
                review.append((line_no, name, "Telepon 2 diisi tetapi Telepon 1 kosong"))
                continue
            if clean(row["Status impor"]) == "TAHAN DUPLIKAT":
                stale_review_labels.append((line_no, name))
        else:
            phone, mobile, unresolved = parse_phones(row["Phone"])

        if mobile:
            two_phones.append((line_no, name))
        if unresolved:
            invalid_phone.append((line_no, name, unresolved[:35]))
        planned.append((line_no, name, key, clean(row["Email"]), phone, mobile,
                        clean(row["Contact Address Complete"]),
                        bool(re.search(r"\bCS\s*$", name, flags=re.I)),
                        unresolved))

    print("DATABASE:", e.cr.dbname)
    print("MODE:", "APPLY" if applying else "PREVIEW (tanpa perubahan)")
    print("SUMBER:", "CSV REVIEW FERI (Telepon 1/2 manual)" if reviewed_file else "CSV vendor asli", "dari MITRA_YA_FILE")
    print("CSV:", len(rows), "kontak | TAMBAH:", len(planned),
          "SUDAH ADA:", len(existing), "REVIEW:", len(review))
    print("PENANDA CS:", sum(bool(p[-2]) for p in planned), "kontak baru")
    print("DUA NOMOR VALID (phone+ya_phone2):", len(two_phones))
    print("TELEPON TIDAK TERSTRUKTUR (disimpan di catatan):", len(invalid_phone))
    if reviewed_file:
        print("STATUS LAMA TAHAN DUPLIKAT TAPI NAMA KINI UNIK:", len(stale_review_labels))
        print("PENTING: status lama diabaikan; yang menentukan adalah nama duplikat pada CSV terbaru")
    for item in review[:40]:
        print("REVIEW BARIS %s | %s | %s" % item)
    for item in invalid_phone[:20]:
        print("TELEPON BARIS %s | %s | %s" % item)
    print("KEBIJAKAN: tidak menggabung berdasar nomor telepon; duplikat nama ditahan")
    print("KEBIJAKAN: supplier_rank=1; boleh juga menjadi customer kemudian")
    print("KEBIJAKAN: dua nomor valid dipisah; nomor ambigu tetap di catatan")
    print("TETAP: tidak mengubah kontak yang sudah ada; tidak membuat transaksi")
    if not applying:
        print("MITRA_PREVIEW_OK: tidak ada data diubah; gunakan YA_MITRA_APPLY=YES")
        return

    # Semua CREATE berada dalam transaksi yang sama; gagal => ROLLBACK.
    try:
        tag = tag_matches[:1]
        if any(p[-2] for p in planned) and not tag:
            tag = Tag.create({"name": TAG_NAME})
        for _line, name, key, email, phone, phone2, address, cs, raw_phone in planned:
            vals = {"name": name, "supplier_rank": 1,
                    "email": email or False, "phone": phone or False,
                    "ya_phone2": phone2 or False,
                    "street": address or False}
            if raw_phone:
                vals["comment"] = "Telepon dari sumber CSV (perlu verifikasi): " + raw_phone
            if cs:
                vals["category_id"] = [(4, tag.id)]
            record = Partners.create(vals)
            ModelData.create({"module": XML_MODULE, "name": xml_name(key),
                              "model": "res.partner", "res_id": record.id,
                              "noupdate": True})
        e.cr.commit()
    except Exception:
        e.cr.rollback()
        print("MITRA_IMPORT_FAILED: seluruh perubahan ROLLBACK")
        raise
    print("MITRA_IMPORT_SUCCESS: tambah=%d, cocok=%d, review_ditahan=%d; COMMIT selesai" %
          (len(planned), len(existing), len(review)))


main()
