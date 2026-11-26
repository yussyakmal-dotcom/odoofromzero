"""Read-only inventory evidence for cross-slot PCK reservation design.
Reports native evidence, never assigns slot ownership or subtracts a claim twice.
Legacy allocations are a separate evidence stream, not an extra stock deduction.
"""
from collections import defaultdict
from odoo.tools import float_compare

assert env.cr.dbname=="erp-yussyakmal-mrp-test-RO_SO"
env.cr.rollback()
env.cr.execute("SET TRANSACTION READ ONLY")
env.cr.execute("SHOW transaction_read_only")
assert env.cr.fetchone()[0]=="on"
company=env.company
WH=env["stock.warehouse"].sudo()
PCK=WH.search([("company_id","=",company.id),("code","=","PCK")])
assert len(PCK)==1 and PCK.lot_stock_id.usage=="internal"
root=PCK.lot_stock_id
Batch=env["ya.packing.batch"].sudo()
Move=env["stock.move"].sudo()
Quant=env["stock.quant"].sudo()
Product=env["product.product"].sudo()
batches=Batch.search([],order="delivery_date,slot,id")
print("PCK_SHARED_SCOPE",company.id,root.id,"batches",len(batches))
print("PCK_BATCH_IDENTITIES",[(b.id,str(b.delivery_date),b.slot,b.state,
    bool(b.ya_pp1_design_b_snapshot),len(b.ya_fg_transfer_ids),
    len(b.ya_store_delivery_ids),len(b.ya_package_assembly_mo_ids)) for b in batches])

# Exact root is the scope used by Design B readers. Sub-location movements
# are reported separately; don't treat a root-to-bin move as consumption.
locs=env["stock.location"].sudo().search([("id","child_of",root.id),
    ("usage","=","internal")])
assert root in locs
locset=set(locs.ids)
quants=Quant.search([("company_id","=",company.id),("location_id","in",locs.ids)])
qtot=defaultdict(lambda:defaultdict(float))
for q in quants:
    p=q.product_id
    kind="root_plain" if q.location_id==root and not(q.lot_id or q.owner_id or q.package_id) and p.tracking=="none" else "other"
    qtot[p.id][kind+"_physical"]+=q.quantity
    qtot[p.id][kind+"_reserved"]+=q.reserved_quantity

moves=Move.search([("company_id","=",company.id),("state","!=","cancel"),
    "|",("location_id","in",locs.ids),("location_dest_id","in",locs.ids)])
# Native relational links only: no origin/name parsing.
receipts=defaultdict(float)
consumed=defaultdict(float)
open_rows=[]
unlinked_done=defaultdict(float)
internal_bin=defaultdict(float)
def identity(m):
    p=m.picking_id
    links=[]
    if p.ya_fg_batch_id:
        links.append(("MO1_FG",p.ya_fg_batch_id))
    if p.ya_mo2_fg_release_line_id:
        links.append(("MO2_FG",p.ya_mo2_fg_release_line_id.finalization_id.batch_id))
    if p.ya_store_batch_id:
        links.append(("STORE_"+str(p.ya_store_stage),p.ya_store_batch_id))
    raw=m.raw_material_production_id
    finished=m.production_id
    if raw and raw.ya_package_assembly_batch_id:
        links.append(("PAKET_RAW",raw.ya_package_assembly_batch_id))
    if finished and finished.ya_package_assembly_batch_id:
        links.append(("PAKET_OUTPUT",finished.ya_package_assembly_batch_id))
    if len(links)>1:
        return "AMBIGUOUS_LINK",0,"",""
    if links:
        kind,b=links[0]
        return kind,b.id,str(b.delivery_date),b.slot
    so=m.sale_line_id.order_id
    if so:
        return ("YA_SO" if so.ya_is_capacity_so else "NORMAL_SO"),0,str(so.ya_delivery_date or ""),so.ya_slot or ""
    return "UNLINKED_NATIVE",0,"",""

for m in moves:
    pid=m.product_id.id
    src=m.location_id.id in locset
    dst=m.location_dest_id.id in locset
    ident=identity(m)
    demand=m.product_uom._compute_quantity(m.product_uom_qty,m.product_id.uom_id,round=False)
    actual=m.product_uom._compute_quantity(m.quantity,m.product_id.uom_id,round=False)
    if src and dst:
        if m.state=="done" and (m.location_id==root or m.location_dest_id==root):
            internal_bin[pid]+=actual
        continue
    exact=(m.location_id==root if src else m.location_dest_id==root)
    if m.state=="done":
        k=(pid,*ident,exact)
        if ident[1]:
            (consumed if src else receipts)[k]+=actual
        else:
            unlinked_done[(pid,"OUT" if src else "IN",ident[0],exact)]+=actual
    elif src:
        open_rows.append(dict(move_id=m.id,picking_id=m.picking_id.id,product_id=pid,
            sku=m.product_id.default_code,state=m.state,kind=ident[0],batch_id=ident[1],
            date=ident[2],slot=ident[3],exact_root=exact,demand=demand,
            native_current_move_qty=actual,raw_mo_id=m.raw_material_production_id.id))
