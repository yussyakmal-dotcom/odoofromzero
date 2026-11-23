"""READ ONLY — investigate ASN MO Not Available after CDC internal transfer.

Run from odoo-bin shell against erp-yussyakmal-mrp-test ONLY.
No create/write/action_assign/validate, SQL UPDATE, commits, or stock changes.
Compare standard MO Component Status with each raw move's source, forecast,
reservation and stock quants. This is a diagnostic, NOT a repair.
"""
from collections import defaultdict
from odoo.tools import float_compare

DB = "erp-yussyakmal-mrp-test"
assert env.cr.dbname == DB, "REFUSED: expected exact test database"
MISSING_MOS = (
    "ASN/MO/00002",
    "ASN/MO/00004",
    "ASN/MO/00005",
    "ASN/MO/00007",
    "ASN/MO/00008",
    "ASN/MO/00009",
    "ASN/MO/00010",
)
READY_CONTROL_MOS = ("ASN/MO/00001", "GRG/MO/00001")
MONITOR_PICKING = "CDC/INT/00003"
P = env["stock.picking"].sudo()
MO = env["mrp.production"].sudo()
Q = env["stock.quant"].sudo()
company_model = env["res.company"].sudo()
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_ASN_MO_AFTER_CDC_TRANSFER")
print("PICKING_MONITOR:", MONITOR_PICKING)
pickings = P.search([("name", "=", MONITOR_PICKING)])
for p in pickings:
    print("TRANSFER:", p.name,
          "| state:", p.state,
          "| operation:", p.picking_type_id.display_name,
          "| source:", p.location_id.complete_name,
          "| dest:", p.location_dest_id.complete_name,
          "| done_at:", p.date_done,
          "| move_count:", len(p.move_ids),
          "| zero_qty_positive_demand:", sum(
              1 for m in p.move_ids if m.quantity <= 0 and m.product_uom_qty > 0),
          "| short_lines:", sum(
              1 for m in p.move_ids
              if float_compare(m.quantity, m.product_uom_qty,
                               precision_rounding=m.product_uom.rounding or 0.00001) < 0))
if not pickings:
    print("TRANSFER_NOT_FOUND:", MONITOR_PICKING)

for name in MISSING_MOS + READY_CONTROL_MOS:
    mos = MO.search([("name", "=", name)])
    if len(mos) != 1:
        print("MO_LOOKUP:", name, "| count:", len(mos))
        continue
    mo = mos[0]
    root = mo.location_src_id
    print("MO:", mo.name,
          "| product:", mo.product_id.display_name,
          "| component_status:", mo.components_availability,
          "| state:", mo.state,
          "| warehouse:", mo.picking_type_id.warehouse_id.display_name,
          "| raw_source:", root.complete_name if root else "(NONE)",
          "| raw_moves:", len(mo.move_raw_ids))
    mismatches = []
    for move in mo.move_raw_ids:
        if move.state in ("cancel", "done"):
            continue
        product = move.product_id
        if not product:
            continue
        required = move.product_qty
        forecast = move.forecast_availability
        prec = product.uom_id.rounding or 0.00001
        shortage = float_compare(forecast, required, precision_rounding=prec) < 0
        # Print only shortages unless this is a one-line control.
        if not shortage and name in MISSING_MOS:
            continue
        source = move.location_id
        q = Q.search([
            ("product_id", "=", product.id),
            ("location_id", "child_of", source.id),
            ("location_id.usage", "=", "internal"),
            ("company_id", "=", mo.company_id.id),
        ])
        on_hand = sum(q.mapped("quantity"))
        reserved = sum(q.mapped("reserved_quantity"))
        raw_reserved = sum(
            line.product_uom_id._compute_quantity(
                line.quantity, product.uom_id, round=False)
            for line in move.move_line_ids
            if line.state not in ("cancel", "done")
        )
        print("  COMPONENT:", product.display_name,
              "| raw_move_state:", move.state,
              "| move_source:", source.complete_name,
              "| demand_product_uom:", round(required, 4),
              "| reserved_this_mo_product_uom:", round(raw_reserved, 4),
              "| forecast_available_product_uom:", round(forecast, 4),
              "| on_hand_source_subtree:", round(on_hand, 4),
              "| reserved_all_source_subtree:", round(reserved, 4),
              "| free_source_subtree:", round(on_hand-reserved, 4),
              "| tracked:", product.tracking)
        if shortage:
            mismatches.append(product.id)
    print("MO_SHORTAGE_COMPONENTS:", mo.name, len(mismatches))
print("READ_ONLY_ASN_MO_TRANSFER_AUDIT_OK")
