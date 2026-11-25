"""Clone-only, read-only bridge audit for FINAL Packing allocation priorities.

OWNER RULE: confirmed YA SO first (direct + Paket kitchen components),
then frozen Paket RO assembly components, then ordinary RO store allocations.
Never edit original immutable RO snapshots. Never count PCK stock reserved
by an older picking as free. No SO/RO DO or stock movements here.

The audit inspects actual connected Odoo 19 model fields and sample rows,
including the protected SO capacity ledger, MO1 frozen allocation,
Paket assembly demands, and current PCK physical/reserved quantity.
It is a prerequisite to creating a separate final Packing ledger.
"""
from collections import Counter, defaultdict

DB = "erp-yussyakmal-mrp-test-RO_SO"
assert env.cr.dbname == DB, "STOP_WRONG_DATABASE"
env.cr.rollback()
env.cr.execute("SET TRANSACTION READ ONLY")
env.cr.execute("SHOW transaction_read_only")
assert env.cr.fetchone()[0] == "on", "STOP_SQL_READ_ONLY_NOT_CONFIRMED"

Mod = env["ir.module.module"].sudo().search([
    ("name", "=", "ya_sale_production_capacity")], limit=1)
assert Mod and Mod.state == "installed" and (
    Mod.installed_version == "19.0.1.1.3"
), "STOP_WRONG_INSTALLED_YA_SALES_MODULE"
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_PACKING_SO_PACKAGE_RO_PRIORITY_SCHEMA")
print("INSTALLED_YA_SALES_VERSION:", Mod.installed_version)

models = {
    "Packing batch": "ya.packing.batch",
    "Frozen RO allocation": "ya.packing.batch.allocation",
    "Package finished RO": "ya.packing.package.demand",
    "Package component RO": "ya.packing.package.component",
    "YA SO capacity ledger": "ya.sale.capacity.reservation",
    "YA sale order": "sale.order",
    "YA sale order line": "sale.order.line",
    "Native PCK stock": "stock.quant",
    "Native stock picking": "stock.picking",
    "MO2 release": "ya.sale.mo2.release.line",
}
wanted_fields = {
    "ya.packing.batch": [
        "delivery_date", "slot", "state", "allocation_ids",
        "ya_package_demand_ids", "ya_package_component_ids",
        "ya_fg_transfer_ids", "ya_store_delivery_ids",
        "ya_package_assembly_mo_ids",
    ],
    "ya.packing.batch.allocation": [
        "batch_id", "line_id", "ro_id", "product_id",
        "store_warehouse_id", "qty_requested", "qty_allocated",
        "qty_shortage", "qty_surplus",
    ],
    "ya.packing.package.demand": [
        "batch_id", "package_ro_id", "product_id",
        "store_warehouse_id", "qty_requested", "component_ids",
    ],
    "ya.packing.package.component": [
        "batch_id", "demand_id", "product_id", "source_kind",
        "kitchen_line_id", "uom_id", "qty_per_package", "qty_required",
    ],
    "ya.sale.capacity.reservation": [
        "order_id", "planning_line_id", "product_id",
        "delivery_date", "slot", "qty_required",
    ],
    "sale.order": [
        "ya_is_capacity_so", "ya_delivery_date", "ya_slot", "state",
        "order_line", "picking_ids", "warehouse_id",
    ],
    "sale.order.line": [
        "order_id", "product_id", "product_uom_qty",
        "product_uom_id", "display_type", "is_downpayment",
    ],
    "stock.picking": [
        "state", "origin", "ya_store_batch_id", "ya_fg_batch_id",
        "ya_mo2_fg_release_line_id", "move_ids",
    ],
    "stock.quant": [
        "product_id", "location_id", "company_id",
        "quantity", "reserved_quantity", "lot_id",
        "package_id", "owner_id",
    ],
    "ya.sale.mo2.release.line": [
        "mo_id", "product_id", "qty_mo2", "planning_line_id",
        "ya_mo2_fg_picking_ids",
    ],
}

for label, model_name in models.items():
    assert model_name in env, "STOP_MODEL_MISSING: %s" % model_name
    Model = env[model_name]
    result = {}
    for key in wanted_fields.get(model_name, []):
        f = Model._fields.get(key)
        result[key] = {
            "type": f.type if f else "MISSING",
            "comodel": f.comodel_name if f and f.type in (
                "many2one", "one2many", "many2many") else None,
        }
    print("SCHEMA:", label, model_name, result)

critical = {
    "ya.packing.batch": (
        "allocation_ids", "ya_package_demand_ids",
        "ya_package_component_ids", "ya_store_delivery_ids"),
    "ya.packing.batch.allocation": (
        "ro_id", "product_id", "store_warehouse_id",
        "qty_requested", "qty_allocated"),
    "ya.packing.package.component": (
        "product_id", "source_kind", "qty_required"),
    "ya.sale.capacity.reservation": (
        "order_id", "product_id", "qty_required"),
    "sale.order": ("ya_is_capacity_so", "order_line", "picking_ids"),
    "stock.quant": ("quantity", "reserved_quantity"),
}
for model, keys in critical.items():
    missing = [k for k in keys if k not in env[model]._fields]
    assert not missing, "STOP_CRITICAL_PACKING_SCHEMA_MISSING: %s/%s" % (
        model, missing)

