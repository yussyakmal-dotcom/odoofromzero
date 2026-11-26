"""Read-only CDC issued-demand diagnostic for Design B, clone only.

Owner buffer policy: full issued transfer demand remains an obligation.
This is NOT a new procurement workflow or a transfer quantity calculator.
Count native outbound moves once; never add linked MO raw moves again.
Physical stock includes reserved stock: do not subtract reservations twice.
Open direct supplier receipts are shown separately, not treated as on-hand.
Unissued MO demand, overdue/uncertain supply, location/lot eligibility,
reservation reconciliation and partially cancelled obligations need review.
"""
from collections import defaultdict
from .pp1_native_sources import DB, require

OPEN_STATES = ("waiting", "confirmed", "partially_available", "assigned")

def read_cdc_commitments(env, company, product_ids):
    require(env.cr.dbname == DB, "Wrong database")
    require(env.user.has_group("stock.group_stock_manager"), "Inventory Administrator required")
    company.ensure_one()
    require(company == env.company, "CDC company mismatch")
    product_ids = sorted(set(product_ids))
    require(bool(product_ids), "Choose material SKUs")
    Warehouse = env["stock.warehouse"].sudo()
    cdc = Warehouse.search([("code","=","CDC"),("company_id","=",company.id)])
    require(len(cdc)==1 and cdc.lot_stock_id.usage=="internal", "Invalid CDC warehouse")
    products = env["product.product"].sudo().browse(product_ids).exists()
    require(set(products.ids)==set(product_ids), "Missing material SKU")
    require(all(not p.company_id or p.company_id==company for p in products), "Material company mismatch")
    locations = env["stock.location"].sudo().search([
        ("id","child_of",cdc.lot_stock_id.id),("usage","=","internal")])
    loc_ids = locations.ids
    Move = env["stock.move"].sudo()
    Quant = env["stock.quant"].sudo()
    common = [("company_id","=",company.id),("product_id","in",product_ids)]
    physical = defaultdict(float)
    reserved = defaultdict(float)
    for q in Quant.search(common+[("location_id","in",loc_ids)]):
        physical[q.product_id.id] += q.quantity
        reserved[q.product_id.id] += q.reserved_quantity
    outbound = defaultdict(float)
    incoming = defaultdict(float)
    outbound_rows = []
    incoming_rows = []
    draft_review = []
    for move in Move.search(common+[("location_id","in",loc_ids),
                                    ("location_dest_id","not in",loc_ids),
                                    ("state","not in",["done","cancel"])]):
        picking = move.picking_id
        # Generated YA draft documents are issued obligations, but unrelated
        # draft proposals are not confirmed commitments.
        ya_issued = bool(picking and (picking.ya_mr_batch_id
                        or picking.ya_mo2_material_release_line_id))
        qty = move.product_uom._compute_quantity(
            move.product_uom_qty, move.product_id.uom_id, round=False)
        require(qty>=0, "Negative CDC outgoing demand")
        if not qty:
            continue
        if move.state not in OPEN_STATES and not (move.state=="draft" and ya_issued):
            draft_review.append(move.id)
            continue
        row = dict(move_id=move.id,picking_id=picking.id or None,
                   product_id=move.product_id.id,qty=qty,state=move.state,
                   kind="MR2" if picking.ya_mo2_material_release_line_id
                        else "MR1" if picking.ya_mr_batch_id else "OTHER")
        outbound_rows.append(row)
        outbound[move.product_id.id] += qty
    # Only open direct vendor receipt legs into the CDC subtree. Other
    # incoming routes are not promised supply by this conservative diagnostic.
    for move in Move.search(common+[("location_id.usage","=","supplier"),
                                    ("location_dest_id","in",loc_ids),
                                    ("state","in",list(OPEN_STATES))]):
        if not move.picking_id or move.picking_id.picking_type_id.code!="incoming":
            continue
        qty = move.product_uom._compute_quantity(
            move.product_uom_qty,move.product_id.uom_id,round=False)
        require(qty>=0,"Negative CDC receipt demand")
        if qty:
            incoming[move.product_id.id] += qty
            incoming_rows.append(dict(move_id=move.id,picking_id=move.picking_id.id,
                product_id=move.product_id.id,qty=qty,scheduled_at=str(move.date)))
    rows = []
    for p in products:
        pid = p.id
        stock = physical[pid]
        held = reserved[pid]
        due = outbound[pid]
        receipts = incoming[pid]
        require(held>=0, "Negative CDC reservation")
        rows.append(dict(product_id=pid,sku=p.default_code,uom_id=p.uom_id.id,
            physical_qty=stock,reserved_qty=held,free_qty=stock-held,
            issued_outbound_demand=due,
            shortage_against_physical=max(due-stock,0.0),
            open_direct_supplier_receipt_qty=receipts,
            projected_gap_if_all_receipts_arrive=max(due-stock-receipts,0.0),
            reservation_reconciliation_needed=bool(held),
            physical_negative=stock<0))
    return dict(cdc_id=cdc.id,company_id=company.id,rows=rows,
                outbound_rows=sorted(outbound_rows,key=lambda r:r["move_id"]),
                incoming_rows=sorted(incoming_rows,key=lambda r:r["move_id"]),
                excluded_draft_review_ids=sorted(draft_review),
                issued_demand_only=True, unissued_mo_demand_not_included=True,
                no_due_date_or_lot_eligibility_guarantee=True,
                diagnostic_only_no_purchase_or_stock_writes=True)
