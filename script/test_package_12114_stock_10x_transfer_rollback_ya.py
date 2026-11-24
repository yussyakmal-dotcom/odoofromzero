"""ROLLBACK E2E — Paket 12114 to native kitchen MOs + CDC 10x opname/transfer.

Only AFTER installing ya_package_store_ro on erp-yussyakmal-mrp-test,
and a verified GUI backup. This creates real records INSIDE a DB savepoint and intentionally rolls
them back. Includes standard Stock Opname at CDC and native CDC->kitchen
internal transfers, but does NOT mark MO Done, assemble Paket or send DO.
Inventory quants are only created by native Odoo inventory adjustment and
rolled back; no fake BoM/Planning/routing or durable inventory. Use known existing
2026-11-24 S1 Published Planning and the real Paket SKU 12114.

This test expects the slot to be FREE. Stop, DO NOT bypass, if the batch or
a preexisting Paket RO already exists.
"""

from collections import defaultdict
from odoo.tools import float_compare, float_round

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "REFUSED: WRONG DB"
print("DATABASE:", env.cr.dbname)
print("MODE: PAKET_12114_STOCK_OPNAME_10X_CDC_TO_KITCHEN_ROLLBACK")
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

# The shell starts as odoo19/SUPERUSER, which bypasses ordinary ACLs but
# DOES NOT make env.user a member of either custom group. We must not disable
# the business role guards. Create two TEMPORARY users with actual group
# membership INSIDE the savepoint, use their identities for the proper action
# at each stage, and roll them back with every other test record. sudo() after
# with_user() bypasses unrelated ACL configuration only: the custom
# has_group() rules still inspect the actual role-bearing env.user.
Users = env["res.users"].sudo()
groups_field = next(
    (name for name in ("group_ids", "groups_id") if name in Users._fields),
    None,
)
assert groups_field, "Cannot locate the res.users membership field"
creator_group = env.ref("ya_package_store_ro.group_ya_package_ro_creator")
packing_group = env.ref("ya_store_ro.group_ya_packing_admin")
role_test_logins = (
    "__ya_pkg_rollback_creator__@example.invalid",
    "__ya_pkg_rollback_packing__@example.invalid",
)
assert not Users.search([
    ("login", "in", list(role_test_logins)),
]), "Rollback test-user login already exists; stop to protect real users"

def make_temporary_role_user(role, label, login):
    vals = {
        "name": label,
        "login": login,
        "company_id": pck.company_id.id,
        "company_ids": [(6, 0, [pck.company_id.id])],
        groups_field: [(6, 0, [role.id])],
    }
    return Users.with_context(
        no_reset_password=True,
        mail_create_nosubscribe=True,
        tracking_disable=True,
    ).create(vals)

class ExpectedRollback(Exception):
    pass

