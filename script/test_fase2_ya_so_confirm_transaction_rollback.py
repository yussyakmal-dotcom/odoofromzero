"""Full ORM rollback trial of clone-only YA SO Confirm + capacity ledger.

Run only AFTER addon upgrade on clone. This creates test data in the current
transaction and explicitly rolls it all back. No stock/MO/DO/invoice writes
are intentional. Asserts native procurement was suppressed and capacity was
booked, then confirms that exceeding Published Planning Max is rejected.
"""
from collections import Counter
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo
from odoo import fields
from odoo.exceptions import UserError

CLONE = "erp-yussyakmal-mrp-test-RO_SO"
assert env.cr.dbname == CLONE, "STOP_WRONG_DATABASE"
print("DATABASE:", env.cr.dbname)
print("MODE: TRANSACTION_ROLLBACK_TEST_YA_SO_CONFIRM")

Sale = env["sale.order"]
Plan = env["ya.production.planning"]
Ledger = env["ya.sale.capacity.reservation"].sudo()
Sample = Sale.sudo().search(
    [("ya_is_capacity_so", "=", True)], limit=1
)
assert Sample and Sample.partner_id, "STOP_MISSING_YA_QUOTE_PARTNER_FOR_TEST"
assert env["ir.module.module"].search(
    [("name", "=", "ya_sale_production_capacity")], limit=1
).installed_version == "19.0.1.1.0", "STOP_ADDON_NOT_UPGRADED"

chosen = None
today = fields.Date.context_today(Sale)
now_wib = datetime.now(ZoneInfo("Asia/Jakarta"))
all_published = Plan.sudo().search([
    ("state", "=", "published"),
])
plannings = all_published.filtered(lambda p: p.delivery_date > today)
by_schedule = {}
for p in plannings:
    key = (p.delivery_date, p.slot)
    by_schedule.setdefault(key, []).append(p)
reject_counts = Counter()
reject_examples = {}


def skip(reason, product_id=None, date=None, slot=None):
    reject_counts[reason] += 1
    if reason not in reject_examples:
        reject_examples[reason] = (str(date or ""), slot or "", product_id or 0)


print("TODAY_ODOO:", today, "NOW_WIB:", now_wib.isoformat())
print("PUBLISHED_ALL:", len(all_published),
      "PUBLISHED_FUTURE:", len(plannings),
      "FUTURE_DATE_SLOTS:", len(by_schedule),
      "FUTURE_PLANNING_LINES:", sum(len(p.line_ids) for p in plannings))
print("FUTURE_SCHEDULES:", [
    (str(key[0]), key[1], len(items),
     sum(len(p.line_ids) for p in items))
    for key, items in sorted(by_schedule.items())[:12]
])

for (date, slot), schedules in sorted(by_schedule.items()):
    dispatch = datetime.combine(
        date, {"S1": time(5), "S2": time(9), "S3": time(11)}[slot],
        tzinfo=ZoneInfo("Asia/Jakarta"),
    )
    if now_wib >= dispatch:
        skip("SLOT_ALREADY_DEPARTED", date=date, slot=slot)
        continue
    if slot == "S1" and now_wib > datetime.combine(
            date - timedelta(days=1), time(15),
            tzinfo=ZoneInfo("Asia/Jakarta")):
        skip("S1_CUTOFF_EXPIRED", date=date, slot=slot)
        continue
    if Ledger.search_count([("delivery_date", "=", date), ("slot", "=", slot)]):
        skip("SLOT_ALREADY_HAS_SO_LEDGER", date=date, slot=slot)
        continue
    batch = env["ya.packing.batch"].sudo().search([
        ("delivery_date", "=", date), ("slot", "=", slot),
    ], limit=1)
    if batch:
        skip("SLOT_ALREADY_HAS_PACKING_BATCH", date=date, slot=slot)
        continue
    candidates = Counter(
        line.product_id.id for p in schedules for line in p.line_ids
    )
    for p in schedules:
        for line in p.line_ids:
            product = line.product_id
            info = (product.id, date, slot)
            if line.max_capacity <= 0:
                skip("SKU_NONPOSITIVE_MAX", *info)
                continue
            if candidates[product.id] != 1:
                skip("SKU_ROUTE_DUPLICATED", *info)
                continue
            if product.categ_id.complete_name == "All / Produk Jadi / Paket":
                skip("SKU_IS_PAKET", *info)
                continue
            try:
                bom = line._capacity_bom()
                pt = bom.picking_type_id
                expected_wh = " ".join(
                    ("Dapur " + (line.planning_id.workcenter_id.name or "")
                    ).casefold().split())
                actual_wh = " ".join(
                    (pt.warehouse_id.name or "").casefold().split()) if pt else ""
                invalid_route = (
                    ("BOM_INACTIVE" if not bom.active else None) or
                    ("BOM_NOT_NORMAL" if bom.type != "normal" else None) or
                    ("BOM_TEMPLATE_DIFFERS" if bom.product_tmpl_id != product.product_tmpl_id else None) or
                    ("BOM_PRODUCT_DIFFERS" if bom.product_id and bom.product_id != product else None) or
                    ("NO_MANUFACTURING_PICKING_TYPE" if not pt else None) or
                    ("NO_MANUFACTURING_WAREHOUSE" if not pt.warehouse_id else None) or
                    ("NO_MANUFACTURING_SOURCE" if not pt.default_location_src_id else None) or
                    ("NO_MANUFACTURING_DEST" if not pt.default_location_dest_id else None) or
                    ("DEST_NOT_KITCHEN_STOCK" if pt.default_location_dest_id != pt.warehouse_id.lot_stock_id else None) or
                    ("KITCHEN_NAME_ROUTE_DIFFERS" if actual_wh != expected_wh else None) or
                    ("SALE_COMPANY_DIFFERS_FROM_KITCHEN" if pt.company_id != Sample.company_id else None)
                )
                if invalid_route:
                    skip(invalid_route, *info)
                    if invalid_route == "KITCHEN_NAME_ROUTE_DIFFERS":
                        print("ROUTE_NAME_EXAMPLE:", line.id,
                              "WORKCENTER:", line.planning_id.workcenter_id.name,
                              "WAREHOUSE:", pt.warehouse_id.name)
                    continue
                output = bom.product_uom_id._compute_quantity(
                    bom.product_qty, product.uom_id, round=False)
                maximum = line.uom_id._compute_quantity(
                    line.max_capacity, product.uom_id, round=False)
                if output <= 0 or abs(output - round(output)) > 1e-9:
                    skip("BOM_OUTPUT_NOT_POSITIVE_WHOLE", *info)
                    continue
                if maximum < output:
                    skip("PLANNING_MAX_LESS_THAN_ONE_BOM", *info)
                    continue
                if abs(maximum - round(maximum)) > 1e-9:
                    skip("PLANNING_MAX_FRACTIONAL_BASE_UOM", *info)
                    continue
                if int(round(maximum)) % int(round(output)):
                    skip("PLANNING_MAX_NOT_MULTIPLE_OF_BOM", *info)
                    continue
            except (UserError, ValueError) as exc:
                skip("BOM_LOOKUP_ERROR", *info)
                if reject_counts["BOM_LOOKUP_ERROR"] <= 2:
                    print("BOM_LOOKUP_ERROR_SAMPLE:", line.id, str(exc)[:200])
                continue
            chosen = (date, slot, product, int(round(maximum)), line)
            break
        if chosen:
            break
    if chosen:
        break

