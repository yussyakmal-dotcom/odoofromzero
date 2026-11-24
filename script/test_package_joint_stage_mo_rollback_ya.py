"""ROLLBACK E2E — real Paket RO 12114 -> joint Pre Produksi -> kitchen MOs.

Only AFTER installing ya_package_store_ro on erp-yussyakmal-mrp-test,
and a verified GUI backup. This creates real records INSIDE a DB savepoint
and triggers an unconditional rollback. It does NOT mark kitchen MO Done,
perform warehouse transfers, assemble Paket or send DO/store receipt.
No fake BoM/Planning/routing or inventory quants. Use known existing
2026-11-24 S1 Published Planning and the real Paket SKU 12114.

This test expects the slot to be FREE. Stop, DO NOT bypass, if the batch or
a preexisting Paket RO already exists.
"""
from collections import defaultdict

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "REFUSED: WRONG DB"
print("DATABASE:", env.cr.dbname)
print("MODE: PACKAGE_JOINT_STAGE_MO_ROLLBACK")
date = "2026-11-24"
slot = "S1"
sku = "12114"
Module = env["ir.module.module"].sudo()
module = Module.search([("name", "=", "ya_package_store_ro")])
assert len(module) == 1 and module.state == "installed", (
    "First install Paket add-on ONLY in the test database"
)
assert module.installed_version == "19.0.1.3.0", (
    "Unexpected Paket add-on version"
)
Batch = env["ya.packing.batch"].sudo()
PackageRO = env["ya.package.store.ro"].sudo()
Product = env["product.product"].sudo()
Warehouse = env["stock.warehouse"].sudo()
assert not Batch.search_count([
    ("delivery_date", "=", date), ("slot", "=", slot),
]), "Date-slot is occupied; never overwrite an existing Pre Produksi"
assert not PackageRO.search_count([
    ("delivery_date", "=", date), ("slot", "=", slot),
]), "Existing Paket RO in selected slot; stop instead of merging test order"
product = Product.search([("default_code", "=", sku)], limit=2)
assert len(product) == 1, "Unique real Paket SKU 12114 required"
assert product.categ_id.complete_name == "All / Produk Jadi / Paket"
pck = Warehouse.search([("code", "=", "PCK")])
assert len(pck) == 1
stores = Warehouse.search([("company_id", "=", pck.company_id.id)])
stores = stores.filtered(lambda wh:
    wh.active and wh.code and wh.code.startswith("T_") and
    wh.id != pck.id and bool(wh.lot_stock_id)
).sorted("id")
assert stores, "No actual active store warehouse available for test RO"
store = stores[0]
print("UAT_REAL_PACKAGE:", product.default_code, product.display_name)
print("UAT_REAL_STORE:", store.code, store.name)
print("UAT_REAL_SLOT:", date, slot)

# Odoo shell uses superuser privileges ONLY inside rollback; this validates
# native ORM mechanics, not the separate creator vs Packing role-permission
# experience (which must be checked in GUI later).
class ExpectedRollback(Exception):
    pass

success = False
created_batch_id = None
created_ro_id = None
created_mo_ids = []
try:
    with env.cr.savepoint():
        ro = PackageRO.create({
            "delivery_date": date,
            "slot": slot,
            "store_warehouse_id": store.id,
            "line_ids": [(0, 0, {
                "product_id": product.id,
                "qty_requested": 1,
            })],
        })
        created_ro_id = ro.id
        ro.action_confirm()
        assert ro.state == "confirmed"
        print("PACKAGE_RO_CONFIRM_PASS")

        Wizard = env["ya.package.joint.slot.preview"].sudo()
        preview = Wizard.create({
            "delivery_date": date,
            "slot": slot,
        })
        preview.action_preview()
        assert preview.package_ro_count == 1
        assert preview.ordinary_ro_count == 0
        assert preview.source_digest
        print("JOINT_PREVIEW_WITHOUT_FAKE_RO_PASS")

        preview.action_move_to_preproduction()
        batches = Batch.search([
            ("delivery_date", "=", date), ("slot", "=", slot),
        ])
        assert len(batches) == 1
        batch = batches[0]
        created_batch_id = batch.id
        assert batch.state == "pre_production"
        assert batch.ya_has_package
        assert ro in batch.ya_package_ro_ids
        assert not batch.ro_ids
        assert len(batch.ya_package_demand_ids) == 1
        demand = batch.ya_package_demand_ids[0]
        assert demand.product_id == product
        assert demand.qty_requested == 1
        assert demand.bom_id
        assert len(demand.component_ids) == 3, (
            "Actual BoM 1405 component count changed; audit source first"
        )
        assert len(batch.line_ids) == 3
        assert set(batch.line_ids.mapped("kitchen_code")) == {"PST", "ROTI"}
        assert all(line.ya_package_component_qty == 1 for line in batch.line_ids)
        assert sum(batch.line_ids.mapped("qty_production")) == (
            sum(batch.line_ids.mapped("ya_package_component_qty")) +
            sum(batch.line_ids.mapped("qty_surplus"))
        ), "Kitchen MO total must equal Paket components plus manual transfer remainder"
        assert not batch.allocation_ids
        print("JOINT_PREPRODUCTION_FROZEN_PAKET_FIRST_PASS")
        print("PCK_INTERNAL_TRANSFER_FALLBACK_QTY:",
              sum(batch.line_ids.mapped("qty_surplus")))

        # Validate actual Odoo-created native MOs (no stock Done).
        batch.line_ids.action_generate_selected_mo()
        assert batch.state == "production_ok"
        mos = batch.line_ids.mapped("mo_id")
        created_mo_ids = mos.ids
        assert len(mos) == len(batch.line_ids) == 3
        assert len(set(mos.mapped("product_id").ids)) == 3
        assert all(mo.state not in ("draft", "done", "cancel") for mo in mos)
        assert all(mo.ya_packing_batch_line_id.batch_id == batch for mo in mos)
        assert not batch.ya_package_assembly_mo_ids, (
            "Paket assembly must NOT occur before FG transfer to PCK"
        )
        for mo in mos:
            assert not mo.workorder_ids, (
                "Kitchen MO source unexpectedly created WO; check this real BoM"
            )
        print("JOINT_KITCHEN_MO_CONFIRM_PASS")
        print("KITCHEN_MO_COUNT:", len(mos))
        success = True
        raise ExpectedRollback()
except ExpectedRollback:
    print("ROLLBACK_EXPECTED_OK")
finally:
    env.cr.rollback()
env.invalidate_all()

assert success, "Rollback test failed"
assert not Batch.search([("id", "=", created_batch_id)]), (
    "Unexpected persisted Paket Packing batch after rollback"
)
assert not PackageRO.search([("id", "=", created_ro_id)]), (
    "Unexpected persisted Paket RO after rollback"
)
assert not env["mrp.production"].sudo().search([
    ("id", "in", created_mo_ids)
]), "Unexpected persisted kitchen MO after rollback"
print("ROLLBACK_NO_RO_BATCH_MO_PERSISTED_PASS")
print("PACKAGE_JOINT_STAGE_MO_ROLLBACK_PASS")
