"""READ ONLY. Reconcile exact native quant reservation totals to open move lines.

Odoo 19 move-line quantity on an open reservable move is a candidate for
reservation attribution, NOT universally a reservation. Compare by exact
company/product/location/lot/owner/package key, including zero quant rows
and unexpected lines. Report draft, picked, non-root and ambiguous links
separately. No slot entitlement or authorization to consume any stock.
"""
from collections import defaultdict
from odoo.tools import float_compare

assert env.cr.dbname=="erp-yussyakmal-mrp-test-RO_SO"
env.cr.rollback()
env.cr.execute("SET TRANSACTION READ ONLY")
env.cr.execute("SHOW transaction_read_only")
assert env.cr.fetchone()[0]=="on"
company=env.company
pck=env["stock.warehouse"].sudo().search([
    ("company_id","=",company.id),("code","=","PCK")])
assert len(pck)==1 and pck.lot_stock_id.usage=="internal"
root=pck.lot_stock_id
locations=env["stock.location"].sudo().search([
    ("id","child_of",root.id),("usage","=","internal")])
Quant=env["stock.quant"].sudo()
ML=env["stock.move.line"].sudo()
Move=env["stock.move"].sudo()
Product=env["product.product"].sudo()
assert all(f in ML._fields for f in ("quantity","product_uom_id","move_id",
    "location_id","lot_id","owner_id","package_id","company_id","picked"))
assert "picked" in Move._fields
def qkey(r):
    return (r.company_id.id,r.product_id.id,r.location_id.id,
            r.lot_id.id or 0,r.owner_id.id or 0,r.package_id.id or 0)
def qty_base(ml):
    return ml.product_uom_id._compute_quantity(ml.quantity,ml.product_id.uom_id,round=False)
def identity(m):
    p=m.picking_id
    links=[]
    if p.ya_fg_batch_id:
        links.append(("MO1_FG",p.ya_fg_batch_id.id))
    if p.ya_mo2_fg_release_line_id:
        links.append(("MO2_FG",p.ya_mo2_fg_release_line_id.finalization_id.batch_id.id))
    if p.ya_store_batch_id:
        links.append(("STORE_"+str(p.ya_store_stage),p.ya_store_batch_id.id))
    if m.raw_material_production_id.ya_package_assembly_batch_id:
        links.append(("PAKET_RAW",m.raw_material_production_id.ya_package_assembly_batch_id.id))
    if m.production_id.ya_package_assembly_batch_id:
        links.append(("PAKET_OUTPUT",m.production_id.ya_package_assembly_batch_id.id))
    if len(links)>1:
        return "AMBIGUOUS_LINK",0
    if links:
        return links[0]
    so=m.sale_line_id.order_id
    return ("YA_SO" if so.ya_is_capacity_so else "NORMAL_SO",0) if so else ("UNLINKED_NATIVE",0)
physical=defaultdict(float)
reserved=defaultdict(float)
candidate=defaultdict(float)
details=defaultdict(list)
exceptions=[]
qs=Quant.search([("company_id","=",company.id),("location_id","in",locations.ids)])
for q in qs:
    k=qkey(q)
    physical[k]+=q.quantity
    reserved[k]+=q.reserved_quantity
lines=ML.search([("company_id","=",company.id),("location_id","in",locations.ids),
                 ("move_id.state","not in",["done","cancel"])])