print("SELECTION_REJECTION_COUNTS:", sorted(reject_counts.items()))
print("SELECTION_REJECTION_EXAMPLES:", sorted(reject_examples.items()))
assert chosen, (
    "STOP_NO_VALID_FUTURE_PUBLISHED_SKU: see reason counts above; "
    "no test SO created; no business data changed"
)
date, slot, product, max_qty, plan_line = chosen
print("SELECTED_DATE_SLOT:", date, slot)
print("PLANNING_LINE_ID:", plan_line.id, "PRODUCT_ID:", product.id,
      "CAPACITY_BASE_UOM:", max_qty)


def make_test_quotation(qty):
    # Reuse only partner/configuration from a *test clone* YA quotation.
    # Never edit the existing owner's quotation.
    order = Sale.with_context(
        default_ya_is_capacity_so=True, tracking_disable=True,
        mail_create_nosubscribe=True, mail_notify_force_send=False,
    ).create({
        "partner_id": Sample.partner_id.id,
        "company_id": Sample.company_id.id,
        "warehouse_id": Sample.warehouse_id.id,
        "pricelist_id": Sample.pricelist_id.id,
        "order_line": [(0, 0, {
            "product_id": product.id,
            "name": product.display_name,
            "product_uom_qty": float(qty),
            "product_uom_id": product.uom_id.id,
            "price_unit": product.lst_price,
        })],
    })
    assert order.ya_is_capacity_so and order.state in ("draft", "sent")
    return order


confirmed_test_id = None
try:
    test = make_test_quotation(1)
    confirmed_test_id = test.id
    print("TEST_QUOTE_CREATED:", test.id)
    wizard = env["ya.sale.capacity.confirm.wizard"].with_context(
        tracking_disable=True, mail_notify_force_send=False,
    ).create({
        "order_id": test.id, "delivery_date": date, "slot": slot,
    })
    action = wizard.action_check_and_confirm()
    assert action.get("res_id") == test.id, "CONFIRM_NAVIGATION_MISMATCH"
    assert test.state in ("sale", "done"), "YA_SO_NOT_CONFIRMED"
    assert test.ya_delivery_date == date and test.ya_slot == slot
    rows = Ledger.search([("order_id", "=", test.id)])
    assert len(rows) == 1, "RESERVATION_MUST_BE_ONE_SKU_LINE"
    assert rows.planning_line_id == plan_line
    assert rows.qty_required == 1
    assert not test.picking_ids, "PREMATURE_DO_CREATED"
    Move = env["stock.move"].sudo()
    if "sale_line_id" in Move._fields:
        assert not Move.search_count([
            ("sale_line_id", "in", test.order_line.ids),
        ]), "PREMATURE_STOCK_MOVE_CREATED"
    print("SO_CONFIRMED_WITH_ATOMIC_LEDGER_NO_DO_PASS")

    overcap = make_test_quotation(max_qty)
    try:
        env["ya.sale.capacity.confirm.wizard"].create({
            "order_id": overcap.id, "delivery_date": date, "slot": slot,
        }).action_check_and_confirm()
        raise AssertionError("OVERCAP_SO_WAS_ACCEPTED")
    except UserError as exc:
        print("OVERCAP_REJECTED:", str(exc)[:240])
    assert overcap.state in ("draft", "sent"), "OVERCAP_CHANGED_ORDER_STATE"
    assert not Ledger.search_count([("order_id", "=", overcap.id)])
    print("OVERCAP_NO_PARTIAL_BOOKING_PASS")
finally:
    env.cr.rollback()
    print("EXPLICIT_ROLLBACK_EXECUTED")

assert not env["sale.order"].sudo().browse(confirmed_test_id).exists()
print("FASE2_YA_SO_CONFIRM_ROLLBACK_PASS")
print("NO_BUSINESS_DATA_COMMITTED")
