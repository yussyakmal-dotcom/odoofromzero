"""Read-only narrow comparison: 12 supplied Work Centers versus BoM kitchen warehouses.
Run ONLY in erp-yussyakmal-mrp-test via odoo-bin shell.
No writes, imports, journal entries, stock moves, or schema changes.
Names are suggestions, NOT verified business mappings.
"""
from collections import Counter

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "REFUSED: wrong database"
TARGETS = [
    ("PST", "Pastry"),
    ("SL", "Sultan & Lemper"),
    ("GRG", "Gorengan"),
    ("LP", "La Passion"),
    ("CKS", "Cake Slice"),
    ("CKL", "Cake Loyang"),
    ("ROTI", "Roti"),
    ("TART", "Tart"),
    ("JP", "Jajan Pasar"),
    ("TLV", "Tart La Vissione"),
    ("ASN", "Asin"),
    ("LG", "Legit"),
]
def norm(s):
    return " ".join(str(s or "").casefold().replace("&", "and").split())

wc_model = env["mrp.workcenter"].sudo().with_context(active_test=False)
bom_model = env["mrp.bom"].sudo().with_context(active_test=False)
operation_model = env["mrp.routing.workcenter"].sudo() if "mrp.routing.workcenter" in env.registry.models else None

print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_WORKCENTER_VS_BOM_KITCHEN")
print("SUPPLIED_WORKCENTERS:", len(TARGETS))
print("ACTUAL_WORKCENTER_TOTAL:", wc_model.search_count([]))
print("BOM_TOTAL:", bom_model.search_count([]))
print("WORKCENTER_SCHEMA:", {k: (str(wc_model._fields[k].type) if k in wc_model._fields else "ABSENT") for k in ("name","code","active","resource_id")})
print("BOM_OPERATION_LINK_FIELD:", "operation_ids" in bom_model._fields)

boms = bom_model.search([("type", "=", "normal")])
by_warehouse = Counter()
for bom in boms:
    pt = bom.picking_type_id
    wh = pt.warehouse_id if pt else False
    by_warehouse[wh.name if wh else "(NO WAREHOUSE)"] += 1

ops_count = operation_model.search_count([]) if operation_model else None
print("BO_M_OPERATIONS_COUNT:", ops_count)
print("BOM_WAREHOUSE_COUNTS:", sorted(by_warehouse.items()))
print("NOTE: zero BoM operations means no direct BoM -> Work Center relation in current data.")

for code, supplied_name in TARGETS:
    matches = wc_model.search([("code", "=", code)])
    if not matches:
        print("TARGET:", code, "|", supplied_name, "| WORKCENTER_NOT_FOUND")
        continue
    if len(matches) != 1:
        print("TARGET:", code, "|", supplied_name, "| DUPLICATE_CODE:", len(matches))
        continue
    wc = matches[0]
    exact_name = [name for name in by_warehouse if norm(name) == norm(wc.name)]
    prefixed_name = [name for name in by_warehouse if norm(name) == norm("Dapur " + wc.name)]
    names = sorted(set(exact_name + prefixed_name))
    print("TARGET:", code, "|", supplied_name, "| DB_WORKCENTER:", wc.name,
          "| CODE_MATCH:", wc.code == code, "| NAME_MATCH:", norm(wc.name) == norm(supplied_name),
          "| EXACT_OR_DAPUR_PREFIX_WAREHOUSE_CANDIDATES:", names,
          "| CANDIDATE_BOMS:", sum(by_warehouse[x] for x in names),
          "| MATCH_IS_NAME_ONLY_NOT_RELATION")
print("READ_ONLY_WORKCENTER_BOM_KITCHEN_CHECK_OK")
