"""Clone-only native MO2 -> separate CDC material picking, rollback-only.

All objects are synthetic in ONE uncommitted transaction:
Published Planning -> Packing Batch -> native confirmed MO1 -> YA SO1 -> YA SO2.
Tests native MO2 creation with own source ledger; RO allocation and PCK DO remain separate.
An unconditional rollback in finally removes test Planning, MO1, SOs & ledger.
Never run against main or first-phase test databases.
"""
from collections import Counter
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from unittest.mock import patch

from odoo.addons.ya_sale_production_capacity.models import mo2_release

from odoo import fields
from odoo.exceptions import UserError

CLONE = "erp-yussyakmal-mrp-test-RO_SO"
assert env.cr.dbname == CLONE, "STOP_WRONG_DATABASE"
Version = env["ir.module.module"].sudo().search([
    ("name", "=", "ya_sale_production_capacity")
], limit=1)
assert Version and Version.state == "installed" and (
    Version.installed_version == "19.0.1.1.3"
), "STOP_WRONG_YA_SALES_ADDON_VERSION"
assert env.user.has_group("mrp.group_mrp_manager"), "STOP_MRP_MANAGER_REQUIRED"
assert env.user.has_group("sales_team.group_sale_salesman"), "STOP_SALES_ROLE_REQUIRED"

Planning = env["ya.production.planning"]
Line = env["ya.production.planning.line"]
Batch = env["ya.packing.batch"]
MO = env["mrp.production"]
Sale = env["sale.order"]
Ledger = env["ya.sale.capacity.reservation"].sudo()
Sample = Sale.sudo().search([
    ("ya_is_capacity_so", "=", True), ("partner_id", "!=", False)
], limit=1)
assert Sample, "STOP_NO_SAMPLE_YA_QUOTATION"

# Odoo shell OS user 'odoo19' maps to Odoo's shell environment user,
# who need not belong to the YA Packing Admin business group.
# Keep sales/MRP fixture creation under the original shell user;
# perform the MO2 release as an EXISTING authorized Packing operator
# (no group grants, no sudo bypass for the release itself).
PACKING_GROUP = "ya_store_ro.group_ya_packing_admin"
packing_actor = env.user
if not packing_actor.has_group(PACKING_GROUP):
    candidates = env["res.users"].sudo().search([
        ("active", "=", True), ("share", "=", False),
    ])
    packing_admins = candidates.filtered(
        lambda user: user.has_group(PACKING_GROUP)
    )
    eligible = packing_admins.filtered(
        lambda user: Sample.company_id in user.company_ids
        and (user.has_group("mrp.group_mrp_manager")
             or user.has_group("mrp.group_mrp_user"))
    )
    print("PACKING_ADMIN_EXISTING_ACTIVE_USERS:", len(packing_admins))
    print("PACKING_ADMIN_WITH_MRP_AND_TEST_COMPANY:", len(eligible))
    assert eligible, (
        "STOP_NO_EXISTING_AUTHORIZED_PACKING_MRP_USER: "
        "test created no MO/Planning/SO; do not grant groups automatically"
    )
    packing_actor = eligible.sorted(
        key=lambda user: (
            0 if user.has_group("mrp.group_mrp_manager") else 1,
            user.id,
        )
    )[0]
# Existing internal user with both Packing read ACL and Inventory Manager.
# Do not grant groups or bypass business permissions for a test.
StockGroup = "stock.group_stock_manager"
stock_actor_candidates = env["res.users"].sudo().search([
    ("active", "=", True), ("share", "=", False),
]).filtered(lambda u: (
    u.has_group(StockGroup) and u.has_group(PACKING_GROUP)
    and Sample.company_id in u.company_ids
))
print("EXISTING_STOCK_AND_PACKING_ADMIN_USERS:", len(stock_actor_candidates))
assert stock_actor_candidates, (
    "STOP_NO_EXISTING_STOCK_AND_PACKING_ADMIN_USER; no test records created"
)
stock_actor = stock_actor_candidates.sorted(key=lambda u: u.id)[0]
print("MO2_CDC_ACTOR_USER_ID:", stock_actor.id)