# move.quantity is NOT universally a reservation measure (draft/picked etc).
# Quant reserved is reported independently. Do not add open demand and
# reserved quantities as if they were disjoint.
open_by_pid=defaultdict(list)
for row in open_rows:
    open_by_pid[row["product_id"]].append(row)
legacy=defaultdict(float)
for b in batches:
    for a in b.allocation_ids:
        if a.qty_allocated>0:
            legacy[(a.product_id.id,b.id,str(b.delivery_date),b.slot)]+=a.qty_allocated
# Legacy allocation qty is historical model quantity, not a native claim;
# not netted against native movements or used to compute entitlement.
by_pid_receipts=defaultdict(list)
by_pid_out=defaultdict(list)
by_pid_legacy=defaultdict(list)
by_pid_unlinked=defaultdict(list)
for k,v in receipts.items():
    by_pid_receipts[k[0]].append((k[1:],v))
for k,v in consumed.items():
    by_pid_out[k[0]].append((k[1:],v))
for k,v in legacy.items():
    by_pid_legacy[k[0]].append((k[1:],v))
for k,v in unlinked_done.items():
    by_pid_unlinked[k[0]].append((k[1:],v))
pids=set(qtot)|set(by_pid_receipts)|set(by_pid_out)|set(by_pid_legacy)|set(open_by_pid)
review=[]
for pid in sorted(pids):
    p=Product.browse(pid)
    q=qtot[pid]
    physical=q["root_plain_physical"]
    reserved=q["root_plain_reserved"]
    free=physical-reserved
    inc=by_pid_receipts[pid]
    out=by_pid_out[pid]
    opens=open_by_pid[pid]
    leg=by_pid_legacy[pid]
    receipt_slots={x[0][1] for x in inc if x[0][0] in ("MO1_FG","MO2_FG") and x[0][-1]}
    flags=[]
    if len(receipt_slots)>1:
        flags.append("MULTIPLE_BATCH_RECEIPTS")
    if opens:
        flags.append("OPEN_NATIVE_OUTBOUND")
    if any(r["kind"] in ("UNLINKED_NATIVE","NORMAL_SO","AMBIGUOUS_LINK") for r in opens):
        flags.append("OTHER_NATIVE_CLAIMS")
    if leg:
        flags.append("LEGACY_ALLOCATION_EVIDENCE")
    if by_pid_unlinked[pid]:
        flags.append("UNLINKED_HISTORIC_MOVEMENTS")
    if q["other_physical"] or q["other_reserved"] or internal_bin[pid]:
        flags.append("OTHER_QUANT_OR_BIN_SCOPE")
    if float_compare(free,0,precision_rounding=p.uom_id.rounding)<0:
        flags.append("NEGATIVE_FREE")
    row=dict(sku=p.default_code,product_id=pid,uom=p.uom_id.name,
        physical=physical,reserved=reserved,free=free,
        other_physical=q["other_physical"],other_reserved=q["other_reserved"],
        fg_receipt_batch_count=len(receipt_slots),open_move_count=len(opens),
        legacy_allocation_batch_count=len(leg),flags=flags)
    if flags or physical or reserved:
        review.append(row)
    if len(receipt_slots)>1 or opens or (physical and leg):
        print("PCK_REVIEW_SKU",row)
        print("PCK_LINKED_RECEIPTS",p.default_code,sorted(inc))
        print("PCK_LINKED_DONE_OUT",p.default_code,sorted(out))
        print("PCK_OPEN_OUTBOUND",p.default_code,opens)
        print("PCK_LEGACY_ALLOCATION_NOT_STOCK",p.default_code,sorted(leg))
        print("PCK_UNLINKED_DONE",p.default_code,sorted(by_pid_unlinked[pid]))
print("PCK_REVIEW_COUNTS",dict(sku_count=len(pids),review_sku_count=len(review),
    multi_batch_receipt_sku_count=sum(r["fg_receipt_batch_count"]>1 for r in review),
    open_outbound_move_count=len(open_rows),
    legacy_allocation_sku_count=len(by_pid_legacy),
    other_scope_sku_count=sum("OTHER_QUANT_OR_BIN_SCOPE" in r["flags"] for r in review),
    negative_free_sku_count=sum("NEGATIVE_FREE" in r["flags"] for r in review)))
print("PCK_NO_SLOT_ENTITLEMENT_CALCULATED_NO_RESERVATION_WRITE")
print("FASE2_PCK_CROSS_SLOT_CLAIMS_READONLY_OK")
env.cr.rollback()
