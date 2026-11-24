"""Owner-confirmed same test MO SUL/MO/00001: zero 2 remaining negatives.

Dedicated TEST DB only. Default PREVIEW and rollback. APPLY only with
an explicit environment token and a verified current TEST DB backup.
Native Odoo inventory adjustment; no direct quant SQL edits, no MO edits.
Only exact SUL/Stock two SKU balances previously shown by read-only audit.
This is distinct from the already COMMITTED 15-SKU adjustment; NEVER rerun
the 15-SKU APPLY to clean these two.

PREVIEW:
  sudo -u odoo19 /opt/odoo19/venv/bin/python3 \\
    /opt/odoo19/odoo/odoo-bin shell -c /etc/odoo19.conf \\
    -d erp-yussyakmal-mrp-test --no-http \\
    < script/opname_2_sul_same_mo_produce_all_ya.py

APPLY after backup and preview verified:
  sudo -u odoo19 env YA_SUL_2_OPNAME_APPLY=YES_TEST_ONLY_2_ZERO \\
    /opt/odoo19/venv/bin/python3 /opt/odoo19/odoo/odoo-bin \\
    shell -c /etc/odoo19.conf -d erp-yussyakmal-mrp-test \\
    --no-http < script/opname_2_sul_same_mo_produce_all_ya.py
"""
import os
from odoo.tools import float_compare

EXPECTED_DB = "erp-yussyakmal-mrp-test"
EXPECTED_WAREHOUSE = "SUL"
APPLY_KEY = "YA_SUL_2_OPNAME_APPLY"
APPLY_TOKEN = "YES_TEST_ONLY_2_ZERO"
token = os.environ.get(APPLY_KEY, "")
if token not in ("", APPLY_TOKEN):
    raise RuntimeError("REFUSED: invalid apply token, no changes")
APPLY = token == APPLY_TOKEN

# Two exact owner-identified test negative quants, not a wildcard.
# SKU: exact prior observed negative quantity, in product base UoM.
TARGET = {
    "10662": -1.0,
    "11436": -10.0,
}
assert len(TARGET) == 2
assert all(qty < 0 for qty in TARGET.values())

def get_negative_snapshot(Quant):
    return {
        q.id: (
            q.product_id.id,
            q.location_id.id,
            q.quantity,
            q.reserved_quantity,
            q.company_id.id,
        )
        for q in Quant.search([
            ("quantity", "<", -0.000001),
            ("location_id.usage", "in", ["internal", "transit"]),
            ("product_id.is_storable", "=", True),
        ])
    }


