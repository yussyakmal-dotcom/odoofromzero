"""Read-only focused check: manufacturing BoM operations and Work Centers.
ONLY erp-yussyakmal-mrp-test. NO writes, no imports, no stock moves.
Follow up from prior test where missing registry model returned None, not zero.
"""
from collections import Counter, defaultdict

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "REFUSED: wrong database"

TARGET_CODES = ("PST", "SL", "GRG", "LP", "CKS", "CKL", "ROTI", "TART", "JP", "TLV", "ASN", "LG")
B = env["mrp.bom"].sudo().with_context(active_test=False)
W = env["mrp.workcenter"].sudo().with_context(active_test=False)
boms = B.search([("type", "=", "normal")])
centers = W.search([], order="code, id")
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_BOM_OPERATION_WORKCENTER")
print("WORKCENTERS_ALL:", [(c.id, c.code, c.name, c.active) for c in centers])
print("NOT_IN_SUPPLIED_LIST:", [(c.code, c.name) for c in centers if c.code not in TARGET_CODES])
print("BOM_TOTAL:", len(boms))
print("BOM_OPERATION_FIELD_PRESENT:", "operation_ids" in B._fields)

if "operation_ids" not in B._fields:
    print("NO_OPERATION_FIELD_CANNOT_DETERMINE_RELATION")
else:
    op_count = Counter()
    wc_count = Counter()
    pair_count = Counter()
    no_op = Counter()
    no_wc = []
    multiple_wc = []
    link_examples = []
    for bom in boms:
        pt = bom.picking_type_id
        wh = pt.warehouse_id if pt else False
        warehouse = wh.name if wh else "(NO WAREHOUSE)"
        ops = bom.operation_ids
        if not ops:
            no_op[warehouse] += 1
            continue
        op_count[warehouse] += len(ops)
        wc_ids = set()
        for op in ops:
            center = op.workcenter_id if "workcenter_id" in op._fields else False
            if not center:
                no_wc.append((bom.product_id.default_code, bom.code, warehouse, op.id))
                continue
            wc_ids.add(center.id)
            wc_count[(center.code, center.name)] += 1
            pair_count[(warehouse, center.code, center.name)] += 1
            if len(link_examples) < 12:
                link_examples.append((bom.product_id.default_code, warehouse, center.code, center.name))
        if len(wc_ids) > 1:
            multiple_wc.append((bom.product_id.default_code, warehouse, sorted(wc_ids)))
    print("BOMS_WITHOUT_OPERATIONS:", sum(no_op.values()))
    print("BOMS_WITHOUT_OPERATIONS_BY_WAREHOUSE:", sorted(no_op.items()))
    print("TOTAL_OPERATIONS_RELATED_TO_BOMS:", sum(op_count.values()))
    print("OPERATIONS_WITHOUT_WORKCENTER:", len(no_wc))
    print("OPERATIONS_WITHOUT_WORKCENTER_EXAMPLES:", no_wc[:8])
    print("BOMS_WITH_MULTIPLE_WORKCENTERS:", len(multiple_wc))
    print("MULTIPLE_WORKCENTER_SAMPLES:", multiple_wc[:8])
    print("WORKCENTER_OPERATION_COUNTS:", sorted(wc_count.items()))
    print("WAREHOUSE_TO_WORKCENTER_OPERATION_COUNTS:", sorted(pair_count.items()))
    print("LINK_SAMPLES:", link_examples)
    if sum(op_count.values()) == 0:
        print("CONCLUSION: NO DIRECT OPERATION LINKS CURRENTLY STORED; matching name is not a verified foreign-key relation.")
    else:
        print("CONCLUSION: OPERATION LINKS FOUND; review warehouse->workcenter pair counts before deciding any master data mapping.")
print("READ_ONLY_BOM_OPERATION_CHECK_OK")
