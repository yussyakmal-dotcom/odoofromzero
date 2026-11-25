"""RO_SO clone-only transactional test: native MO1 reused by YA Sales.

All objects are synthetic in ONE uncommitted transaction:
Published Planning -> Packing Batch -> native confirmed MO1 -> YA SO1 -> YA SO2.
Tests computed incremental MO2, NOT MO2 release, RO allocation or physical DO.
An unconditional rollback in finally removes test Planning, MO1, SOs & ledger.
Never run against main or first-phase test databases.
"""
from collections import Counter
from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError

CLONE = "erp-yussyakmal-mrp-test-RO_SO"
assert env.cr.dbname == CLONE, "STOP_WRONG_DATABASE"
Version = env["ir.module.module"].sudo().search([
    ("name", "=", "ya_sale_production_capacity")
], limit=1)
assert Version and Version.state == "installed" and (
    Version.installed_version in ("19.0.1.1.0", "19.0.1.1.1", "19.0.1.1.2", "19.0.1.1.3")
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
print("DATABASE:", env.cr.dbname)
print("MODE: MO1_SO_CONFIRM_INCREMENTAL_MO2_ROLLBACK")
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
    success = True
finally:
    env.cr.rollback()
    print("EXPLICIT_ROLLBACK_EXECUTED")

env.invalidate_all()
if ids.get("mo1"):
    assert not MO.sudo().browse(ids["mo1"]).exists(), "MO1_REMAINED_AFTER_ROLLBACK"
if ids.get("planning"):
    assert not Planning.sudo().browse(ids["planning"]).exists(), (
        "PLANNING_REMAINED_AFTER_ROLLBACK"
    )
if ids.get("so1"):
    assert not Sale.sudo().browse(ids["so1"]).exists(), "SO1_REMAINED_AFTER_ROLLBACK"
if ids.get("so2"):
    assert not Sale.sudo().browse(ids["so2"]).exists(), "SO2_REMAINED_AFTER_ROLLBACK"
assert success, "MO1_SO_CONFIRM_TEST_INCOMPLETE"
print("FASE2_YA_SO_AFTER_MO1_ROLLBACK_PASS")
print("SCOPE: MO1_REUSE_AND_MO2_QTY_PREVIEW_ONLY; NO_MO2_RELEASE_OR_PACKING_DO")
print("NO_TEST_OBJECTS_COMMITTED")
