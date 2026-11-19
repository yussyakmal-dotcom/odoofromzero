"""Audit read-only 30 warehouse, lokasi stock dan operation types Odoo 19.

Jalankan dengan odoo-bin shell -d erp-yussyakmal --no-http.
Hasil hanya ke stdout; tidak ada write()/create()/commit().
"""

import csv
from collections import Counter
from pathlib import Path


def main():
    odoo_env = globals().get("env")
    if odoo_env is None or odoo_env.cr.dbname != "erp-yussyakmal":
        raise RuntimeError("Jalankan lewat Odoo shell pada erp-yussyakmal")

    source = Path("MASTER CONFIG/Master_Gudang_Import.csv")
    with source.open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 30:
        raise RuntimeError("Master Gudang bukan 30 baris")

    Warehouse = odoo_env["stock.warehouse"].sudo()
    Location = odoo_env["stock.location"].sudo()
    PickingType = odoo_env["stock.picking.type"].sudo()
    warehouses = Warehouse.search([])
    locations = Location.search([])
    picking_types = PickingType.search([])
    codes = Counter(w.code for w in warehouses)
    expected = {row["Short Name"].strip(): row["Warehouse"].strip() for row in rows}

    issues = []
    if len(warehouses) != 30:
        issues.append("Jumlah warehouse database %s, master 30" % len(warehouses))
    unknown = sorted(set(codes) - set(expected))
    missing = sorted(set(expected) - set(codes))
    if unknown:
        issues.append("Kode warehouse di luar master: " + ", ".join(unknown))
    if missing:
        issues.append("Kode warehouse belum ada: " + ", ".join(missing))
    if any(count != 1 for count in codes.values()):
        issues.append("Ada kode warehouse duplikat")

    print("DATABASE:", odoo_env.cr.dbname)
    print("MODE: AUDIT READ-ONLY")
    print("WAREHOUSE:", len(warehouses), "| MASTER:", len(rows))
    print("TOTAL STOCK LOCATION:", len(locations))
    print("TOTAL OPERATION TYPE:", len(picking_types))
    print("OPERATION TYPE PER JENIS:", dict(sorted(Counter(t.code for t in picking_types).items())))
    print("=" * 72)

    for row in rows:
        code, name = row["Short Name"].strip(), row["Warehouse"].strip()
        record = warehouses.filtered(lambda w: w.code == code)
        if len(record) != 1:
            print("GUDANG: %s | %s | MISSING/DUPLICATE" % (code, name))
            continue
        wh = record[0]
        if wh.name != name:
            issues.append("Nama warehouse %s berbeda: %r (master %r)" % (code, wh.name, name))
        stock = wh.lot_stock_id if "lot_stock_id" in wh._fields else Location.browse([])
        expected_location = code + "/Stock"
        actual_location = stock.complete_name if stock and "complete_name" in stock._fields else "(tidak tersedia)"
        if not stock or stock.usage != "internal":
            issues.append("Lokasi stok internal tidak ditemukan: " + code)
        # Lengkapnya jalur lokasi dapat memiliki prefix selain CODE/Stock.
        if stock and not actual_location.endswith(expected_location):
            issues.append("Lokasi stok %s: %s (diharapkan akhiran %s)" % (code, actual_location, expected_location))

        types = picking_types.filtered(lambda t: "warehouse_id" in t._fields and t.warehouse_id.id == wh.id)
        type_counts = Counter(t.code for t in types)
        print("GUDANG: %s | %s | STOCK: %s | OPERASI: %d %s" %
              (code, wh.name, actual_location, len(types), dict(sorted(type_counts.items()))))
        if not types:
            issues.append("Belum ada operation type untuk " + code)
        for t in types.sorted(lambda x: (x.code, x.name, x.id)):
            src = t.default_location_src_id.complete_name if "default_location_src_id" in t._fields and t.default_location_src_id else "-"
            dst = t.default_location_dest_id.complete_name if "default_location_dest_id" in t._fields and t.default_location_dest_id else "-"
            seq = t.sequence_code if "sequence_code" in t._fields else "-"
            active = t.active if "active" in t._fields else True
            print("  TYPE: id=%s | %s | %s | src=%s | dst=%s | sequence=%s | active=%s" %
                  (t.id, t.code, t.name, src, dst, seq, active))

    print("=" * 72)
    print("AUDIT_ISSUES:", len(issues))
    for item in issues:
        print("  PERIKSA:", item)
    print("AUDIT_GUDANG_COMPLETE: tidak ada perubahan database.")


main()
