"""READ-ONLY: why confirmed Packing MOs have no Work Orders in Odoo 19.

Run via odoo-bin shell in erp-yussyakmal-mrp-test ONLY.
Reads BoM Operations, native MO WO links, Work Centers, module flags.
NO writes, Plan, Confirm, stock reservation or state changes.
"""
from collections import Counter

EXPECTED_DB = "erp-yussyakmal-mrp-test"
assert env.cr.dbname == EXPECTED_DB, "REFUSED: wrong DB"

BATCH_DATE = "2026-11-27"
SLOT = "S1"
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_MO_BOM_OPERATIONS_WORKORDERS")
Module = env["ir.module.module"].sudo()
for name in ("mrp", "mrp_workorder", "ya_store_ro", "ya_material_requirement"):
    module = Module.search([("name", "=", name)], limit=1)
    print("MODULE:", name, "|", module.state if module else "NOT_FOUND",
          "| version:", module.installed_version if module else "")

registry = env.registry.models
print("MODEL_EXISTS:", {
    m: (m in registry)
    for m in ("mrp.production", "mrp.bom", "mrp.workcenter",
              "mrp.routing.workcenter", "mrp.workorder", "ya.packing.batch")
})
if "mrp.routing.workcenter" in registry:
    Operation = env["mrp.routing.workcenter"].sudo()
    print("BOM_OPERATIONS_IN_DATABASE:", Operation.search_count([]))
else:
    Operation = None
    print("WARNING: Operation model missing; cannot generate native WO.")

print("WORKCENTERS_IN_DATABASE:", env["mrp.workcenter"].sudo().search_count([]))
batch = env["ya.packing.batch"].sudo().search([
    ("delivery_date", "=", BATCH_DATE),
    ("slot", "=", SLOT),
    ("state", "=", "production_ok"),
])
print("BATCH_COUNT:", len(batch))
if len(batch) != 1:
    print("STOP: expected exactly one Packing production batch")
else:
    batch = batch[0]
    mos = batch.line_ids.mapped("mo_id")
    print("BATCH:", batch.name, "| MO_COUNT:", len(mos))
    totals = Counter()
    for mo in mos.sorted(lambda m: m.name):
        bom = mo.bom_id
        operations = bom.operation_ids if bom else env["mrp.routing.workcenter"]
        wos = mo.workorder_ids
        totals["mo"] += 1
        totals["mos_with_bom_operations"] += bool(operations)
        totals["mos_with_wo"] += bool(wos)
        totals["bom_operation_refs"] += len(operations)
        totals["wo_refs"] += len(wos)
        print("MO:", mo.name,
              "| product:", mo.product_id.display_name,
              "| state:", mo.state,
              "| components:", mo.components_availability,
              "| bom:", bom.display_name if bom else "(NONE)",
              "| bom_operations:", len(operations),
              "| workorders:", len(wos),
              "| is_planned:", mo.is_planned)
        for op in operations[:5]:
            print("    BOM_OPERATION:", op.name,
                  "| workcenter:", op.workcenter_id.display_name,
                  "| id:", op.id)
        for wo in wos[:5]:
            print("    WORKORDER:", wo.display_name,
                  "| state:", wo.state,
                  "| workcenter:", wo.workcenter_id.display_name,
                  "| operation:", wo.operation_id.display_name)
    print("TOTALS:", dict(totals))
print("READ_ONLY_MO_BOM_OPERATIONS_AUDIT_OK")
