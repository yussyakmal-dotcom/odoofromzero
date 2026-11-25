"""Clone-only YA Confirm integration test with temporary Published Planning.

The real future slot 2026-11-27 S1 may already have Packing DO/FG transfer.
Do not bypass its guard or modify its operational Planning/MOs/DOs.
Instead create one temporary kitchen Planning in an unused future slot,
using one existing valid published kitchen SKU/BoM as the template.
Confirm two temporary SOs and explicitly ROLLBACK everything.
NO COMMIT; run ONLY on erp-yussyakmal-mrp-test-RO_SO.
"""
from collections import Counter
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from odoo import fields
from odoo.exceptions import UserError

CLONE = "erp-yussyakmal-mrp-test-RO_SO"
assert env.cr.dbname == CLONE, "STOP_WRONG_DATABASE"
assert env["ir.module.module"].search(
    [("name", "=", "ya_sale_production_capacity")], limit=1
).installed_version in ("19.0.1.1.0", "19.0.1.1.1", "19.0.1.1.2"), "STOP_ADDON_NOT_UPGRADED"
assert env.user.has_group("sales_team.group_sale_salesman"), "STOP_SALES_ACCESS_REQUIRED"
assert env.user.has_group("mrp.group_mrp_manager"), "STOP_MRP_MANAGER_REQUIRED"

Sale = env["sale.order"]
Planning = env["ya.production.planning"]
PlanningLine = env["ya.production.planning.line"]
Ledger = env["ya.sale.capacity.reservation"].sudo()
Sample = Sale.sudo().search(
    [("ya_is_capacity_so", "=", True), ("partner_id", "!=", False)],
    limit=1,
)
assert Sample, "STOP_NO_SAMPLE_YA_PARTNER_FOR_TEST"
today = fields.Date.context_today(Sale)
print("DATABASE:", env.cr.dbname)
print("MODE: TEMP_PLANNING_SO_CONFIRM_ROLLBACK_ONLY")
print("NOW_WIB:", datetime.now(ZoneInfo("Asia/Jakarta")).isoformat())
print("EXISTING_YA_QUOTE_SAMPLE_ID:", Sample.id)

candidate_rejections = Counter()
source = None
source_bom = None
capacity = None

# TEMPLATE SELECTION IS READ-ONLY. An actual published kitchen SKU/BoM,
# preferably from the current available future schedule, is reused.
published = Planning.sudo().search(
    [("state", "=", "published")], order="delivery_date desc,slot,id"
)
routes = Counter(
    (p.delivery_date, p.slot, line.product_id.id)
    for p in published for line in p.line_ids
)
for plan in published:
    for line in plan.line_ids:
        product = line.product_id
        if line.max_capacity <= 0 or routes[
                (plan.delivery_date, plan.slot, product.id)] != 1:
            candidate_rejections["MAX_ZERO_OR_DUPLICATE_ROUTE"] += 1
            continue
        if product.categ_id.complete_name == "All / Produk Jadi / Paket":
            candidate_rejections["PACKAGE_SKU_NOT_SUITABLE_FOR_DIRECT_TEST"] += 1
            continue
        try:
            bom = line._capacity_bom()
            pt = bom.picking_type_id
            expected = " ".join(
                ("Dapur " + (plan.workcenter_id.name or "")).casefold().split()
            )
            actual = " ".join((pt.warehouse_id.name or "").casefold().split()
                              ) if pt and pt.warehouse_id else ""
            if (not bom.active or bom.type != "normal"
                    or bom.product_tmpl_id != product.product_tmpl_id
                    or (bom.product_id and bom.product_id != product)
                    or not pt or not pt.warehouse_id
                    or not pt.default_location_src_id
                    or not pt.default_location_dest_id
                    or pt.default_location_dest_id != pt.warehouse_id.lot_stock_id
                    or pt.company_id != Sample.company_id
                    or actual != expected):
                candidate_rejections["BOM_OR_KITCHEN_ROUTE_INVALID"] += 1
                continue
            output = bom.product_uom_id._compute_quantity(
                bom.product_qty, product.uom_id, round=False)
            maximum = line.uom_id._compute_quantity(
                line.max_capacity, product.uom_id, round=False)
            if (output <= 0 or abs(output - round(output)) > 1e-9
                    or maximum < output
                    or abs(maximum - round(maximum)) > 1e-9
                    or int(round(maximum)) % int(round(output))):
                candidate_rejections["OUTPUT_OR_MAX_INCOMPATIBLE"] += 1
                continue
            # Publishing draft Max uses raw BoM output (current SOP).
            from odoo.addons.ya_production_planning.models.capacity_rules import closest_batch_multiple
            if closest_batch_multiple(line.max_capacity, bom.product_qty) != line.max_capacity:
                candidate_rejections["DRAFT_PUBLISH_MAX_RULE"] += 1
                continue
        except (UserError, ValueError) as exc:
            candidate_rejections["BOM_RESOLUTION_ERROR"] += 1
            if candidate_rejections["BOM_RESOLUTION_ERROR"] <= 2:
                print("BOM_TEMPLATE_ERROR:", line.id, str(exc)[:200])
            continue
        source = line
        source_bom = bom
        capacity = int(round(maximum))
        break
    if source:
        break