print("MO2_RELEASE_ACTOR_USER_ID:", packing_actor.id,
      "IS_PACKING_ADMIN:", packing_actor.has_group(PACKING_GROUP),
      "MRP_ACCESS:", bool(
          packing_actor.has_group("mrp.group_mrp_manager") or
          packing_actor.has_group("mrp.group_mrp_user")
      ))
assert Sample.company_id in packing_actor.company_ids, (
    "STOP_RELEASE_ACTOR_COMPANY_ACCESS"
)
print("DATABASE:", env.cr.dbname)
print("MODE: NATIVE_MO2_DONE_FG_DRAFT_ROLLBACK")
print("SAMPLE_YA_QUOTATION_ID:", Sample.id)

source_line = None
source_bom = None
units_per_batch = None
max_capacity = None
rejected = Counter()
published = Planning.sudo().search([
    ("state", "=", "published")
], order="delivery_date desc,slot,id")
per_slot_sku = Counter(
    (p.delivery_date, p.slot, line.product_id.id)
    for p in published for line in p.line_ids
)
for p in published:
    for line in p.line_ids:
        product = line.product_id
        if (line.max_capacity <= 0 or
                per_slot_sku[(p.delivery_date, p.slot, product.id)] != 1 or
                product.categ_id.complete_name == "All / Produk Jadi / Paket"):
            rejected["MAX_ROUTE_OR_PAKET"] += 1
            continue
        try:
            bom = line._capacity_bom()
            pt = bom.picking_type_id
            expected = " ".join(
                ("Dapur " + (p.workcenter_id.name or "")).casefold().split()
            )
            actual = " ".join(
                (pt.warehouse_id.name or "").casefold().split()
            ) if pt and pt.warehouse_id else ""
            if (not bom.active or bom.type != "normal"
                    or bom.product_tmpl_id != product.product_tmpl_id
                    or (bom.product_id and bom.product_id != product)
                    or not pt or not pt.warehouse_id
                    or not pt.default_location_src_id
                    or not pt.default_location_dest_id
                    or pt.default_location_dest_id != pt.warehouse_id.lot_stock_id
                    or pt.company_id != Sample.company_id or actual != expected):
                rejected["BOM_KITCHEN_ROUTE_INVALID"] += 1
                continue
            output = bom.product_uom_id._compute_quantity(
                bom.product_qty, product.uom_id, round=False
            )
            maximum = line.uom_id._compute_quantity(
                line.max_capacity, product.uom_id, round=False
            )
            if (output <= 0 or abs(output - round(output)) > 1e-9
                    or maximum < 2 * output or
                    abs(maximum - round(maximum)) > 1e-9
                    or int(round(maximum)) % int(round(output))):
                rejected["NOT_TWO_VALID_BOM_BATCHES"] += 1
                continue
            from odoo.addons.ya_production_planning.models.capacity_rules import closest_batch_multiple
            if closest_batch_multiple(
                line.max_capacity, bom.product_qty
            ) != line.max_capacity:
                rejected["PUBLISH_MAX_INCOMPATIBLE"] += 1
                continue
        except (UserError, ValueError) as exc:
            rejected["BOM_RESOLUTION_ERROR"] += 1
            if rejected["BOM_RESOLUTION_ERROR"] <= 2:
                print("BOM_REJECTION_EXAMPLE:", line.id, str(exc)[:180])
            continue
        source_line = line
        source_bom = bom
        units_per_batch = int(round(output))
        max_capacity = int(round(maximum))
        break
    if source_line:
        break

print("TEMPLATE_SKU_REJECTIONS:", sorted(rejected.items()))
assert source_line, "STOP_NO_SOURCE_WITH_TWO_BOM_BATCHES; NO_TEST_WRITES"
print("TEMPLATE:", "PLAN_LINE:", source_line.id,
      "PRODUCT_ID:", source_line.product_id.id,
      "BOM_ID:", source_bom.id, "BOM_OUTPUT:", units_per_batch,
      "PUBLISHED_MAX:", max_capacity)

date = None
slot = "S1"
today = fields.Date.context_today(Sale)
for days in range(14, 75):
    candidate = today + timedelta(days=days)
    d = [("delivery_date", "=", candidate), ("slot", "=", slot)]
    if (not Planning.sudo().search_count(d)
            and not Batch.sudo().search_count(d)
            and not Ledger.search_count(d)
            and not Sale.sudo().search_count([
                ("ya_is_capacity_so", "=", True),
                ("ya_delivery_date", "=", candidate),
                ("ya_slot", "=", slot),
            ])):
        date = candidate
        break