open_states={"waiting","confirmed","partially_available","assigned"}
for ml in lines:
    m=ml.move_id
    k=qkey(ml)
    value=qty_base(ml)
    if not value:
        continue
    kind,bid=identity(m)
    flags=[]
    if m.state not in open_states:
        flags.append("NON_RESERVABLE_OR_DRAFT_STATE")
    if ml.picked or m.picked:
        flags.append("PICKED_REVIEW")
    if (ml.location_id!=root or ml.lot_id or ml.owner_id or ml.package_id
            or ml.product_id.tracking!="none"):
        flags.append("OTHER_QUANT_SCOPE")
    if (m.company_id!=company or m.product_id!=ml.product_id or value<0
            or m.location_id!=root or ml.location_dest_id!=m.location_dest_id):
        flags.append("MOVE_LINE_ROUTE_OR_QTY_REVIEW")
    if ml.location_dest_id in locations:
        flags.append("INTERNAL_BIN_MOVE")
    if not bid or kind=="AMBIGUOUS_LINK":
        flags.append("UNATTRIBUTED_BATCH")
    row=dict(move_line_id=ml.id,move_id=m.id,picking_id=m.picking_id.id,
             state=m.state,picked=bool(ml.picked or m.picked),
             kind=kind,batch_id=bid,quantity_base=value,flags=flags)
    details[k].append(row)
    if m.state in open_states and value>=0:
        candidate[k]+=value
    if flags:
        exceptions.append((k,row))
mismatches=[]
scope_review=[]
matched_keys=0
attributed=defaultdict(float)
for k in sorted(set(physical)|set(reserved)|set(candidate)|set(details)):
    p=Product.browse(k[1])
    r,c=reserved[k],candidate[k]
    delta=r-c
    matches=float_compare(r,c,precision_rounding=p.uom_id.rounding)==0
    rows=details[k]
    if not matches or r<0 or r>physical[k]+1e-7:
        mismatches.append(dict(key=k,sku=p.default_code,physical=physical[k],
            quant_reserved=r,open_line_candidate=c,delta=delta,lines=rows))
    else:
        matched_keys+=1
    # Only exact root untracked plain and clean native links; even then
    # this is numerical reconciliation, not proof of historical ownership.
    clean=matches and r>=0 and r<=physical[k]+1e-7 and all(not x["flags"] for x in rows)
    if r or c or rows:
        print("PCK_NATIVE_RESERVATION_KEY",dict(key=k,sku=p.default_code,
            physical=physical[k],quant_reserved=r,open_line_candidate=c,
            matches=matches,clean_attribution_candidate=clean,lines=rows))
        if clean:
            for x in rows:
                attributed[(p.id,x["batch_id"])]+=x["quantity_base"]
        else:
            scope_review.append((k,p.default_code))
# Include native outstanding demand with no move lines (e.g. stockout).
moves=Move.search([("company_id","=",company.id),("location_id","in",locations.ids),
                   ("state","not in",["done","cancel"])])
by_move=defaultdict(float)
for k,rows in details.items():
    for row in rows:
        if row["state"] in open_states:
            by_move[row["move_id"]]+=row["quantity_base"]
for m in moves:
    demand=m.product_uom._compute_quantity(m.product_uom_qty,m.product_id.uom_id,round=False)
    current=by_move[m.id]
    if float_compare(demand,current,precision_rounding=m.product_id.uom_id.rounding)!=0:
        print("PCK_NATIVE_OPEN_DEMAND_REVIEW",dict(move_id=m.id,sku=m.product_id.default_code,
            state=m.state,identity=identity(m),demand=demand,open_line_candidate=current))
print("PCK_RECONCILED_BATCH_RESERVATION_CANDIDATES",[
    (Product.browse(pid).default_code,bid,v) for (pid,bid),v in sorted(attributed.items())])
print("PCK_NATIVE_RESERVATION_MISMATCHES",mismatches)
print("PCK_NATIVE_RESERVATION_SCOPE_REVIEW",scope_review)
print("PCK_NATIVE_RESERVATION_SUMMARY",dict(
    quant_count=len(qs),open_line_count=len(lines),matched_key_count=matched_keys,
    mismatch_key_count=len(mismatches),scope_review_key_count=len(scope_review),
    exception_line_count=len(exceptions),open_move_count=len(moves)))
print("PCK_NO_ENTITLEMENT_NO_RESERVATION_WRITE")
print("FASE2_PCK_NATIVE_RESERVATION_RECONCILIATION_READONLY_OK")
env.cr.rollback()