Batch = env["ya.packing.batch"].sudo()
SO = env["sale.order"].sudo()
Reservations = env["ya.sale.capacity.reservation"].sudo()
Allocation = env["ya.packing.batch.allocation"].sudo()
PackageDemand = env["ya.packing.package.demand"].sudo()
PackageComponent = env["ya.packing.package.component"].sudo()
Picking = env["stock.picking"].sudo()

print("TOTALS:", {
    "packing_batches": Batch.search_count([]),
    "frozen_ro_allocation_rows": Allocation.search_count([]),
    "frozen_package_demand_rows": PackageDemand.search_count([]),
    "frozen_package_component_rows": PackageComponent.search_count([]),
    "confirmed_ya_so": SO.search_count([
        ("ya_is_capacity_so", "=", True),
        ("state", "in", ("sale", "done")),
    ]),
    "protected_so_capacity_rows": Reservations.search_count([]),
    "native_mo2_releases_persisted":
        env["ya.sale.mo2.release.line"].sudo().search_count([]),
    "fg_legacy_pickings": Picking.search_count([
        ("ya_fg_batch_id", "!=", False)]),
    "fg_mo2_pickings": Picking.search_count([
        ("ya_mo2_fg_release_line_id", "!=", False)]),
})

sample_batches = Batch.search(
    [], order="delivery_date desc,slot,id", limit=3
)
for batch in sample_batches:
    ro_allocation = defaultdict(lambda: {
        "requested": 0, "allocated": 0, "shortage": 0, "surplus": 0
    })
    for item in batch.allocation_ids:
        v = ro_allocation[item.product_id.id]
        v["requested"] += item.qty_requested
        v["allocated"] += item.qty_allocated
        v["shortage"] += item.qty_shortage
        v["surplus"] += item.qty_surplus
    kitchen_component = defaultdict(float)
    pck_component = defaultdict(float)
    for item in batch.ya_package_component_ids:
        bucket = (kitchen_component if item.source_kind == "kitchen"
                  else pck_component)
        bucket[item.product_id.id] += item.qty_required
    print("BATCH_SAMPLE:", {
        "id": batch.id, "date": str(batch.delivery_date),
        "slot": batch.slot, "state": batch.state,
        "mo1_rows": len(batch.line_ids),
        "frozen_ro_allocations": len(batch.allocation_ids),
        "ro_skus": len(ro_allocation),
        "frozen_package_finished_rows": len(batch.ya_package_demand_ids),
        "package_component_rows": len(batch.ya_package_component_ids),
        "package_kitchen_component_skus": len(kitchen_component),
        "package_pck_stock_component_skus": len(pck_component),
        "fg_legacy_pickings": len(batch.ya_fg_transfer_ids),
        "package_assembly_mos": len(batch.ya_package_assembly_mo_ids),
        "store_do": len(batch.ya_store_delivery_ids),
        "frozen_ro_sku_example": list(sorted(ro_allocation.items()))[:3],
        "package_kitchen_component_example":
            list(sorted(kitchen_component.items()))[:3],
    })
    confirmed_so = SO.search([
        ("ya_is_capacity_so", "=", True),
        ("ya_delivery_date", "=", batch.delivery_date),
        ("ya_slot", "=", batch.slot),
        ("state", "in", ("sale", "done")),
    ])
    protected_rows = Reservations.search([
        ("delivery_date", "=", batch.delivery_date),
        ("slot", "=", batch.slot),
    ])
    print("SLOT_SO_REAL_DATA:", {
        "batch": batch.id, "confirmed_so_count": len(confirmed_so),
        "protected_kitchen_capacity_rows": len(protected_rows),
        "protected_qty_per_kitchen_product": list(sorted(
            Counter({
                pid: sum(row.qty_required
                    for row in protected_rows
                    if row.product_id.id == pid)
                for pid in protected_rows.mapped("product_id").ids
            }).items()
        ))[:8],
    })

PCK = env["stock.warehouse"].sudo().search([
    ("code", "=", "PCK"), ("company_id", "=", 1)])
assert len(PCK) == 1 and PCK.lot_stock_id, (
    "STOP_PCK_WAREHOUSE_NOT_UNIQUE_COMPANY1"
)
quant = env["stock.quant"].sudo().search([
    ("company_id", "=", 1), ("product_id", "=", 1584),
    ("location_id", "=", PCK.lot_stock_id.id),
    ("lot_id", "=", False), ("package_id", "=", False),
    ("owner_id", "=", False),
])
physical = sum(quant.mapped("quantity"))
reserved = sum(quant.mapped("reserved_quantity"))
print("EXAMPLE_SKU10028_PCK_STOCK:", {
    "product_id": 1584, "pck_stock_location_id": PCK.lot_stock_id.id,
    "physical": physical, "reserved": reserved,
    "free": physical - reserved,
})
assert physical >= 0 and reserved >= 0, "STOP_INVALID_PCK_QUANT"
print("OWNER_PRIORITY_POLICY: SO direct and SO Paket kitchen components,"
      " then RO Paket assembly components, then frozen ordinary RO demand")
print("IMPORTANT: protected SO capacity is NOT a physical stock reservation")
print("IMPORTANT: frozen RO allocation is a planning snapshot, not final DO")
print("IMPORTANT: PCK free stock excludes existing reserved stock")
print("IMPORTANT: package final SKU and kitchen components are distinct buckets")
print("IMPORTANT: original Fase1 package DO is restricted to former Fase1 test DB")
print("READ_ONLY_FASE2_PACKING_SO_PRIORITY_SCHEMA_AUDIT_PASS")
print("NO_PACKING_MO_OR_STOCK_MUTATION")
env.cr.rollback()
