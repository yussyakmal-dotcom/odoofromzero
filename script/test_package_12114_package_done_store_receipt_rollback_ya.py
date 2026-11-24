"""ROLLBACK E2E — Paket 12114 physical production through native T_BAN receipt.

Only AFTER installing ya_package_store_ro on erp-yussyakmal-mrp-test,
and a verified GUI backup. This creates real records INSIDE a DB savepoint and intentionally rolls
them back. Includes standard Stock Opname at CDC and native CDC->kitchen
internal transfers, native kitchen MO Done, physical finished-goods transfers
and native Paket assembly MO Done, DO dispatch, transit, and store receipt.
16 rounded surplus component units remain in PCK for separate approved standard
internal-transfer SOP (NOT invented Paket RO or automatic store allocation).
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
print("MODE: PAKET_12114_FULL_STORE_RECEIPT_ROLLBACK")
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
# Stable reference to the FINAL Paket SKU, distinct from the repeatedly
# reassigned 'product' variable used for kitchen raw-material processing.
package_product = product
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

        # NEXT native manufacturing stage: only REAL MOs and Odoo's
        # button_mark_done(), no manual fake finished inventory or raw SQL.
        # All the raw materials are already physically in PST/ROTI and
        # natively reserved to THESE 3 kitchen MOs.
        expected_fg = {}
        before_fg = {}
        raw_stock_after_transfer = {
            (wh_id, pid): stock(kitchens[wh_id], pid)[0]
            for wh_id, pid in requirements
        }
        for mo in mos:
            assert mo.product_id.tracking == "none", (
                "Tracked finished goods require normal lot/serial workflow")
            assert mo.state not in ("done", "draft", "cancel")
            assert not mo.workorder_ids, "Unexpected kitchen WO"
            raw_qty = defaultdict(float)
            for move in mo.move_raw_ids:
                assert move.product_id.tracking == "none"
                assert move.state == "assigned", (
                    "MO raw materials not fully reserved before Done")
                required_qty = move.product_uom._compute_quantity(
                    move.product_uom_qty, move.product_id.uom_id, round=False)
                actual_reserved = move.product_uom._compute_quantity(
                    move.quantity, move.product_id.uom_id, round=False)
                precision = move.product_id.uom_id.rounding
                assert float_compare(
                    actual_reserved, required_qty,
                    precision_rounding=precision) >= 0, (
                    "One MO raw material is not fully reserved")
                raw_qty[move.product_id.id] += required_qty
            wh = mo.picking_type_id.warehouse_id
            assert mo.location_dest_id == wh.lot_stock_id
            assert mo.product_id.id not in expected_fg, (
                "Duplicate kitchen MO finished SKU")
            expected_fg[mo.product_id.id] = (
                wh.id, mo.product_qty, mo.product_id.uom_id.rounding
            )
            before_fg[mo.product_id.id] = (
                stock(wh, mo.product_id.id)[0],
                stock(pck, mo.product_id.id)[0],
            )
            result = mo.with_context(
                skip_redirection=True,
                skip_backorder=True,
            ).button_mark_done()
            if isinstance(result, dict) or mo.state != "done":
                raise AssertionError(
                    "Native MO Done produced wizard or incomplete state "
                    "for %s: %s" % (mo.name, str(result)[:300]))
            finished = mo.move_finished_ids.filtered(
                lambda m: m.state == "done" and
                m.product_id == mo.product_id and
                m.location_dest_id == wh.lot_stock_id
            )
            finish_qty = sum(m.product_uom._compute_quantity(
                m.quantity, mo.product_id.uom_id, round=False)
                for m in finished)
            assert float_compare(
                finish_qty, mo.product_qty,
                precision_rounding=mo.product_id.uom_id.rounding) == 0, (
                "Native MO finished stock-move Qty differs from planned batch")
            assert all(raw.state == "done" for raw in mo.move_raw_ids), (
                "Native MO did not post every original BOM raw move")
            print("KITCHEN_MO_DONE:", mo.product_id.default_code,
                  "KITCHEN:", wh.code,
                  "FINISHED_QTY:", finish_qty,
                  "RAW_MOVE_COUNT:", len(mo.move_raw_ids))

        env.flush_all()
        env.invalidate_all()
        assert all(mo.state == "done" for mo in mos)
        for (wh_id, pid), need in requirements.items():
            wh = kitchens[wh_id]
            original_qty = raw_stock_after_transfer[(wh_id, pid)]
            current_qty, _ = stock(wh, pid)
            assert float_compare(
                original_qty - current_qty, need,
                precision_rounding=products[pid].uom_id.rounding
            ) == 0, "MO raw consumption delta differs from actual BoM demand"
            assert float_compare(
                current_qty, 0,
                precision_rounding=products[pid].uom_id.rounding
            ) >= 0, "No-negative-stock policy: raw stock below zero"
        for pid, (wh_id, expected, precision) in expected_fg.items():
            wh = kitchens[wh_id]
            after_kitchen = stock(wh, pid)[0]
            assert float_compare(
                after_kitchen - before_fg[pid][0], expected,
                precision_rounding=precision
            ) == 0, "Native MO Finished stock delta mismatch"
        print("NATIVE_KITCHEN_MO_DONE_3_PASS")
        print("NATIVE_MO_RAW_CONSUMPTION_DELTAS_PASS")
        print("NATIVE_MO_FINISHED_KITCHEN_STOCK_DELTAS_PASS")

        # The SAME batch's standard button (already used for ordinary RO)
        # physically moves the actual MO Done products kitchen->PCK.
        fg_result = batch_as_packing.action_ya_fg_move_to_packing()
        fg_pickings = batch_as_packing.ya_fg_transfer_ids
        fg_picking_ids = fg_pickings.ids
        assert len(fg_pickings) == len(kitchens) == 2, (
            "Expected exactly one native FG picking per kitchen")
        assert all(p.state == "done" for p in fg_pickings)
        assert all(p.location_dest_id == pck.lot_stock_id for p in fg_pickings)
        for pid, (wh_id, expected, precision) in expected_fg.items():
            wh = kitchens[wh_id]
            after_kitchen, _ = stock(wh, pid)
            after_pck, _ = stock(pck, pid)
            assert float_compare(
                after_kitchen, before_fg[pid][0],
                precision_rounding=precision
            ) == 0, "Kitchen finished stock did not physically leave"
            assert float_compare(
                after_pck - before_fg[pid][1], expected,
                precision_rounding=precision
            ) == 0, "PCK did not physically receive kitchen finished SKU"
        assert batch_as_packing.action_ya_fg_move_to_packing()
        assert len(batch_as_packing.ya_fg_transfer_ids) == 2, (
            "Double-click created duplicate FG transfers")
        print("NATIVE_KITCHEN_TO_PCK_FG_PICKINGS:", len(fg_pickings))
        print("NATIVE_KITCHEN_TO_PCK_FG_TRANSFER_ROLLBACK_PASS")
        print("NATIVE_FG_DOUBLE_CLICK_IDEMPOTENCE_PASS")

        # One standard manufacturing order at PCK, for one actual final
        # Paket SKU. This action must NOT consume components / Done yet.
        assembly_result = batch_as_packing.action_ya_create_package_assembly_mos()
        assemblies = batch_as_packing.ya_package_assembly_mo_ids
        assembly_mo_ids = assemblies.ids
        assert len(assemblies) == 1, (
            "One Paket SKU must produce exactly one PCK assembly MO")
        assembly = assemblies[0]
        # Odoo 19 recomputes draft MO defaults from BoM. Before changing a
        # functional addon, report which actual ORM value differs from the
        # frozen Paket demand. Never mask a wrong SKU or silently alter Qty.
        env.flush_all()
        assembly.invalidate_recordset()
        assert package_product.id == demand.product_id.id, (
            "Frozen Paket demand was not linked to the selected Paket SKU")
        assert package_product.default_code == sku, (
            "Selected Paket SKU changed during stock/production UAT")
        frozen_qty = sum(
            d.qty_requested for d in batch_as_packing.ya_package_demand_ids
            if d.product_id.id == package_product.id
        )
        mo_qty_base = assembly.product_uom_id._compute_quantity(
            assembly.product_qty, assembly.product_id.uom_id, round=False)
        frozen_product_ids = batch_as_packing.ya_package_demand_ids.mapped(
            "product_id").ids
        print("PCK_ASSEMBLY_ACTUAL:",
              "MO_ID:", assembly.id,
              "PRODUCT_ID:", assembly.product_id.id,
              "SKU:", assembly.product_id.default_code,
              "PRODUCT_QTY:", assembly.product_qty,
              "MO_UOM:", assembly.product_uom_id.name,
              "QTY_IN_BASE_UOM:", mo_qty_base,
              "BOM_ID:", assembly.bom_id.id,
              "TYPE_ID:", assembly.picking_type_id.id,
              "SRC_LOCATION_ID:", assembly.location_src_id.id,
              "DEST_LOCATION_ID:", assembly.location_dest_id.id,
              "STATE:", assembly.state)
        print("PCK_ASSEMBLY_EXPECTED:",
              "PRODUCT_ID:", package_product.id,
              "SKU:", package_product.default_code,
              "FROZEN_PRODUCT_IDS:", frozen_product_ids,
              "FROZEN_QTY:", frozen_qty,
              "EXPECTED_BASE_UOM:", package_product.uom_id.name,
              "BOM_ID:", demand.bom_id.id,
              "TYPE_ID:", pck.manu_type_id.id,
              "PCK_STOCK_LOCATION_ID:", pck.lot_stock_id.id)
        assert assembly.product_id.id == package_product.id, (
            "PCK assembly WRONG PRODUCT: actual %s expected %s" %
            (assembly.product_id.id, package_product.id))
        assert float_compare(
            mo_qty_base, frozen_qty,
            precision_rounding=package_product.uom_id.rounding) == 0, (
            "PCK assembly WRONG QTY: actual %s expected %s "
            "in product base UoM" % (mo_qty_base, frozen_qty))
        assert assembly.bom_id.id == demand.bom_id.id, (
            "PCK assembly wrong BoM: actual %s expected %s" %
            (assembly.bom_id.id, demand.bom_id.id))
        assert assembly.picking_type_id.id == pck.manu_type_id.id, (
            "PCK assembly wrong Manufacturing operation type: "
            "actual %s expected %s" %
            (assembly.picking_type_id.id, pck.manu_type_id.id))
        assert assembly.location_src_id.id == pck.lot_stock_id.id, (
            "PCK assembly raw source is not PCK/Stock")
        assert assembly.location_dest_id.id == pck.lot_stock_id.id, (
            "PCK assembly finished destination is not PCK/Stock")
        assert assembly.state not in ("draft", "done", "cancel")
        assert not assembly.workorder_ids
        assembly_raw = defaultdict(float)
        for move in assembly.move_raw_ids:
            assembly_raw[move.product_id.id] += (
                move.product_uom._compute_quantity(
                    move.product_uom_qty, move.product_id.uom_id,
                    round=False))
        expected_package_parts = {
            d.product_id.id: d.qty_required
            for d in demand.component_ids
        }
        assert set(assembly_raw) == set(expected_package_parts), (
            "PCK assembly BoM components differ from frozen Paket snapshot")
        for pid, qty in expected_package_parts.items():
            assert float_compare(
                assembly_raw[pid], qty,
                precision_rounding=Product.browse(pid).uom_id.rounding
            ) == 0, "PCK assembly component Qty mismatch"
        assert len(batch_as_packing.ya_package_assembly_mo_ids) == 1
        batch_as_packing.action_ya_create_package_assembly_mos()
        assert len(batch_as_packing.ya_package_assembly_mo_ids) == 1, (
            "Double-click duplicated Paket assembly MO")
        print("PCK_PACKAGE_ASSEMBLY_MO_COUNT:", len(assemblies))
        print("PCK_PACKAGE_ASSEMBLY_BOM_COMPONENT_COUNT:", len(assembly_raw))
        print("PCK_PACKAGE_ASSEMBLY_MO_CONFIRMED_ROLLBACK_PASS")
        print("PCK_PACKAGE_ASSEMBLY_DOUBLE_CLICK_IDEMPOTENCE_PASS")

        # Final stage: native 1 Paket assembly MO consumes ONLY 1 of each
        # finished component in PCK, produces 1 final Paket in PCK/Stock.
        # Do not turn the other 16 kitchen finished units into fake RO.
        assert package_product.tracking == "none", (
            "Final Paket SKU is tracked; normal lot/serial SOP required")
        assert all(m.product_id.tracking == "none"
                   for m in assembly.move_raw_ids), (
            "PCK assembly has tracked ingredients; use real lot/serial SOP")
        assert set(expected_package_parts) == set(expected_fg), (
            "All Paket components must originate from 3 kitchen MOs")
        package_stock_before = stock(pck, package_product.id)[0]
        pck_component_before = {
            pid: stock(pck, pid)[0] for pid in expected_package_parts
        }
        for pid, qty in expected_package_parts.items():
            comp = Product.browse(pid)
            assert float_compare(
                pck_component_before[pid], qty,
                precision_rounding=comp.uom_id.rounding
            ) >= 0, "Insufficient PCK component physical stock for assembly"

        assembly.action_assign()
        env.flush_all()
        env.invalidate_all()
        for raw in assembly.move_raw_ids:
            comp = raw.product_id
            required = raw.product_uom._compute_quantity(
                raw.product_uom_qty, comp.uom_id, round=False)
            reserved = raw.product_uom._compute_quantity(
                raw.quantity, comp.uom_id, round=False)
            assert raw.state == "assigned" and float_compare(
                reserved, required,
                precision_rounding=comp.uom_id.rounding
            ) >= 0, (
                "Native PCK assembly component not fully reserved: %s"
                % comp.display_name)
            assert raw.location_id == pck.lot_stock_id, (
                "Paket component must be consumed from PCK/Stock")
        assembly_done_result = assembly.with_context(
            skip_redirection=True, skip_backorder=True
        ).button_mark_done()
        if isinstance(assembly_done_result, dict) or assembly.state != "done":
            raise AssertionError(
                "Native Paket assembly MO not Done; do not bypass Odoo "
                "wizard: %s" % str(assembly_done_result)[:300])
        assert all(move.state == "done" for move in assembly.move_raw_ids), (
            "Assembly raw components did not finish via native stock moves")
        finish_moves = assembly.move_finished_ids.filtered(
            lambda move: move.state == "done" and
            move.product_id == package_product and
            move.location_dest_id == pck.lot_stock_id
        )
        actual_package_mo_qty = sum(
            move.product_uom._compute_quantity(
                move.quantity, package_product.uom_id, round=False)
            for move in finish_moves
        )
        assert float_compare(
            actual_package_mo_qty, frozen_qty,
            precision_rounding=package_product.uom_id.rounding
        ) == 0, "Native final Paket MO produced different Qty"
        env.flush_all()
        env.invalidate_all()
        assert float_compare(
            stock(pck, package_product.id)[0] - package_stock_before,
            frozen_qty,
            precision_rounding=package_product.uom_id.rounding
        ) == 0, "Final Paket did not physically enter PCK"
        surplus = 0.0
        for pid, qty in expected_package_parts.items():
            comp = Product.browse(pid)
            after_qty = stock(pck, pid)[0]
            assert float_compare(
                pck_component_before[pid] - after_qty, qty,
                precision_rounding=comp.uom_id.rounding
            ) == 0, (
                "Actual Paket assembly consumed incorrect kitchen part Qty")
            assert float_compare(
                after_qty, 0.0,
                precision_rounding=comp.uom_id.rounding
            ) >= 0, "PCK component stock went negative"
            surplus += after_qty - before_fg[pid][1]
        assert abs(surplus - 16) < 1e-9, (
            "16 rounded kitchen component units must remain unallocated "
            "for separate standard internal-transfer SOP")
        print("PCK_NATIVE_ASSEMBLY_MO_DONE_PASS")
        print("PCK_NATIVE_ASSEMBLY_COMPONENT_CONSUMPTION_PASS")
        print("PCK_KITCHEN_SURPLUS_REQUIRES_SEPARATE_TRANSFER:", surplus)

        # Paket-only batch: ONE store DO T_BAN, ONE final Paket line. The
        # existing store delivery addon remains responsible for transit,
        # dispatch, receipt and native stock moves. Never create a fake RO.
        Location = env["stock.location"].sudo()
        transits = Location.search([
            ("usage", "=", "transit"),
            ("name", "=", "Inter-warehouse transit"),
            ("company_id", "in", [False, pck.company_id.id]),
        ])
        assert len(transits) == 1, (
            "Existing native Inter-warehouse transit must be unique")
        transit = transits[0]
        QuantLocal = env["stock.quant"].sudo()
        def quant_exact(location, product_id):
            qs = QuantLocal.search([
                ("product_id", "=", product_id),
                ("location_id", "=", location.id),
                ("company_id", "=", pck.company_id.id),
            ])
            return sum(qs.mapped("quantity"))
        original_transit_package = quant_exact(transit, package_product.id)
        original_store_package = quant_exact(store.lot_stock_id, package_product.id)
        pck_after_assembly = quant_exact(pck.lot_stock_id, package_product.id)
        assert float_compare(
            pck_after_assembly - package_stock_before, 1,
            precision_rounding=package_product.uom_id.rounding
        ) == 0

        assert not batch_as_packing.ya_store_delivery_ids
        batch_as_packing.action_ya_generate_store_do()
        delivery_docs = batch_as_packing.ya_store_delivery_ids
        dispatches = delivery_docs.filtered(
            lambda record: record.ya_store_stage == "dispatch")
        assert len(dispatches) == 1, (
            "Paket-only RO must create ONE store dispatch")
        dispatch = dispatches[0]
        dispatch_id = dispatch.id
        assert dispatch.ya_store_warehouse_id == store
        assert dispatch.location_id == pck.lot_stock_id
        assert dispatch.location_dest_id == transit
        assert dispatch.state not in ("done", "cancel")
        assert len(dispatch.move_ids) == 1
        dispatch_move = dispatch.move_ids[0]
        assert dispatch_move.product_id == package_product
        assert float_compare(
            dispatch_move.product_uom._compute_quantity(
                dispatch_move.product_uom_qty, package_product.uom_id,
                round=False), frozen_qty,
            precision_rounding=package_product.uom_id.rounding
        ) == 0, "Store Paket DO Demand differs from confirmed Paket RO"
        assert quant_exact(transit, package_product.id) == original_transit_package
        assert quant_exact(store.lot_stock_id, package_product.id) == original_store_package
        assert quant_exact(pck.lot_stock_id, package_product.id) == pck_after_assembly
        assert not delivery_docs.filtered(
            lambda record: record.ya_store_stage == "receipt")
        batch_as_packing.action_ya_generate_store_do()
        assert len(batch_as_packing.ya_store_delivery_ids) == 1, (
            "Generating the DO twice duplicated stock picking")
        print("PCK_PAKET_STORE_DO_DEMAND_AND_IDEMPOTENCE_PASS")

        # Mimic Packing operator entering actual shipped Qty, then use
        # existing native dispatch Validate rather than direct stock writes.
        if float_compare(
            dispatch_move.quantity, frozen_qty,
            precision_rounding=package_product.uom_id.rounding
        ) != 0:
            assert float_compare(
                dispatch_move.quantity, 0,
                precision_rounding=package_product.uom_id.rounding
            ) >= 0, "Negative prefilled DO shipment"
            dispatch_move.write({"quantity": frozen_qty})
        shipped_result = dispatch.with_context(
            skip_immediate=True, skip_backorder=True,
            cancel_backorder=True,
        ).button_validate()
        if isinstance(shipped_result, dict) or dispatch.state != "done":
            raise AssertionError(
                "YA native dispatch not Done; do not bypass Odoo wizard: "
                "%s" % str(shipped_result)[:300])
        env.flush_all()
        env.invalidate_all()
        assert float_compare(
            pck_after_assembly - quant_exact(
                pck.lot_stock_id, package_product.id),
            frozen_qty, precision_rounding=package_product.uom_id.rounding
        ) == 0, "PCK stock not debited by DO shipment"
        assert float_compare(
            quant_exact(transit, package_product.id) -
            original_transit_package,
            frozen_qty, precision_rounding=package_product.uom_id.rounding
        ) == 0, "Transit did not physically receive outgoing Paket"
        assert quant_exact(
            store.lot_stock_id, package_product.id
        ) == original_store_package, (
            "Store stock changed BEFORE store validated receipt")
        receipts = batch_as_packing.ya_store_delivery_ids.filtered(
            lambda rec: rec.ya_store_stage == "receipt")
        assert len(receipts) == 1, (
            "Native dispatch Done must generate EXACTLY ONE receipt")
        receipt = receipts[0]
        receipt_id = receipt.id
        assert receipt.ya_source_dispatch_id == dispatch
        assert receipt.ya_store_warehouse_id == store
        assert receipt.location_id == transit
        assert receipt.location_dest_id == store.lot_stock_id
        assert len(receipt.move_ids) == 1
        assert receipt.move_ids.product_id == package_product
        print("PCK_TO_TRANSIT_PAKET_DISPATCH_DONE_PASS")
        print("TRANSIT_TO_STORE_NATIVE_RECEIPT_CREATED_PASS")

        receipt_move = receipt.move_ids[0]
        if float_compare(
            receipt_move.quantity, frozen_qty,
            precision_rounding=package_product.uom_id.rounding
        ) != 0:
            receipt_move.write({"quantity": frozen_qty})
        received_result = receipt.with_context(
            skip_immediate=True, skip_backorder=True,
            cancel_backorder=True
        ).button_validate()
        if isinstance(received_result, dict) or receipt.state != "done":
            raise AssertionError(
                "Native store receipt not Done; do not bypass Odoo wizard: "
                "%s" % str(received_result)[:300])
        env.flush_all()
        env.invalidate_all()
        assert float_compare(
            quant_exact(store.lot_stock_id, package_product.id) -
            original_store_package,
            frozen_qty, precision_rounding=package_product.uom_id.rounding
        ) == 0, "T_BAN store stock not increased by actual receipt"
        assert float_compare(
            quant_exact(transit, package_product.id),
            original_transit_package,
            precision_rounding=package_product.uom_id.rounding
        ) == 0, "Transit stock did not clear after store receipt"
        assert float_compare(
            quant_exact(pck.lot_stock_id, package_product.id),
            package_stock_before,
            precision_rounding=package_product.uom_id.rounding
        ) == 0, "Finished Paket still resides in PCK after store receipt"
        assert len(batch_as_packing.ya_store_delivery_ids.filtered(
            lambda rec: rec.ya_store_stage == "dispatch")) == 1
        assert len(batch_as_packing.ya_store_delivery_ids.filtered(
            lambda rec: rec.ya_store_stage == "receipt")) == 1
        print("NATIVE_STORE_RECEIPT_T_BAN_DONE_PASS")
        print("PCK_TRANSIT_STORE_PAKET_STOCK_DELTAS_PASS")
        print("NATIVE_ONE_DO_ONE_RECEIPT_NO_DUPLICATES_PASS")
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
assert not env["mrp.production"].sudo().search([
    ("id", "in", assembly_mo_ids)
]), "Unexpected persisted PCK Paket assembly MO after rollback"
assert not env["stock.picking"].sudo().search([
    ("id", "in", fg_picking_ids)
]), "Unexpected persisted kitchen-to-PCK picking after rollback"
assert not env["stock.picking"].sudo().search([
    ("id", "in", [dispatch_id, receipt_id])
]), "Unexpected persisted Paket dispatch/receipt after rollback"
assert float_compare(
    quant_exact(transit, package_product.id),
    original_transit_package,
    precision_rounding=package_product.uom_id.rounding
) == 0, "Transit Paket stock survived rollback"
assert float_compare(
    quant_exact(store.lot_stock_id, package_product.id),
    original_store_package,
    precision_rounding=package_product.uom_id.rounding
) == 0, "Store Paket stock survived rollback"
assert float_compare(
    quant_exact(pck.lot_stock_id, package_product.id),
    package_stock_before,
    precision_rounding=package_product.uom_id.rounding
) == 0, "PCK Paket finished stock survived rollback"
print("ROLLBACK_PAKET_PCK_TRANSIT_STORE_VERIFIED_PASS")
for fg_pid, (wh_id, _, precision) in expected_fg.items():
    kitchen = Warehouse.browse(wh_id)
    original_kitchen_fg, original_pck_fg = before_fg[fg_pid]
    assert float_compare(
        stock(kitchen, fg_pid)[0], original_kitchen_fg,
        precision_rounding=precision
    ) == 0, "Kitchen finished SKU stock survived rollback"
    assert float_compare(
        stock(pck, fg_pid)[0], original_pck_fg,
        precision_rounding=precision
    ) == 0, "PCK finished SKU stock survived rollback"
print("ROLLBACK_FINISHED_STOCK_VERIFIED_PASS")
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
print("PACKAGE_12114_FULL_STORE_RECEIPT_ROLLBACK_PASS")