assert date, "STOP_NO_FREE_FUTURE_S1; NO_TEST_WRITES"

ids = {}
success = False
try:
    # Minimal synthetic Planning and Packing fixture following actual
    # ORM structures. Does not overwrite any existing RO or batch.
    plan = Planning.sudo().create({
        "delivery_date": date, "slot": slot,
        "kitchen_code": source_line.planning_id.kitchen_code,
        "workcenter_id": source_line.planning_id.workcenter_id.id,
        "upload_filename": "ROLLBACK_ONLY_MO1",
    })
    ids["planning"] = plan.id
    plan_line = Line.sudo().create({
        "planning_id": plan.id,
        "product_id": source_line.product_id.id,
        "reference": source_line.reference,
        "max_capacity": source_line.max_capacity,
        "uom_id": source_line.uom_id.id,
        "bom_id": source_bom.id,
        "source_sheet": "ROLLBACK_ONLY", "source_row": 2,
    })
    plan.action_publish()
    assert plan.state == "published"

    batch = Batch.with_context(ya_create_production_batch=True).create({
        "delivery_date": date, "slot": slot,
        "state": "pre_production",
        "line_ids": [(0, 0, {
            "planning_id": plan.id,
            "kitchen_code": plan.kitchen_code,
            "product_id": source_line.product_id.id,
            "reference": source_line.reference,
            "bom_id": source_bom.id,
            "qty_requested": 0,
            "qty_production": units_per_batch,
            "qty_surplus": units_per_batch,
            "qty_shortage": 0,
            "max_capacity": max_capacity,
            "uom_id": source_line.product_id.uom_id.id,
        })],
        "staged_at": fields.Datetime.now(),
        "staged_by": env.user.id,
    })
    ids["batch"] = batch.id
    bline = batch.line_ids.ensure_one()

    pt = source_bom.picking_type_id
    mo = MO.with_context(
        tracking_disable=True, mail_notify_force_send=False,
    ).create({
        "product_id": source_line.product_id.id,
        "product_qty": float(units_per_batch),
        "product_uom_id": source_line.product_id.uom_id.id,
        "bom_id": source_bom.id,
        "picking_type_id": pt.id,
        "location_src_id": pt.default_location_src_id.id,
        "location_dest_id": pt.default_location_dest_id.id,
        "company_id": pt.company_id.id,
        "date_start": fields.Datetime.now(),
        "origin": "ROLLBACK_ONLY / YA SO AFTER MO1",
        "ya_packing_batch_line_id": bline.id,
    })
    ids["mo1"] = mo.id
    mo.action_confirm()
    assert mo.state not in ("draft", "cancel", "done"), "MO1_DID_NOT_CONFIRM"
    bline.with_context(ya_release_production_batch=True).write({
        "mo_id": mo.id
    })
    batch.sudo().with_context(ya_release_production_batch=True).write({
        "state": "production_ok",
        "released_at": fields.Datetime.now(),
        "released_by": env.user.id,
    })
    assert batch.state == "production_ok"
    assert bline.mo_id == mo
    assert not batch.ya_store_delivery_ids
    assert not batch.ya_fg_transfer_ids.filtered(lambda p: p.state == "done")
    print("SYNTHETIC_MO1_RELEASED:", "BATCH:", batch.id,
          "MO1:", mo.id, "MO1_QTY:", units_per_batch,
          "DATE:", date, "SLOT:", slot)

    def new_ya_quote(qty):
        return Sale.with_context(
            default_ya_is_capacity_so=True,
            tracking_disable=True,
            mail_create_nosubscribe=True,
            mail_notify_force_send=False,
        ).create({
            "partner_id": Sample.partner_id.id,
            "company_id": Sample.company_id.id,
            "warehouse_id": Sample.warehouse_id.id,
            "pricelist_id": Sample.pricelist_id.id,
            "order_line": [(0, 0, {
                "product_id": source_line.product_id.id,
                "name": source_line.product_id.display_name,
                "product_uom_qty": float(qty),
                "product_uom_id": source_line.product_id.uom_id.id,
                "price_unit": source_line.product_id.lst_price,
            })],
        })

    def confirm_and_assert(order, expected_mo2):
        proposal = order._ya_prepare_locked_booking(date, slot)
        checks = proposal["capacity_checks"]
        assert len(checks) == 1, "INVALID_SKU_CAPACITY_PROPOSAL"
        calculation = checks[0]["calculation"]
        assert calculation["mo1_output"] == units_per_batch, "MO1_NOT_REUSED"
        assert calculation["incremental_mo2_output_needed"] == expected_mo2, (
            "MO2_INCREMENT_WRONG: %s expected %s"
            % (calculation["incremental_mo2_output_needed"], expected_mo2)
        )
        print("PRE_CONFIRM_CAPACITY:", "SO:", order.id,
              "MO1_REUSE:", calculation["mo1_output"],
              "MO2_INCREMENT_NEEDED:", expected_mo2)
        action = env["ya.sale.capacity.confirm.wizard"].with_context(
            tracking_disable=True, mail_notify_force_send=False,
        ).create({
            "order_id": order.id, "delivery_date": date, "slot": slot
        }).action_check_and_confirm()
        assert action.get("res_id") == order.id
        assert order.state in ("sale", "done")
        assert not order.picking_ids, "YA_SO_EARLY_DELIVERY_CREATED"
        entries = Ledger.search([("order_id", "=", order.id)])
        assert len(entries) == 1
        assert entries.planning_line_id == plan_line
        return entries

    so1 = new_ya_quote(1)
    ids["so1"] = so1.id
    r1 = confirm_and_assert(so1, 0)
    print("SO1_REUSED_EXISTING_MO1_PASS")

    # Combined SO demand after SO2 = 1 + one whole batch.
    # For any positive batch, this rounds to TWO batches; MO1 already
    # covers one, so incremental MO2 proposal must be exactly one batch.
    so2 = new_ya_quote(units_per_batch)
    ids["so2"] = so2.id
    r2 = confirm_and_assert(so2, units_per_batch)
    assert r1.qty_required == 1
    assert r2.qty_required == units_per_batch
    print("SO2_ONLY_INCREMENTAL_MO2_PROPOSED_PASS")

    # No MO2 is created by Confirm; it is a subsequent separate release.
    assert MO.sudo().search_count([
        ("ya_packing_batch_line_id", "=", bline.id)
    ]) == 1, "UNEXPECTED_EXTRA_MO"
    assert not batch.ya_store_delivery_ids, "PREMATURE_STORE_DELIVERY"
    assert len(Ledger.search([
        ("delivery_date", "=", date), ("slot", "=", slot)
    ])) == 2, "EXPECTED_TWO_ATOMIC_CAPACITY_LEDGER_ROWS"

    overcap = new_ya_quote(max_capacity)
    ids["overcap"] = overcap.id
    try:
        env["ya.sale.capacity.confirm.wizard"].create({
            "order_id": overcap.id, "delivery_date": date, "slot": slot
        }).action_check_and_confirm()
        raise AssertionError("OVERCAP_SO_WRONGLY_ACCEPTED")
    except UserError as exc:
        print("OVERCAP_REJECTED:", str(exc)[:200])
    assert overcap.state in ("draft", "sent")
    assert not Ledger.search_count([("order_id", "=", overcap.id)])
    print("MO1_MO2_CAPACITY_LIMIT_PASS")

    # Release is time-gated H-1 15:30 WIB. Patch the clock ONLY in this
    # ephemeral Odoo shell, never via persisted server code/context bypass.
    # This synthetic date remains valid and all objects roll back.
    synthetic_release_clock = datetime.combine(
        date - timedelta(days=1), time(15, 31),
        tzinfo=ZoneInfo("Asia/Jakarta"),
    )
    with patch.object(
        mo2_release, "_now_wib",
        return_value=synthetic_release_clock,
    ):
        final = batch.with_user(packing_actor).with_company(
            Sample.company_id
        )._ya_release_final_mo2()
        ids["final"] = final.id
        lines = final.line_ids
        assert len(lines) == 1, "MO2_ONE_SKU_EXPECTED"
        line = lines.ensure_one()
        assert line.planning_line_id == plan_line
        assert line.qty_mo1 == units_per_batch
        assert line.qty_mo2 == units_per_batch
        assert line.qty_so == 1 + units_per_batch
        assert line.qty_ro_direct == 0 and line.qty_ro_package == 0
        assert line.qty_mo1 + line.qty_mo2 <= max_capacity
        mo2 = line.mo_id
        ids["mo2"] = mo2.id
        assert mo2.state not in ("draft", "cancel", "done")
        assert not mo2.ya_packing_batch_line_id, (
            "MO2_WRONGLY_LINKED_TO_MO1_FASE1_FIELD"
        )
        assert bline.mo_id == mo, "MO1_WAS_OVERWRITTEN"
        assert mo2.id != mo.id
        assert MO.sudo().search_count([
            ("ya_packing_batch_line_id", "=", bline.id),
        ]) == 1, "MO1_UNIQUE_INVARIANT_BROKEN"
        print("NATIVE_MO2_RELEASE_PASS:", "FINALIZATION:", final.id,
              "MO1:", mo.id, "MO2:", mo2.id,
              "MO2_QTY:", line.qty_mo2, "MAX:", max_capacity)

        try:
            batch.with_user(packing_actor).with_company(
                Sample.company_id
            )._ya_release_final_mo2()
            raise AssertionError("DUPLICATE_MO2_FINALIZATION_ACCEPTED")
        except UserError as exc:
            print("DUPLICATE_MO2_RELEASE_REJECTED:", str(exc)[:200])
        assert len(final.line_ids) == 1
        print("MO2_ONE_TIME_DATE_SLOT_GUARD_PASS")

        # The new CDC wave uses the confirmed MO2's real native raw moves,
        # never the original MO1 raw moves or frozen RO allocations.
        materials = {}
        for raw in mo2.move_raw_ids.filtered(lambda x: x.state != "cancel"):
            base = raw.product_uom._compute_quantity(
                raw.product_uom_qty, raw.product_id.uom_id, round=False
            )
            materials[raw.product_id.id] = (
                materials.get(raw.product_id.id, 0.0) + base
            )
        materials = {
            pid: qty for pid, qty in materials.items() if qty > 0
        }
        assert materials, "EXPECTED_MO2_RAW_MATERIAL_COMPONENTS"
        cdc_picking = line.with_user(stock_actor).with_company(
            Sample.company_id
        )._ya_create_mo2_cdc_transfer()
        ids["cdc_picking"] = cdc_picking.id
        assert cdc_picking.ya_mo2_material_release_line_id == line
        assert not cdc_picking.ya_mr_batch_id, (
            "MO2_MUST_NOT_USE_FASE1_UNIQUE_MR_BATCH_KITCHEN"
        )
        assert cdc_picking.state not in ("done", "cancel"), (
            "CDC_TRANSFER_MUST_REMAIN_UNVALIDATED"
        )
        actual = {}
        for move in cdc_picking.move_ids:
            pid = move.product_id.id
            actual[pid] = actual.get(pid, 0.0) + (
                move.product_uom._compute_quantity(
                    move.product_uom_qty, move.product_id.uom_id,
                    round=False,
                )
            )
        assert set(materials) == set(actual), (
            "MO2_CDC_RAW_SKU_SET_DIFFERS_FROM_NATIVE_MO2"
        )
        for pid, qty in materials.items():
            product = env["product.product"].browse(pid)
            assert abs(actual[pid] - qty) <= product.uom_id.rounding, (
                "MO2_CDC_RAW_QTY_NOT_EQUAL_TO_MO2: %s" % pid
            )
        print("MO2_CDC_TRANSFER_CREATED_NOT_VALIDATED_PASS:",
              "MO2:", mo2.id, "PICKING:", cdc_picking.id,
              "RAW_SKUS:", len(actual))

        # Double-click must reopen exactly same native picking.
        again = line.with_user(stock_actor).with_company(
            Sample.company_id
        )._ya_create_mo2_cdc_transfer()
        assert again.id == cdc_picking.id
        assert len(line.ya_mo2_material_picking_ids) == 1
        assert not batch.mr_native_transfer_ids
        print("MO2_CDC_DOUBLE_CLICK_NO_DUPLICATE_PASS")
        # Mandatory negative FG gate on v19.0.1.1.3. A Confirmed
        # MO2 and unvalidated CDC demand must never create a PCK picking.
        try:
            line.with_user(stock_actor).with_company(
                Sample.company_id
            )._ya_create_mo2_fg_transfer()
            raise AssertionError("UNFINISHED_MO2_FG_WRONGLY_ALLOWED")
        except UserError as exc:
            assert "DONE native MO2" in str(exc), (
                "UNEXPECTED_FG_REJECTION: %s" % exc
            )
        assert not line.ya_mo2_fg_picking_ids
        print("MO2_FG_UNFINISHED_BLOCKED_PASS")

        # POSITIVE PATH: actual Odoo CDC stock transfer and MRP completion,
        # no fake state or synthetic stock quants. All will be rolled back.
        cdc_wh = env["stock.warehouse"].sudo().search([
            ("company_id", "=", Sample.company_id.id),
            ("code", "=", "CDC")])
        pck_wh = env["stock.warehouse"].sudo().search([
            ("company_id", "=", Sample.company_id.id),
            ("code", "=", "PCK")])
        kitchen = mo2.picking_type_id.warehouse_id
        assert len(cdc_wh) == len(pck_wh) == 1 and kitchen
        assert len({cdc_wh.id, pck_wh.id, kitchen.id}) == 3
        assert not mo2.workorder_ids, "UNEXPECTED_WO_ON_MO2"
        assert mo2.product_id.tracking == "none"
        assert all(env["product.product"].browse(pid).tracking == "none"
                   for pid in materials)
        qmodel = env["stock.quant"].sudo().with_company(Sample.company_id)

        def stock_at(pid, loc):
            quants = qmodel.search([
                ("company_id", "=", Sample.company_id.id),
                ("product_id", "=", pid), ("location_id", "=", loc.id),
                ("lot_id", "=", False), ("owner_id", "=", False),
                ("package_id", "=", False)])
            return (sum(quants.mapped("quantity")),
                    sum(quants.mapped("reserved_quantity")))

        before = {}
        pairs = [(pid, loc) for pid in materials for loc in
                 (cdc_wh.lot_stock_id, kitchen.lot_stock_id)]
        pairs += [(mo2.product_id.id, kitchen.lot_stock_id),
                  (mo2.product_id.id, pck_wh.lot_stock_id)]
        for pid, loc in pairs:
            before[(pid, loc.id)] = stock_at(pid, loc)
        for pid, qty in materials.items():
            cdc_qty, cdc_reserved = stock_at(pid, cdc_wh.lot_stock_id)
            assert cdc_qty - cdc_reserved >= qty - 1e-7, (
                "STOP_INSUFFICIENT_CDC_FOR_NATIVE_TEST: %s" % pid)
        assert stock_at(mo2.product_id.id, kitchen.lot_stock_id)[1] == 0
        print("NATIVE_STOCK_BASELINE_CAPTURED:", len(before))

        # Native Odoo CDC picking validates actual stock movement.
        real_cdc = cdc_picking.with_user(stock_actor).with_company(
            Sample.company_id)
        real_cdc.action_confirm()
        real_cdc.action_assign()
        for raw_move in real_cdc.move_ids:
            raw_move.write({"quantity": raw_move.product_uom_qty})
        result = real_cdc.with_context(
            skip_immediate=True, skip_backorder=True,
            cancel_backorder=True).button_validate()
        assert real_cdc.state == "done" and all(
            m.state == "done" for m in real_cdc.move_ids), (
            "MO2_CDC_NATIVE_VALIDATE_NOT_DONE: %s" % str(result)[:200])
        for pid, qty in materials.items():
            cdc_before, _ = before[(pid, cdc_wh.lot_stock_id.id)]
            kit_before, _ = before[(pid, kitchen.lot_stock_id.id)]
            cdc_after, _ = stock_at(pid, cdc_wh.lot_stock_id)
            kit_after, _ = stock_at(pid, kitchen.lot_stock_id)
            assert abs(cdc_after - (cdc_before - qty)) < 1e-7
            assert abs(kit_after - (kit_before + qty)) < 1e-7
            assert cdc_after >= 0, "MO2_CDC_WOULD_CREATE_NEGATIVE_STOCK"
        print("MO2_CDC_NATIVE_DONE_STOCK_DELTAS_PASS")

        # Odoo 19 native MO completion sets real raw and finished moves.
        # Do NOT force MO state, move states, or create stock quants manually.
        real_mo2 = mo2.with_user(packing_actor).with_company(
            Sample.company_id).with_context(
                tracking_disable=True, mail_notify_force_send=False)
        real_mo2.action_assign()
        real_mo2.write({"qty_producing": float(units_per_batch)})
        result = real_mo2.with_context(
            skip_backorder=True, skip_redirection=True).button_mark_done()
        assert real_mo2.state == "done", (
            "NATIVE_MO2_DID_NOT_COMPLETE: %s" % str(result)[:180])
        native_finished = real_mo2.move_finished_ids.filtered(
            lambda x: x.state == "done"
            and x.product_id == mo2.product_id
            and x.location_dest_id == kitchen.lot_stock_id)
        done_qty = sum(
            x.product_uom._compute_quantity(
                x.quantity, mo2.product_id.uom_id, round=False)
            for x in native_finished)
        assert native_finished and abs(done_qty - units_per_batch) < 1e-7
        fg_before, _ = before[(mo2.product_id.id, kitchen.lot_stock_id.id)]
        fg_after, _ = stock_at(mo2.product_id.id, kitchen.lot_stock_id)
        assert abs(fg_after - (fg_before + done_qty)) < 1e-7, (
            "MO2_DONE_DID_NOT_POST_FINISHED_STOCK")
        assert not mo2.workorder_ids and bline.mo_id == mo
        print("NATIVE_MO2_DONE_STOCK_DELTAS_PASS:",
              "MO2:", mo2.id, "FG:", done_qty)

        fg = line.with_user(stock_actor).with_company(
            Sample.company_id)._ya_create_mo2_fg_transfer()
        ids["fg_picking"] = fg.id
        assert fg.state == "draft" and len(fg.move_ids) == 1
        assert fg.ya_mo2_fg_release_line_id == line
        assert not fg.ya_fg_batch_id and not fg.ya_mr_batch_id
        move = fg.move_ids.ensure_one()
        assert move.state == "draft" and move.quantity == 0
        assert abs(move.product_uom_qty - done_qty) < 1e-7
        assert move.location_id == kitchen.lot_stock_id
        assert move.location_dest_id == pck_wh.lot_stock_id
        assert stock_at(mo2.product_id.id, pck_wh.lot_stock_id) == (
            before[(mo2.product_id.id, pck_wh.lot_stock_id.id)])
        again = line.with_user(stock_actor).with_company(
            Sample.company_id)._ya_create_mo2_fg_transfer()
        assert again.id == fg.id and len(line.ya_mo2_fg_picking_ids) == 1
        assert not batch.ya_fg_transfer_ids and not batch.ya_store_delivery_ids
        print("MO2_FG_NATIVE_DRAFT_CREATION_PASS:",
              "PICKING:", fg.id, "QTY:", done_qty)
        print("MO2_FG_DOUBLE_CLICK_NO_DUPLICATE_PASS")
        ids["stock_before"] = [
            (pid, loc.id, *before[(pid, loc.id)]) for pid, loc in pairs]
        ids["synthetic_moves"] = list(set(
            real_mo2.move_raw_ids.ids + real_mo2.move_finished_ids.ids
            + real_cdc.move_ids.ids + fg.move_ids.ids))
        if "stock_valuation_layer_ids" in env["stock.move"]._fields:
            ids["valuation_ids"] = env["stock.move"].sudo().browse(
                ids["synthetic_moves"]).mapped(
                    "stock_valuation_layer_ids").ids


    # The operational 27-Nov batch (or any other advanced batch) must
    # remain blocked even when the release clock is inside the allowed
    # window. This check is read-only, never edits real historical data.
    advanced_batch = Batch.sudo().search([
        ("state", "=", "production_ok"),
        ("delivery_date", "!=", date),
        ("slot", "=", "S1"),
    ]).filtered(lambda b: bool(b.ya_store_delivery_ids)
               or bool(b.ya_fg_transfer_ids))[:1]
    if advanced_batch:
        archived_clock = datetime.combine(
            advanced_batch.delivery_date - timedelta(days=1),
            time(15, 31), tzinfo=ZoneInfo("Asia/Jakarta"),
        )
        with patch.object(mo2_release, "_now_wib", return_value=archived_clock):
            try:
                advanced_batch.with_user(packing_actor).with_company(
                    Sample.company_id
                )._ya_prepare_mo2_final_release()
                raise AssertionError("ADVANCED_PACKING_WAS_WRONGLY_ALLOWED")
            except UserError as exc:
                assert "already exist" in str(exc), (
                    "REJECTION_NOT_PHYSICAL_STAGE: %s" % exc
                )
                print("EXISTING_ADVANCED_PACKING_MO2_REJECTED_PASS",
                      "BATCH:", advanced_batch.id)

    # The actual clock is restored. Neither native MO2 nor Confirm should
    # create a PCK picking or customer/store delivery in this step.
    assert not batch.ya_store_delivery_ids
    assert not batch.ya_fg_transfer_ids
    assert not so1.picking_ids and not so2.picking_ids
    assert len(Ledger.search([
        ("delivery_date", "=", date), ("slot", "=", slot),
    ])) == 2
    success = True
