"""READ ONLY registry check after installing Paket addon in TEST DB only.

This script does NOT create RO, MO, snapshot, stock, DO or change settings.
Check results before any rollback E2E test or GUI use.
"""
assert env.cr.dbname == "erp-yussyakmal-mrp-test", "REFUSED: WRONG DB"
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_PAKET_ODOO_REGISTRY")

m = env["ir.module.module"].sudo().search([
    ("name", "=", "ya_package_store_ro"),
])
assert len(m) == 1 and m.state == "installed", "Paket addon not installed"
assert m.installed_version == "19.0.1.3.0", (
    "Expected Paket addon version 19.0.1.3.0, found %s" %
    m.installed_version
)
print("MODULE:", m.name, m.state, m.installed_version)
expected = {
    "ya.package.store.ro": ["store_warehouse_id", "delivery_date",
                            "slot", "line_ids", "state"],
    "ya.package.store.ro.line": ["ro_id", "product_id", "qty_requested"],
    "ya.package.joint.slot.preview": [
        "delivery_date", "slot", "source_digest", "accept_shortage",
    ],
    "ya.packing.batch": [
        "ya_has_package", "ya_package_ro_ids",
        "ya_package_demand_ids", "ya_package_component_ids",
        "ya_package_assembly_mo_ids",
    ],
    "ya.packing.batch.line": [
        "ya_package_component_qty", "ya_kitchen_bom_output",
    ],
    "ya.packing.package.demand": [
        "batch_id", "package_ro_id", "product_id",
        "store_warehouse_id", "bom_id", "qty_requested",
    ],
    "ya.packing.package.component": [
        "batch_id", "demand_id", "product_id", "source_kind",
        "kitchen_line_id", "qty_per_package", "qty_required",
    ],
    "mrp.production": ["ya_package_assembly_batch_id"],
}
for model, fields in expected.items():
    obj = env[model]
    missing = [name for name in fields if name not in obj._fields]
    assert not missing, "Missing %s model fields: %s" % (model, missing)
    print("MODEL_REGISTRY:", model, "OK")
for ref in [
    "ya_package_store_ro.view_ya_package_joint_slot_preview_form",
    "ya_package_store_ro.view_ya_joint_packing_batch_form",
    "ya_package_store_ro.view_ya_joint_packing_preproduction_list",
    "ya_package_store_ro.action_ya_package_joint_slot_preview",
]:
    record = env.ref(ref, raise_if_not_found=False)
    assert record, "Missing installed XML data: %s" % ref
    print("ODOO_XML_RECORD:", ref, record.id)

pck = env["stock.warehouse"].sudo().search([("code", "=", "PCK")])
assert len(pck) == 1 and pck.manu_type_id.id == 279, (
    "Real PCK Manufacturing operation type 279 changed"
)
assert pck.manu_type_id.default_location_src_id == pck.lot_stock_id
assert pck.manu_type_id.default_location_dest_id == pck.lot_stock_id
print("PCK_MANUFACTURING_ROUTE_PASS")

batch = env["ya.packing.batch"].sudo().search([
    ("delivery_date", "=", "2026-11-24"), ("slot", "=", "S1"),
])
print("UAT_SLOT_BATCH_COUNT:", len(batch))
if batch:
    print("UAT_SLOT_OCCUPIED: do not run stage/rollback test on this slot")
else:
    print("UAT_SLOT_AVAILABLE: 2026-11-24 S1")
print("PACKAGE_TESTDB_REGISTRY_READONLY_PASS")
