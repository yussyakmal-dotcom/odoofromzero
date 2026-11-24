"""ROLLBACK UAT: mixed Paket 12114 + ordinary RO 11999 on ONE real slot.

Requires installed ya_package_store_ro 19.0.1.3.0 ONLY in
erp-yussyakmal-mrp-test, tested backup and free 2026-11-24 S1.
Uses real Published Planning, real BoMs, real store warehouses.
NO fake BoM/Planning/stock. Makes RO and kitchen MOs inside rollback.
This does NOT mark MOs Done, transfer to PCK, assemble Paket or deliver.
"""
assert env.cr.dbname == "erp-yussyakmal-mrp-test", "REFUSED: WRONG DB"
print("DATABASE:", env.cr.dbname)
print("MODE: MIXED_PAKET_ORDINARY_RO_ROLLBACK")

DATE, SLOT = "2026-11-24", "S1"
PACKAGE_SKU, COMPONENT_SKU = "12114", "11999"
Package = env["ya.package.store.ro"].sudo()
Ordinary = env["ya.store.ro"].sudo()
Batch = env["ya.packing.batch"].sudo()
Users = env["res.users"].sudo()
Product = env["product.product"].sudo()
Warehouses = env["stock.warehouse"].sudo()
Planning = env["ya.production.planning"].sudo()
Module = env["ir.module.module"].sudo().search([
    ("name", "=", "ya_package_store_ro")])
assert len(Module) == 1 and Module.state == "installed"
assert Module.installed_version == "19.0.1.3.0", "Unexpected installed Paket version"
assert not Batch.search_count([
    ("delivery_date", "=", DATE), ("slot", "=", SLOT)]), (
    "Real date-slot already used; do not change existing batch")
assert not Package.search_count([
    ("delivery_date", "=", DATE), ("slot", "=", SLOT)]), (
    "Paket RO already exists in test slot; do not overwrite")
assert not Ordinary.search_count([
    ("delivery_date", "=", DATE), ("slot", "=", SLOT),
    ("state", "=", "confirmed")]), (
    "Confirmed ordinary RO already exists in test slot; do not overwrite")

def unique_product(code):
    recs = Product.search([("default_code", "=", code)], limit=2)
    assert len(recs) == 1, "Missing or duplicated actual product %s" % code
    return recs[0]

def unique_store(code):
    recs = Warehouses.search([("code", "=", code)], limit=2)
    assert len(recs) == 1 and recs.active and recs.lot_stock_id, (
        "Missing/invalid test store " + code)
    return recs[0]

pkg = unique_product(PACKAGE_SKU)
component = unique_product(COMPONENT_SKU)
assert pkg.categ_id.complete_name == "All / Produk Jadi / Paket"
pkg_store = unique_store("T_BAN")
store_a = unique_store("T_KD")
store_b = unique_store("T_RAI")
assert len({pkg_store.id, store_a.id, store_b.id}) == 3
assert pkg_store.company_id == store_a.company_id == store_b.company_id

plannings = Planning.search([
    ("delivery_date", "=", DATE), ("slot", "=", SLOT),
    ("state", "=", "published")])
candidate_lines = plannings.mapped("line_ids").filtered(
    lambda line: line.product_id == component and line.max_capacity > 0)
assert len(candidate_lines) == 1, (
    "11999 must have exactly one real positive Published Planning line")
plan_line = candidate_lines[0]
plan = plan_line.planning_id
assert plan.kitchen_code == "PST", (
    "Actual kitchen routing for 11999 changed, review audit")
qty_base = plan_line.uom_id._compute_quantity(
    1, component.uom_id, round=False)
assert abs(qty_base - 1) < 1e-9, (
    "11999 Planning UoM no longer corresponds to whole single base unit")
kitchen_bom = plan_line._capacity_bom()
bom_output = kitchen_bom.product_uom_id._compute_quantity(
    kitchen_bom.product_qty, component.uom_id, round=False)
capacity = plan_line.uom_id._compute_quantity(
    plan_line.max_capacity, component.uom_id, round=False)
assert abs(bom_output - 7) < 1e-9 and abs(capacity - 7) < 1e-9, (
    "Expected real 11999 BoM output/Published Max 7 changed")
assert plan.workcenter_id and kitchen_bom.picking_type_id, (
    "Cannot run UAT without verified real kitchen routing")
print("UAT_REAL_PACKAGE:", pkg.default_code, pkg.display_name)
print("UAT_REAL_COMPONENT:", component.default_code,
      "KITCHEN:", plan.kitchen_code,
      "BOM:", kitchen_bom.id, "BOM_OUTPUT:", int(bom_output),
      "MAX:", int(capacity))
print("UAT_STORES:", pkg_store.code, store_a.code, store_b.code)
print("UAT_REAL_SLOT:", DATE, SLOT)

group_field = next(
    (name for name in ("group_ids", "groups_id") if name in Users._fields), None)
assert group_field, "Cannot identify res.users membership field"
creator_group = env.ref("ya_package_store_ro.group_ya_package_ro_creator")
packing_group = env.ref("ya_store_ro.group_ya_packing_admin")
manager_group = env.ref("mrp.group_mrp_manager")
logins = (
    "__ya_mixed_rollback_creator__@example.invalid",
    "__ya_mixed_rollback_packing__@example.invalid",
    "__ya_mixed_rollback_mrp_manager__@example.invalid",
)
assert not Users.search([("login", "in", list(logins))]), (
    "Temporary login already exists; refuse to touch real users")

def temp_user(group, label, login):
    user = Users.with_context(
        no_reset_password=True, mail_create_nosubscribe=True,
        tracking_disable=True,
    ).create({
        "name": label, "login": login,
        "company_id": pkg_store.company_id.id,
        "company_ids": [(6, 0, [pkg_store.company_id.id])],
        group_field: [(6, 0, [group.id])],
    })
    return user