print("TEMPLATE_SELECTION_REJECTIONS:", sorted(candidate_rejections.items()))
assert source, (
    "STOP_NO_VALID_PUBLISHED_KITCHEN_SKU_TEMPLATE; "
    "nothing created, no business changes"
)
print("TEMPLATE_SOURCE_PLANNING_LINE_ID:", source.id,
      "PRODUCT_ID:", source.product_id.id,
      "KITCHEN:", source.planning_id.kitchen_code,
      "BOM_ID:", source_bom.id, "CAPACITY_BASE_UOM:", capacity)

# An unused future date avoids the already-shipped 27 Nov batch.
test_date = None
test_slot = "S1"
for days in range(14, 75):
    date = today + timedelta(days=days)
    domain = [("delivery_date", "=", date), ("slot", "=", test_slot)]
    if (not Planning.sudo().search_count(domain)
            and not env["ya.packing.batch"].sudo().search_count(domain)
            and not Ledger.search_count(domain)
            and not Sale.sudo().search_count([
                ("ya_is_capacity_so", "=", True),
                ("ya_delivery_date", "=", date),
                ("ya_slot", "=", test_slot),
            ])):
        test_date = date
        break
assert test_date, "STOP_NO_UNUSED_FUTURE_DATE_SLOT; no writes"

created_plan_id = None
confirmed_test_id = None
try:
    # Only synthetic records are created in this transaction, never copying
    # production data or mutating pre-existing Published Planning/DO.
    plan = Planning.sudo().create({
        "delivery_date": test_date,
        "slot": test_slot,
        "kitchen_code": source.planning_id.kitchen_code,
        "workcenter_id": source.planning_id.workcenter_id.id,
        "state": "draft",
        "upload_filename": "ROLLBACK-ONLY-NO-UPLOAD",
    })
    created_plan_id = plan.id
    test_line = PlanningLine.sudo().create({
        "planning_id": plan.id,
        "product_id": source.product_id.id,
        "reference": source.reference,
        "max_capacity": source.max_capacity,
        "uom_id": source.uom_id.id,
        "bom_id": source_bom.id,
        "source_sheet": "ROLLBACK_ONLY",
        "source_row": 2,
    })
    plan.action_publish()
    assert plan.state == "published"
    print("TEMP_PLANNING_PUBLISHED:", plan.id, "LINE:", test_line.id,
          "DATE:", test_date, "SLOT:", test_slot)

    def make_quotation(qty):
        # Inherit only configuration from an existing TEST clone quotation.
        # Disable mail notification side effects; rollback still guaranteed.
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
                "product_id": source.product_id.id,
                "name": source.product_id.display_name,
                "product_uom_qty": float(qty),
                "product_uom_id": source.product_id.uom_id.id,
                "price_unit": source.product_id.lst_price,
            })],
        })

    test = make_quotation(1)
    confirmed_test_id = test.id
    print("TEMP_QUOTATION_CREATED:", test.id)
    action = env["ya.sale.capacity.confirm.wizard"].with_context(
        tracking_disable=True, mail_notify_force_send=False,
    ).create({
        "order_id": test.id,
        "delivery_date": test_date,
        "slot": test_slot,
    }).action_check_and_confirm()

    assert action.get("res_id") == test.id, "CONFIRM_ACTION_TARGET_WRONG"
    assert test.state in ("sale", "done"), "SO_NOT_CONFIRMED"
    assert test.ya_delivery_date == test_date
    assert test.ya_slot == test_slot
    rows = Ledger.search([("order_id", "=", test.id)])
    assert len(rows) == 1, "EXPECTED_ONE_RESERVATION_ROW"
    assert rows.planning_line_id == test_line
    assert rows.qty_required == 1
    assert not test.picking_ids, "PREMATURE_SALES_DELIVERY"
    Move = env["stock.move"].sudo()
    if "sale_line_id" in Move._fields:
        assert not Move.search_count([
            ("sale_line_id", "in", test.order_line.ids)
        ]), "PREMATURE_STOCK_MOVE"
    print("YA_SO_ATOMIC_CONFIRM_LEDGER_NO_EARLY_DO_PASS")

    overcap = make_quotation(capacity)
    try:
        env["ya.sale.capacity.confirm.wizard"].with_context(
            tracking_disable=True, mail_notify_force_send=False,
        ).create({
            "order_id": overcap.id,
            "delivery_date": test_date,
            "slot": test_slot,
        }).action_check_and_confirm()
        raise AssertionError("OVERCAP_SO_WAS_WRONGLY_ACCEPTED")
    except UserError as exc:
        print("OVERCAP_REJECTED:", str(exc)[:250])
    assert overcap.state in ("draft", "sent")
    assert not Ledger.search_count([("order_id", "=", overcap.id)])
    print("OVERCAP_NO_PARTIAL_BOOKING_PASS")
finally:
    env.cr.rollback()
    print("EXPLICIT_ROLLBACK_EXECUTED")

# Re-query to show the synthetic template and orders are no longer present.
env.invalidate_all()
assert not Planning.sudo().browse(created_plan_id).exists(), (
    "TEMP_PLANNING_REMAINED_AFTER_ROLLBACK"
)
if confirmed_test_id:
    assert not Sale.sudo().browse(confirmed_test_id).exists(), (
        "TEMP_QUOTATION_REMAINED_AFTER_ROLLBACK"
    )
print("FASE2_YA_SO_CONFIRM_ROLLBACK_PASS")
print("NO_TEMP_PLANNING_OR_SO_OR_CAPACITY_LEDGER_COMMITTED")
print("MO1_REUSE_MO2_PACKING_DISPATCH_NOT_TESTED_HERE")
