"""Fase 2 custom SO integration preflight. Read-only Odoo shell, TEST DB only.

Usage:
  sudo -u odoo19 /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin shell \\
    -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test --no-http \\
    < script/audit_fase2_sale_capacity_schema_readonly_ya.py

No create, write, upgrade, Stock adjustment, or commit.
"""
assert env.cr.dbname == "erp-yussyakmal-mrp-test", "REFUSED: MRP TEST DB ONLY"

print("DATABASE:", env.cr.dbname)
print("MODE: FASE2_SALE_CAPACITY_SCHEMA_READ_ONLY")

Module = env["ir.module.module"].sudo()
names = [
    "sale", "sale_stock", "mrp", "ya_production_planning",
    "ya_store_ro", "ya_package_store_ro", "ya_workflow_navigation",
    "ya_material_requirement", "ya_packing_store_delivery",
]
for name in names:
    mods = Module.search([("name", "=", name)], limit=1)
    print("MODULE:", name, mods.state if mods else "NOT_FOUND",
          mods.installed_version if mods else "N/A")

model_fields = {
    "sale.order": [
        "name", "state", "order_line", "date_order", "commitment_date",
        "expected_date", "warehouse_id", "picking_ids", "partner_id",
        "company_id", "client_order_ref",
    ],
    "sale.order.line": [
        "order_id", "product_id", "product_uom_qty", "product_uom",
        "qty_delivered", "qty_invoiced",
    ],
    "ya.production.planning": [
        "delivery_date", "slot", "kitchen_code", "state",
        "workcenter_id", "line_ids",
    ],
    "ya.production.planning.line": [
        "planning_id", "product_id", "max_capacity", "bom_id",
        "uom_id",
    ],
    "ya.packing.batch": [
        "delivery_date", "slot", "state", "line_ids", "allocation_ids",
        "ro_ids",
    ],
    "ya.packing.batch.line": [
        "batch_id", "planning_id", "product_id", "qty_production",
        "mo_id", "max_capacity", "bom_id",
    ],
    "ya.packing.batch.allocation": [
        "batch_id", "ro_id", "product_id", "qty_requested",
        "qty_allocated", "qty_shortage", "qty_surplus",
    ],
    "mrp.production": [
        "product_id", "product_qty", "bom_id", "state",
        "ya_packing_batch_line_id", "ya_package_assembly_batch_id",
    ],
}
for model_name, fields in model_fields.items():
    if model_name not in env.registry:
        print("MODEL_NOT_FOUND:", model_name)
        continue
    model = env[model_name].sudo()
    print("MODEL_FIELDS:", model_name,
          {field: field in model._fields for field in fields})

Planning = env["ya.production.planning"].sudo()
PlanningLine = env["ya.production.planning.line"].sudo()
published = Planning.search([("state", "=", "published")])
print("PUBLISHED_PLANNING_COUNT:", len(published))
print("PUBLISHED_PLANNING_LINE_COUNT:",
      PlanningLine.search_count([("planning_id", "in", published.ids)]))
print("PUBLISHED_SCHEDULE_SAMPLE:",
      sorted({(str(p.delivery_date), p.slot) for p in published})[:10])

so = env["sale.order"].sudo()
print("STANDARD_SO_DRAFT_COUNT:", so.search_count([("state", "=", "draft")]))
print("STANDARD_SO_CONFIRMED_COUNT:",
      so.search_count([("state", "in", ["sale", "done"])]))
print("FASE2_READ_ONLY_SCHEMA_AUDIT_PASS")