class ExpectedRollback(Exception):
    pass

ro_ids = []
batch_id = None
mo_ids = []
success = False
try:
    with env.cr.savepoint():
        creator = temp_user(
            creator_group, "YA Mixed UAT Paket Creator", logins[0])
        packing = temp_user(
            packing_group, "YA Mixed UAT Packing", logins[1])
        manager = temp_user(
            manager_group, "YA Mixed UAT MRP Manager", logins[2])
        assert creator.has_group(
            "ya_package_store_ro.group_ya_package_ro_creator")
        assert packing.has_group("ya_store_ro.group_ya_packing_admin")
        assert manager.has_group("mrp.group_mrp_manager")
        print("MIXED_ROLLBACK_TEST_ROLE_USERS_READY")

        paket_ro = Package.with_user(creator).sudo().create({
            "delivery_date": DATE, "slot": SLOT,
            "store_warehouse_id": pkg_store.id,
            "line_ids": [(0, 0, {
                "product_id": pkg.id, "qty_requested": 1})],
        })
        ro_ids.append(("ya.package.store.ro", paket_ro.id))
        paket_ro.action_confirm()
        assert paket_ro.state == "confirmed"
        print("MIXED_PAKET_RO_CONFIRMED_PASS")

        regular = []
        for store, qty in ((store_a, 2), (store_b, 1)):
            ro = Ordinary.with_user(manager).sudo().create({
                "planning_id": plan.id,
                "store_warehouse_id": store.id,
                "line_ids": [(0, 0, {
                    "product_id": component.id,
                    "reference": component.default_code,
                    "qty_requested": qty,
                    "uom_id": plan_line.uom_id.id,
                })],
            })
            ro_ids.append(("ya.store.ro", ro.id))
            ro.action_confirm()
            assert ro.state == "confirmed"
            regular.append(ro)
        print("MIXED_ORDINARY_RO_CONFIRMED_PASS")

        wizard = env["ya.package.joint.slot.preview"].with_user(
            packing).sudo().create({"delivery_date": DATE, "slot": SLOT})
        wizard.action_preview()
        assert wizard.package_ro_count == 1
        assert wizard.ordinary_ro_count == 2
        assert wizard.source_digest
        print("MIXED_JOINT_PREVIEW_PASS")
        wizard.action_move_to_preproduction()

        batches = Batch.search([
            ("delivery_date", "=", DATE), ("slot", "=", SLOT)])
        assert len(batches) == 1
        batch = batches[0]
        batch_id = batch.id
        assert batch.state == "pre_production" and batch.ya_has_package
        assert set(batch.ro_ids.ids) == {r.id for r in regular}
        assert paket_ro in batch.ya_package_ro_ids
        assert all(ro.packing_batch_id == batch for ro in regular)
        line = batch.line_ids.filtered(lambda row: row.product_id == component)
        assert len(line) == 1
        assert line.ya_package_component_qty == 1
        assert line.qty_requested == 3
        assert line.qty_production == 7
        assert line.qty_surplus == 0, "11999 BoM extra belongs to ordering stores"
        allocations = batch.allocation_ids.filtered(
            lambda row: row.product_id == component)
        assert len(allocations) == 2
        actual = {a.store_warehouse_id.id: (
            a.qty_requested, a.qty_surplus, a.qty_shortage, a.qty_allocated)
            for a in allocations}
        expected = {
            store_a.id: (2, 2, 0, 4),
            store_b.id: (1, 1, 0, 2),
        }
        assert actual == expected, (actual, expected)
        assert line.ya_package_component_qty + sum(
            allocations.mapped("qty_allocated")) == line.qty_production
        assert len(batch.line_ids) == 3
        assert sum(batch.line_ids.mapped("qty_surplus")) == 10, (
            "Other two package-only kitchen components should leave 6+4"
            " unallocated for native internal transfer")
        print("MIXED_PACKAGE_FIRST_STORE_PRORATA_PASS")
        print("MIXED_STORE_ALLOCATION:", actual)
        print("MIXED_PCK_INTERNAL_TRANSFER_FALLBACK_QTY:",
              sum(batch.line_ids.mapped("qty_surplus")))

        as_packing = Batch.with_user(packing).sudo().browse(batch.id)
        as_packing.line_ids.action_generate_selected_mo()
        batch.invalidate_recordset()
        assert batch.state == "production_ok"
        mos = batch.line_ids.mapped("mo_id")
        mo_ids = mos.ids
        assert len(mos) == 3 and len(set(mos.mapped("product_id").ids)) == 3
        assert all(mo.state not in ("draft", "done", "cancel") for mo in mos)
        assert not batch.ya_package_assembly_mo_ids
        print("MIXED_NATIVE_KITCHEN_MO_CONFIRM_PASS")
        success = True
        raise ExpectedRollback()
except ExpectedRollback:
    print("ROLLBACK_EXPECTED_OK")
finally:
    env.cr.rollback()
env.invalidate_all()

assert success, "Mixed UAT failed; transaction was rolled back"
assert not Batch.search([("id", "=", batch_id)])
for model, rid in ro_ids:
    assert not env[model].sudo().search([("id", "=", rid)])
assert not env["mrp.production"].sudo().search([("id", "in", mo_ids)])
assert not Users.search([("login", "in", list(logins))])
print("MIXED_ROLLBACK_NO_RO_BATCH_MO_USERS_PERSISTED_PASS")
print("PACKAGE_JOINT_MIXED_STAGE_MO_ROLLBACK_PASS")