def run(env):
    if env.cr.dbname != EXPECTED_DB:
        raise RuntimeError("REFUSED: only dedicated MRP TEST database allowed")

    Warehouse = env["stock.warehouse"].sudo()
    Product = env["product.product"].sudo()
    Quant = env["stock.quant"].sudo()
    s = Warehouse.search([("code", "=", EXPECTED_WAREHOUSE)], limit=2)
    if len(s) != 1 or s.lot_stock_id.complete_name != "SUL/Stock":
        raise RuntimeError("REFUSED: SUL stock warehouse/location ambiguous")
    if s.lot_stock_id.usage != "internal" or not s.company_id:
        raise RuntimeError("REFUSED: not a valid internal stock location")
    if s.lot_stock_id.company_id and s.lot_stock_id.company_id != s.company_id:
        raise RuntimeError("REFUSED: SUL stock location belongs to another company")

    print("DATABASE:", env.cr.dbname)
    print("MODE:", "NATIVE_OPNAME_APPLY_2_TEST_ONLY" if APPLY else
          "NATIVE_OPNAME_DRY_RUN_2_TEST_ONLY")
    print("WAREHOUSE:", s.code, s.lot_stock_id.complete_name)
    print("TARGET_QTY_AFTER_PER_SKU: 0 (physical test inventory)")
    print("SKU_COUNT:", len(TARGET))

    snapshot = get_negative_snapshot(Quant)
    plans = []
    for sku, expected_before in TARGET.items():
        product = Product.search([("default_code", "=", sku)], limit=2)
        if len(product) != 1:
            raise RuntimeError("REFUSED: missing/duplicate product "+sku)
        prod = product[0]
        if not prod.is_storable or prod.tracking != "none":
            raise RuntimeError("REFUSED: nonstorable/lot-tracked SKU "+sku)
        if prod.company_id and prod.company_id != s.company_id:
            raise RuntimeError("REFUSED: product belongs to another company "+sku)
        if not prod.uom_id.rounding or prod.uom_id.rounding <= 0:
            raise RuntimeError("REFUSED: invalid product UoM rounding "+sku)

        # Match the actual root stock location and unique quant. No
        # lot/package/owner split can be silently rewritten.
        quants = Quant.search([
            ("product_id", "=", prod.id),
            ("location_id", "=", s.lot_stock_id.id),
        ])
        if len(quants) != 1:
            raise RuntimeError(
                "REFUSED: expected exactly one SUL/Stock quant for %s, got %s"
                % (sku, len(quants)))
        q = quants[0]
        if (q.company_id != s.company_id or q.lot_id or q.package_id or
                q.owner_id or q.reserved_quantity != 0):
            raise RuntimeError(
                "REFUSED: company/lot/package/owner/reservation changed for "
                +sku)
        if float_compare(q.quantity, expected_before,
                         precision_rounding=prod.uom_id.rounding) != 0:
            raise RuntimeError(
                "REFUSED: %s actual %s differs from previous audit %s; "
                "no automatic adjustment" %
                (sku, q.quantity, expected_before))
        if q.id not in snapshot:
            raise RuntimeError("REFUSED: expected negative SUL stock quant "+sku)
        plans.append((sku, prod, q, expected_before))

    target_quant_ids = {q.id for _, _, q, _ in plans}
    untouched_negatives = {
        qid: data for qid, data in snapshot.items()
        if qid not in target_quant_ids
    }
    print("NEGATIVE_QUANTS_BEFORE:", len(snapshot))
    print("EXACT_MATCHED_SUL_NEGATIVE_SKUS:", len(plans))
    print("OTHER_NEGATIVE_QUANTS_UNTOUCHED:", len(untouched_negatives))
    for sku, prod, q, before in plans:
        print("OPNAME_PLAN:",
              "sku:", sku,
              "before:", before,
              "counted:", 0.0,
              "delta:", -before,
              "uom:", prod.uom_id.name,
              "quant_id:", q.id)
    if not APPLY:
        print("PREVIEW_ONLY_2_SUL_OPNAME_OK")
        return

    adjusted = 0
    for sku, prod, q, before in plans:
        # Real Odoo native Inventory Adjustment; do not write quant.quantity
        # and do not fake stock.move/physical transfer.
        q.with_context(inventory_mode=True).write({
            "inventory_quantity": 0.0,
        })
        q.action_apply_inventory()
        env.flush_all()
        env.invalidate_all()
        after = sum(Quant.search([
            ("product_id", "=", prod.id),
            ("location_id", "=", s.lot_stock_id.id),
            ("company_id", "=", s.company_id.id),
        ]).mapped("quantity"))
        if float_compare(
            after, 0.0,
            precision_rounding=prod.uom_id.rounding
        ) != 0:
            raise RuntimeError(
                "REFUSED: post-opname SUL SKU %s stock %s not zero" %
                (sku, after))
        print("OPNAME_POSTED:", sku, "BEFORE:", before, "AFTER:", after)
        adjusted += 1

    # Must not alter any OTHER negative stock quant.
    new_snapshot = get_negative_snapshot(Quant)
    for qid, data in untouched_negatives.items():
        if qid not in new_snapshot:
            raise RuntimeError(
                "REFUSED: another negative quant %d changed/vanished" % qid)
        if new_snapshot[qid] != data:
            raise RuntimeError(
                "REFUSED: another negative quant %d was altered" % qid)
    unexpected = set(new_snapshot) - set(untouched_negatives)
    if unexpected:
        raise RuntimeError(
            "REFUSED: new unexpected internal/transit negatives: %s" %
            sorted(unexpected))
    if adjusted != 2 or len(new_snapshot) != len(untouched_negatives):
        raise RuntimeError(
            "REFUSED: negative-stock count mismatch after 2 adjustments")
    print("OPNAME_2_ALL_VERIFIED_BEFORE_COMMIT")
    print("UNRELATED_NEGATIVE_QUANTS_UNCHANGED:", len(untouched_negatives))
    env.cr.commit()
    print("OPNAME_2_SUL_TEST_COMMITTED_PASS")


try:
    run(env)
except Exception:
    env.cr.rollback()
    print("OPNAME_ABORTED_ROLLBACK_NO_PARTIAL_COMMIT")
    raise
else:
    if not APPLY:
        env.cr.rollback()