success = False
created_batch_id = None
created_ro_id = None
created_mo_ids = []
try:
    with env.cr.savepoint():
        creator = make_temporary_role_user(
            creator_group, "YA Rollback Paket RO Creator",
            role_test_logins[0],
        )
        packing_admin = make_temporary_role_user(
            packing_group, "YA Rollback Packing Admin",
            role_test_logins[1],
        )
        assert creator.has_group(
            "ya_package_store_ro.group_ya_package_ro_creator"
        ), "Creator test user lacks the actual creator role"
        assert packing_admin.has_group(
            "ya_store_ro.group_ya_packing_admin"
        ), "Packing test user lacks the actual Packing role"
        print("ROLLBACK_TEST_ROLE_USERS_READY")

        # WITH_USER supplies a real role-bearing identity. sudo preserves
        # the existing mechanical smoke-test scope and does not change which
        # user is checked by package_ro.py and joint_slot_preview.py.
        role_ro_model = PackageRO.with_user(creator).sudo()
        ro = role_ro_model.create({
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

        Wizard = env["ya.package.joint.slot.preview"].with_user(
            packing_admin
        ).sudo()
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
        BatchAsPacking = Batch.with_user(packing_admin).sudo()
        batch_as_packing = BatchAsPacking.browse(batch.id)
        batch_as_packing.line_ids.action_generate_selected_mo()
        batch.invalidate_recordset()
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
            if "workorder_ids" in mo._fields:
                assert not mo.workorder_ids, (
                    "Kitchen MO source unexpectedly created WO; "
                    "inspect the real kitchen BoM operations"
                )
        print("JOINT_KITCHEN_MO_CONFIRM_PASS")
        print("KITCHEN_MO_COUNT:", len(mos))

        # Physical-stage UAT 1: reapply the original safeguarded CDC
        # 10x-shortage opname ALGORITHM to THESE test-created native MOs.
        # The original dev_seed_cdc_material_10x_ya.py remains UNCHANGED:
        # it targets a different committed 2026-11-27 S1 batch and commits.
        # This harness never calls that script's unconditional commit. Every
        # stock adjustment and native CDC->kitchen picking is rollback-only.
        CDC = Warehouse.search([
            ("code", "=", "CDC"), ("company_id", "=", pck.company_id.id),
        ])
        assert len(CDC) == 1 and CDC.lot_stock_id.usage == "internal", (
            "No unique actual CDC warehouse; do not invent warehouse stock")
        cdc = CDC[0]
        requirements = defaultdict(float)
        raw_locations = defaultdict(set)
        kitchens = {}
        products = {}
        for mo in mos:
            kitchen = mo.picking_type_id.warehouse_id
            assert kitchen and kitchen.lot_stock_id and kitchen != cdc
            assert kitchen.company_id == cdc.company_id
            kitchens[kitchen.id] = kitchen
            for move in mo.move_raw_ids:
                assert move.state not in ("done", "cancel")
                product = move.product_id
                assert product.tracking == "none", (
                    "Cannot stock-opname tracked product without lot/serial")
                assert (("is_storable" in product._fields and
                         product.is_storable) or
                        ("is_storable" not in product._fields and
                         product.type == "product")), (
                    "Non-storable component in real Paket BOM: %s" %
                    product.display_name)
                qty = move.product_uom._compute_quantity(
                    move.product_uom_qty, product.uom_id, round=False)
                assert qty > 0 and product.uom_id.rounding > 0
                requirements[(kitchen.id, product.id)] += qty
                raw_locations[(kitchen.id, product.id)].add(move.location_id.id)
                products[product.id] = product
        assert requirements, "No material needs on real Paket kitchen MOs"
        for (wh_id, pid), sources in raw_locations.items():
            allowed = set(env["stock.location"].sudo().search([
                ("id", "child_of", kitchens[wh_id].lot_stock_id.id),
            ]).ids)
            assert sources.issubset(allowed), (
                "Unexpected raw source; don't seed wrong kitchen location")

        Quant = env["stock.quant"].sudo()
        def stock(warehouse, product_id):
            quants = Quant.search([
                ("product_id", "=", product_id),
                ("location_id", "child_of", warehouse.lot_stock_id.id),
                ("location_id.usage", "=", "internal"),
                ("company_id", "=", cdc.company_id.id),
            ])
            return (sum(quants.mapped("quantity")),
                    sum(quants.mapped("reserved_quantity")))

        before = {(wh.id, pid): stock(wh, pid) for wh in
                  [cdc] + list(kitchens.values())
                  for pid in products}
        gross_by_product = defaultdict(float)
        for (wh_id, pid), needed in requirements.items():
            physical, reserved = stock(kitchens[wh_id], pid)
            assert physical >= 0 and reserved == 0, (
                "Existing kitchen stock/reservation requires review")
            gross_by_product[pid] += max(0, needed - physical)

        inventory_changes = 0
        for pid, gross in sorted(gross_by_product.items()):
            product = products[pid]
            current, reserved = stock(cdc, pid)
            assert current >= 0 and reserved == 0, (
                "Existing CDC negative/reserved stock requires review")
            shortage = max(0.0, gross - current)
            # EXACT established CDC seed semantics: target 10x current
            # shortfall, not 10x a previously adjusted quantity.
            desired = max(current, 10 * shortage)
            desired = float_round(
                desired, precision_rounding=product.uom_id.rounding,
                rounding_method="UP")
            if float_compare(desired, current,
                             precision_rounding=product.uom_id.rounding) <= 0:
                continue
            root = Quant.search([
                ("product_id", "=", pid),
                ("location_id", "=", cdc.lot_stock_id.id),
                ("company_id", "=", cdc.company_id.id),
            ])
            assert len(root) <= 1, "Ambiguous CDC root quant"
            assert float_compare(sum(root.mapped("quantity")), current,
                                 precision_rounding=product.uom_id.rounding) == 0, (
                "CDC has child-bin stock; never overwrite inventory count")
            quant = root[:1]
            if not quant:
                quant = Quant.with_context(inventory_mode=True).create({
                    "product_id": pid,
                    "location_id": cdc.lot_stock_id.id,
                    "company_id": cdc.company_id.id,
                })
            quant.with_context(inventory_mode=True).write({
                "inventory_quantity": desired,
            })
            quant.action_apply_inventory()
            actual, _ = stock(cdc, pid)
            assert float_compare(actual, desired,
                                 precision_rounding=product.uom_id.rounding) == 0, (
                "CDC inventory adjustment Qty mismatch")
            inventory_changes += 1
        print("CDC_10X_OPNAME_PRODUCT_COUNT:", inventory_changes)
        print("CDC_10X_OPNAME_NATIVE_APPLY_ROLLBACK_PASS")

        # Native CDC -> kitchen internal transfer, exactly enough for the
        # current kitchen MOs, not all 10x CDC inventory.
        Operation = cdc.int_type_id
        assert Operation and Operation.code == "internal"
        assert Operation.company_id == cdc.company_id
        Picking = env["stock.picking"].sudo().with_company(cdc.company_id)
        StockMove = env["stock.move"].sudo().with_company(cdc.company_id)
        transfer_count = 0
        transfer_pickings = []
        transferred = {}
        for wh_id in sorted(kitchens):
            kitchen = kitchens[wh_id]
            rows = sorted(
                ((pid, qty) for (id_, pid), qty in requirements.items()
                 if id_ == wh_id), key=lambda row: row[0])
            assert rows, "No raw materials for a kitchen transfer"
            for pid, needed in rows:
                amount, reserved = stock(cdc, pid)
                assert amount - reserved >= needed, (
                    "CDC stock insufficient for native internal transfer")
                available_in_kitchen, _ = stock(kitchen, pid)
                transfer_qty = max(0, needed - available_in_kitchen)
                if transfer_qty > 0:
                    transferred[(wh_id, pid)] = transfer_qty
            values = [(pid, transferred[(wh_id, pid)])
                      for pid, _ in rows if (wh_id, pid) in transferred]
            if not values:
                continue
            picking = Picking.create({
                "picking_type_id": Operation.id,
                "company_id": cdc.company_id.id,
                "location_id": cdc.lot_stock_id.id,
                "location_dest_id": kitchen.lot_stock_id.id,
                "origin": "UAT-ROLLBACK-12114-CDC-%s" % kitchen.code,
            })
            moves = StockMove.create([{
                "picking_id": picking.id,
                "product_id": pid,
                "product_uom": products[pid].uom_id.id,
                "product_uom_qty": qty,
                "location_id": cdc.lot_stock_id.id,
                "location_dest_id": kitchen.lot_stock_id.id,
                "company_id": cdc.company_id.id,
            } for pid, qty in values])
            picking.action_confirm()
            for move in moves:
                assert move.state not in ("done", "cancel")
                move.write({"quantity": move.product_uom_qty})
            result = picking.with_context(
                skip_immediate=True, skip_backorder=True,
                cancel_backorder=True,
            ).button_validate()
            assert not isinstance(result, dict) and picking.state == "done", (
                "Native CDC->kitchen picking did not fully validate")
            assert all(move.state == "done" for move in moves), (
                "Picking is done but one material move is not done")
            transfer_pickings.append(picking)
            transfer_count += 1

        assert transfer_count == len(kitchens), (
            "Expected one native CDC internal picking per real kitchen")
        # Inspect exact posted stock moves BEFORE treating free-stock as
        # evidence of a shortage. After goods arrive, native Odoo can auto-
        # reserve them for an already-confirmed MO, reducing (physical -
        # reserved) without reducing physical inventory.
        env.flush_all()
        env.invalidate_all()
        transfer_done_by_key = defaultdict(float)
        for picking in transfer_pickings:
            assert picking.state == "done", (
                "Validated CDC->kitchen picking did not remain Done")
            for move in picking.move_ids:
                if move.state != "done":
                    raise AssertionError("CDC->kitchen move not Done")
                qty_done = move.product_uom._compute_quantity(
                    move.quantity, move.product_id.uom_id, round=False)
                transfer_done_by_key[(
                    picking.location_dest_id.id, move.product_id.id,
                )] += qty_done
        # Native Odoo immediately reserves received inventory for the
        # confirmed kitchen MOs. FREE = physical - ALL reservations can be 0
        # even when the entire demand is already reserved for THESE MOs.
        # Credit only the quantities found on assigned move lines belonging
        # to the current test MOs AND sourced from this real kitchen stock
        # tree. Never credit another MO's reservations or invent stock.
        allowed_sources = {
            wh_id: set(env["stock.location"].sudo().search([
                ("id", "child_of", kitchen.lot_stock_id.id),
            ]).ids) for wh_id, kitchen in kitchens.items()
        }
        own_mo_reserved = defaultdict(float)
        raw_state_by_key = defaultdict(list)
        for mo in mos:
            kitchen = mo.picking_type_id.warehouse_id
            for move in mo.move_raw_ids:
                key = (kitchen.id, move.product_id.id)
                raw_state_by_key[key].append((
                    move.id, move.state,
                    round(move.product_uom_qty, 5),
                    round(move.quantity, 5),
                    len(move.move_line_ids),
                ))
                if move.state != "assigned":
                    continue
                for line in move.move_line_ids:
                    if line.location_id.id not in allowed_sources[kitchen.id]:
                        continue
                    quantity = line.product_uom_id._compute_quantity(
                        line.quantity, move.product_id.uom_id, round=False)
                    if quantity < 0:
                        raise AssertionError(
                            "Unexpected negative test MO material reservation")
                    own_mo_reserved[key] += quantity

        shortages = []
        auto_reserved_count = 0
        for (wh_id, pid), need in sorted(requirements.items()):
            kitchen = kitchens[wh_id]
            product = products[pid]
            actual, reserved = stock(kitchen, pid)
            free = actual - reserved
            original, original_reserved = before[(wh_id, pid)]
            transferred_qty = transferred.get((wh_id, pid), 0.0)
            done_qty = transfer_done_by_key.get(
                (kitchen.lot_stock_id.id, pid), 0.0)
            precision = product.uom_id.rounding
            own_reserved = own_mo_reserved[(wh_id, pid)]
            # Free stock + reservations attributable to THIS trial's MOs.
            effective_for_mo = free + own_reserved
            receipt_ok = float_compare(
                done_qty, transferred_qty,
                precision_rounding=precision) == 0
            physical_ok = float_compare(
                actual, need, precision_rounding=precision) >= 0
            # Critical: do not treat another MO's reserved materials as
            # available to this test MO, or accept negative/overreserved stock.
            reservation_ownership_ok = (
                float_compare(
                    own_reserved, reserved,
                    precision_rounding=precision) <= 0 and
                float_compare(
                    reserved, actual,
                    precision_rounding=precision) <= 0 and
                float_compare(
                    free, 0, precision_rounding=precision) >= 0
            )
            free_only_ok = float_compare(
                free, need, precision_rounding=precision) >= 0
            ready_for_test_mos = (
                reservation_ownership_ok and
                float_compare(
                    effective_for_mo, need,
                    precision_rounding=precision) >= 0
            )
            if (not free_only_ok and ready_for_test_mos and
                    own_reserved > 0):
                auto_reserved_count += 1
            if not (receipt_ok and physical_ok and ready_for_test_mos):
                print("STOCK_DIAGNOSTIC:", kitchen.code,
                      product.default_code or product.id,
                      "NEED:", round(need, 5),
                      "ORIGINAL:", round(original, 5),
                      "ORIGINAL_RESERVED:", round(original_reserved, 5),
                      "TRANSFER_PLANNED:", round(transferred_qty, 5),
                      "TRANSFER_DONE:", round(done_qty, 5),
                      "PHYSICAL:", round(actual, 5),
                      "RESERVED:", round(reserved, 5),
                      "FREE:", round(free, 5),
                      "RESERVED_BY_TEST_MO:", round(own_reserved, 5),
                      "EFFECTIVE_FOR_TEST_MO:", round(effective_for_mo, 5),
                      "UNIT:", product.uom_id.name,
                      "RAW_MOVE_STATE:", raw_state_by_key[(wh_id, pid)],
                      "RECEIPT_OK:", receipt_ok,
                      "PHYSICAL_OK:", physical_ok,
                      "FREE_ONLY_OK:", free_only_ok,
                      "RESERVATION_OWNERSHIP_OK:",
                      reservation_ownership_ok,
                      "READY_FOR_TEST_MOS:", ready_for_test_mos)
                shortages.append((
                    kitchen.code, product.default_code or pid,
                    receipt_ok, physical_ok, ready_for_test_mos))
        print("POST_TRANSFER_DIAGNOSTIC_COUNT:", len(shortages))
        print("AUTO_RESERVED_FOR_TEST_MO_COMBINATIONS:", auto_reserved_count)
        if shortages:
            print("POST_TRANSFER_DIAGNOSTIC_KEYS:", shortages)
            raise AssertionError(
                "CDC transfer post-check failed receipt, physical, or "
                "test-MO-owned reservation check; see STOCK_DIAGNOSTIC.")
        print("NATIVE_CDC_KITCHEN_RESERVED_TO_TEST_MO_PASS")
        print("CDC_TO_KITCHEN_PICKING_COUNT:", transfer_count)
        print("PST_AND_ROTI_MATERIAL_READY_ROLLBACK_PASS")
        print("NATIVE_CDC_KITCHEN_TRANSFER_ROLLBACK_PASS")
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
assert not env["res.users"].sudo().search([
    ("login", "in", list(role_test_logins)),
]), "Unexpected persisted temporary role users after rollback"
print("ROLLBACK_ROLE_USERS_NOT_PERSISTED_PASS")
# The test must also restore every impacted CDC/kitchen material quant.
# No opening balances, stock moves or user accounts may survive.
for (wh_id, pid), (original_qty, original_res) in before.items():
    wh = Warehouse.browse(wh_id)
    now_qty, now_res = stock(wh, pid)
    assert float_compare(
        now_qty, original_qty,
        precision_rounding=products[pid].uom_id.rounding,
    ) == 0, "Stock Opname rollback failed for %s in %s" % (pid, wh.code)
    assert float_compare(
        now_res, original_res,
        precision_rounding=products[pid].uom_id.rounding,
    ) == 0, "Reservation rollback failed for %s in %s" % (pid, wh.code)
print("ROLLBACK_STOCK_OPNAME_AND_PICKINGS_VERIFIED_PASS")
print("ROLLBACK_NO_RO_BATCH_MO_PERSISTED_PASS")
print("PACKAGE_12114_10X_OPNAME_TRANSFER_ROLLBACK_PASS")