finally:
    env.cr.rollback()
    print("EXPLICIT_ROLLBACK_EXECUTED")

env.invalidate_all()
if ids.get("mo1"):
    assert not MO.sudo().browse(ids["mo1"]).exists(), "MO1_REMAINED_AFTER_ROLLBACK"
if ids.get("mo2"):
    assert not MO.sudo().browse(ids["mo2"]).exists(), "MO2_REMAINED_AFTER_ROLLBACK"
if ids.get("cdc_picking"):
    assert not env["stock.picking"].sudo().browse(
        ids["cdc_picking"]
    ).exists(), "MO2_CDC_PICKING_REMAINED_AFTER_ROLLBACK"
if ids.get("fg_picking"):
    assert not env["stock.picking"].sudo().browse(
        ids["fg_picking"]).exists(), "MO2_FG_PICKING_PERSISTED"
if ids.get("synthetic_moves"):
    assert not env["stock.move"].sudo().browse(
        ids["synthetic_moves"]).exists(), "SYNTHETIC_NATIVE_MOVES_PERSISTED"
if ids.get("valuation_ids"):
    assert not env["stock.valuation.layer"].sudo().browse(
        ids["valuation_ids"]).exists(), "SYNTHETIC_VALUATION_PERSISTED"
if ids.get("stock_before"):
    for pid, loc, expected_qty, expected_reserved in ids["stock_before"]:
        quants = env["stock.quant"].sudo().search([
            ("company_id", "=", Sample.company_id.id),
            ("product_id", "=", pid), ("location_id", "=", loc),
            ("lot_id", "=", False), ("owner_id", "=", False),
            ("package_id", "=", False)])
        qty = sum(quants.mapped("quantity"))
        reserved = sum(quants.mapped("reserved_quantity"))
        assert abs(qty - expected_qty) < 1e-7 and abs(
            reserved - expected_reserved) < 1e-7, (
                "STOCK_NOT_RESTORED_AFTER_ROLLBACK: %s/%s" % (pid, loc))
    print("NATIVE_STOCK_ROLLBACK_VERIFIED")

if ids.get("final"):
    assert not env["ya.sale.mo2.finalization"].sudo().browse(
        ids["final"]
    ).exists(), "MO2_FINALIZATION_REMAINED_AFTER_ROLLBACK"
if ids.get("planning"):
    assert not Planning.sudo().browse(ids["planning"]).exists(), (
        "PLANNING_REMAINED_AFTER_ROLLBACK"
    )
if ids.get("so1"):
    assert not Sale.sudo().browse(ids["so1"]).exists(), "SO1_REMAINED_AFTER_ROLLBACK"
if ids.get("so2"):
    assert not Sale.sudo().browse(ids["so2"]).exists(), "SO2_REMAINED_AFTER_ROLLBACK"
assert success, "NATIVE_MO2_ROLLBACK_TEST_INCOMPLETE"
print("FASE2_YA_NATIVE_MO2_DONE_FG_DRAFT_ROLLBACK_PASS")
print("SCOPE: NATIVE CDC DONE + MO2 DONE + FG PICKING DRAFT; FG NOT VALIDATED, NO SO/RO DO")
print("NO_TEST_OBJECTS_COMMITTED")
