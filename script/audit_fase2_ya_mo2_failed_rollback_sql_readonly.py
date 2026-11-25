"""Strict SQL-only post-failure audit for synthetic MO2 native stock rollback.

ONLY clone erp-yussyakmal-mrp-test-RO_SO. Fresh Odoo shell transaction,
PostgreSQL READ ONLY after resetting shell start transaction.
This must run BEFORE any rerun of the stock-mutating rollback test.

Last failed fixture (25 Nov):
  batch22; MO1 99 MO2 100; SO 34,35,36;
  finalization 6; CDC picking76; FG draft picking77.
Suspected post-rollback mismatch product2465 (SKU11111) location5.
Do NOT fix quants or infer corruption just from ORM-cache assertion.
"""
DB = "erp-yussyakmal-mrp-test-RO_SO"
assert env.cr.dbname == DB, "STOP_WRONG_DATABASE"
env.cr.rollback()  # new transaction; this diagnostic has no prior writes
env.cr.execute("SET TRANSACTION READ ONLY")
env.cr.execute("SHOW transaction_read_only")
assert env.cr.fetchone()[0] == "on", "STOP_CANNOT_PROVE_READ_ONLY"

print("DATABASE:", env.cr.dbname)
print("MODE: INDEPENDENT_SQL_READ_ONLY_ROLLBACK_PERSISTENCE_AUDIT")
print("TRANSACTION_READ_ONLY: ON")


def rows(query, args=()):
    env.cr.execute(query, args)
    return env.cr.fetchall()


warehouses = rows(
    """SELECT code, id, lot_stock_id, company_id
       FROM stock_warehouse
       WHERE code IN ('CDC', 'GRG', 'PCK') AND company_id = 1
       ORDER BY code"""
)
print("WAREHOUSES:", warehouses)
assert len(warehouses) == 3, (
    "STOP_EXPECTED_UNIQUE_CDC_GRG_PCK_IN_TEST_COMPANY"
)
locations = {rec[0]: rec[2] for rec in warehouses}
assert all(locations.values()), "STOP_MISSING_WAREHOUSE_STOCK_LOCATIONS"
location_ids = sorted(set([5] + list(locations.values())))
print("LOCATIONS_UNDER_AUDIT:", rows(
    "SELECT id, name, usage, location_id, company_id "
    "FROM stock_location WHERE id = ANY(%s::integer[]) ORDER BY id",
    (location_ids,),
))

# These are the same untracked products from published BoM1154, plus output.
products = {
    190: "10547 / Gram", 317: "10840 / Gram",
    482: "11289 / Pcs", 2465: "11111 / Pcs",
    1584: "10028 / Finished Pcs",
}
product_ids = list(products)
quant_rows = rows(
    """SELECT id, product_id, location_id, company_id, quantity,
              reserved_quantity, lot_id, package_id, owner_id
       FROM stock_quant
       WHERE company_id = 1
         AND product_id = ANY(%s::integer[])
         AND location_id = ANY(%s::integer[])
       ORDER BY product_id, location_id, id""",
    (product_ids, location_ids),
)
for rec in quant_rows:
    print("PERSISTED_QUANT_ROW:", {
        "id": rec[0], "product": rec[1], "sku": products[rec[1]],
        "location": rec[2], "company": rec[3],
        "physical": rec[4], "reserved": rec[5],
        "lot": rec[6], "package": rec[7], "owner": rec[8],
    })
for pid in product_ids:
    for label in ("CDC", "GRG", "PCK"):
        loc = locations[label]
        matching = [
            r for r in quant_rows if r[1] == pid and r[2] == loc
            and r[6] is None and r[7] is None and r[8] is None
        ]
        physical = sum(r[4] for r in matching)
        reserved = sum(r[5] for r in matching)
        print("PERSISTED_EXACT_STOCK:", label, pid, products[pid],
              "PHYSICAL:", physical, "RESERVED:", reserved,
              "FREE:", physical - reserved, "QUANT_ROWS:", len(matching))

target = [r for r in quant_rows
          if r[1] == 2465 and r[2] == 5
          and r[6] is None and r[7] is None and r[8] is None]
print("FOCUS_SKU11111_LOCATION5:", {
    "physical": sum(r[4] for r in target),
    "reserved": sum(r[5] for r in target),
    "row_count": len(target),
    "note": "Compare with previous read-only reference (900 / 0 at CDC); "
            "not a transaction-time baseline if other writers were active",
})

# Check for leftovers from exact synthetic IDs; DB sequences continue after
# rollback (gaps in IDs do NOT indicate committed synthetic records).
checks = (
    ("SYNTHETIC_MO", "mrp_production", "id = ANY(%s::integer[])", ([99, 100],)),
    ("SYNTHETIC_PICKING", "stock_picking", "id = ANY(%s::integer[])", ([76, 77],)),
    ("SYNTHETIC_SALE_ORDER", "sale_order", "id = ANY(%s::integer[])", ([34, 35, 36],)),
    ("SYNTHETIC_PACKING_BATCH", "ya_packing_batch", "id = %s", (22,)),
    ("SYNTHETIC_FINALIZATION", "ya_sale_mo2_finalization", "id = %s", (6,)),
    ("SYNTHETIC_MO2_LINES", "ya_sale_mo2_release_line", "finalization_id = %s", (6,)),
)
persisted_any = False
for label, table, criterion, args in checks:
    found = rows(
        "SELECT COUNT(*) FROM %s WHERE %s" % (table, criterion), args
    )[0][0]
    print("PERSISTED_TEST_OBJECTS:", label, found)
    if found:
        persisted_any = True

native_moves = rows(
    """SELECT id, state, product_id, picking_id,
              raw_material_production_id, production_id
       FROM stock_move
       WHERE picking_id = ANY(%s::integer[])
          OR raw_material_production_id = ANY(%s::integer[])
          OR production_id = ANY(%s::integer[])
       ORDER BY id""",
    ([76, 77], [99, 100], [99, 100]),
)
print("PERSISTED_SYNTHETIC_STOCK_MOVES:", native_moves)
if native_moves:
    persisted_any = True

if persisted_any:
    print("STOP_PERSISTED_SYNTHETIC_RECORDS_FOUND_REVIEW_BEFORE_RERUN")
else:
    print("INDEPENDENT_SQL_SYNTHETIC_OBJECTS_ABSENT_PASS")

print("NOTE: Exact quant comparison to test-time baseline still required.")
print("NOTE: This separate SQL snapshot cannot establish causality of stock")
print("      changes without baseline and concurrency evidence.")
print("READ_ONLY_POST_FAILURE_MO2_STOCK_DIAGNOSTIC_COMPLETE")
print("NO_ORM_WRITES_NO_STOCK_MUTATIONS")
env.cr.rollback()
