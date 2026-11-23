"""READ-ONLY tracing of Batch 3 manufacture -> Packing -> transit -> store.

Only erp-yussyakmal-mrp-test; no writes/postings/recomputation. A FINANCIAL
DIAGNOSTIC, not an accounting pass. Trace source stock moves and any SVL/GL
links actually present in this Odoo 19 Community installation.
"""
from collections import Counter

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "WRONG DB"
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_BATCH3_MRP_STORE_FINANCIAL_TRACE")
Batch = env["ya.packing.batch"].sudo()
batches = Batch.search([("delivery_date", "=", "2026-11-23"), ("slot", "=", "S2")])
print("BATCH_MATCHES:", len(batches))
assert len(batches) == 1, "Cannot uniquely identify Batch 3"
batch = batches[0]
assert batch.id == 3, "Batch identity unexpected; inspect first"
print("BATCH:", batch.id, batch.name, batch.state, "COMPANY:", env.company.name)

Picking = env["stock.picking"].sudo()
pickings = Picking.search([("ya_store_batch_id", "=", batch.id)],
                          order="id")
print("LINKED_STORE_PICKINGS:", len(pickings))
moved_ids = set()
for picking in pickings:
    print("PICKING:", picking.id, picking.name, picking.state,
          "STAGE:", picking.ya_store_stage,
          "SOURCE:", picking.location_id.complete_name,
          "SOURCE_USAGE:", picking.location_id.usage,
          "DESTINATION:", picking.location_dest_id.complete_name,
          "DEST_USAGE:", picking.location_dest_id.usage,
          "COMPANY:", picking.company_id.name)
    for move in picking.move_ids:
        print("  MOVE:", move.id, move.product_id.default_code,
              "STATE:", move.state,
              "DEMAND:", move.product_uom_qty,
              "DONE_QTY:", move.quantity,
              "UOM:", move.product_uom.name,
              "ORIGIN:", move.origin or "-")
        moved_ids.add(move.id)

mos = batch.line_ids.mapped("mo_id")
print("LINKED_MOS:", len(mos))
for mo in mos:
    print("MO:", mo.id, mo.name, mo.state, "SKU:", mo.product_id.default_code,
          "PLANNED:", mo.product_qty, "ACTUAL:", (
              mo.qty_producing if "qty_producing" in mo._fields else "FIELD_UNAVAILABLE"),
          "COST:", (mo.production_cost if "production_cost" in mo._fields else
                   "FIELD_UNAVAILABLE"),
          "SRC:", mo.location_src_id.complete_name,
          "DEST:", mo.location_dest_id.complete_name)
    for label, records in [("RAW", mo.move_raw_ids),
                           ("FINISHED", mo.move_finished_ids)]:
        for m in records:
            print("  MO_", label, "MOVE:", m.id,
                  "SKU:", m.product_id.default_code, "STATE:", m.state,
                  "QTY:", m.quantity, "UOM:", m.product_uom.name,
                  "SRC:", m.location_id.complete_name,
                  "DST:", m.location_dest_id.complete_name)
            moved_ids.add(m.id)

# Trace direct stock.move -> stock.valuation.layer or installed model equivalent.
StockMove = env["stock.move"].sudo()
Move = env["account.move"].sudo() if "account.move" in env.registry.models else None
SVL = env["stock.valuation.layer"].sudo() if "stock.valuation.layer" in env.registry.models else None
print("SVL_AVAILABLE:", bool(SVL is not None))
print("GL_AVAILABLE:", bool(Move is not None))
if SVL is not None:
    print("SVL_FIELDS:", {k: v.type for k, v in SVL._fields.items()
          if k in ("stock_move_id", "product_id", "quantity", "unit_cost", "value",
                   "remaining_value", "remaining_qty", "account_move_id",
                   "company_id", "description")})
    if "stock_move_id" in SVL._fields:
        layers = SVL.search([("stock_move_id", "in", sorted(moved_ids))], order="id")
        print("SVL_LINKED_TO_RELEVANT_MOVES:", len(layers))
        for layer in layers[:120]:
            vals = []
            for k in ("quantity", "unit_cost", "value", "remaining_value",
                      "account_move_id"):
                if k in SVL._fields:
                    obj = layer[k]
                    vals.append("%s=%s" % (k, obj.name if k == "account_move_id" and obj else obj))
            print("  SVL:", layer.id,
                  "STOCK_MOVE:", layer.stock_move_id.id,
                  "SKU:", layer.product_id.default_code,
                  "DETAIL:", " | ".join(vals))
        if len(layers) > 120:
            print("SVL_EXTRA_NOT_SHOWN:", len(layers)-120)
    else:
        print("SVL_MOVE_LINK_NOT_AVAILABLE")
if Move is not None:
    print("ACCOUNT_MOVE_FIELDS:",
          {k: v.type for k, v in Move._fields.items()
           if k in ("stock_move_id", "stock_valuation_layer_ids", "state", "date")})
    linked_entry_ids = set()
    if SVL is not None and "account_move_id" in SVL._fields and "stock_move_id" in SVL._fields:
        linked_entry_ids.update(layers.mapped("account_move_id").ids)
    if "stock_move_id" in Move._fields:
        linked_entry_ids.update(Move.search([("stock_move_id", "in", sorted(moved_ids))]).ids)
    print("DIRECTLY_LINKED_GL_ENTRIES:", len(linked_entry_ids))
    for entry in Move.browse(sorted(linked_entry_ids))[:50]:
        print("  ENTRY:", entry.name, "DATE:", entry.date, "STATE:", entry.state,
              "LINES:", len(entry.line_ids))
        for line in entry.line_ids[:25]:
            print("    GL:", line.account_id.code,
                  "DEBIT:", line.debit, "CREDIT:", line.credit,
                  "PRODUCT:", line.product_id.default_code or "-")
    print("NOTE: zero directly linked GL entries does NOT alone imply error in Odoo 19.")
print("NOTE: no cost correctness or per-location inventory value proven by this diagnostic.")
print("READ_ONLY_BATCH3_FINANCIAL_TRACE_OK")
