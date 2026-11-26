"""Read-only exact-root native PCK claim review, not operational entitlement.

Conservative preview only. No decision to release historic surplus, no
unissued-demand policy, no write/reservation/DO, no guarantee of concurrency.
Unsupported routes, tracked/packed/owned stock and attribution fail closed.
"""
from collections import defaultdict
from decimal import Decimal
from .pp1_native_sources import DB, require
from .pck_claim_protection_rules import review_claims


def native_pck_claim_review(batch,demand):
    batch.ensure_one()
    env=batch.env
    require(env.cr.dbname==DB,"Wrong database")
    require(env.user.has_group("ya_store_ro.group_ya_packing_admin"),"Packing Admin required")
    # The demand reader already holds the date-slot mutex. This helper
    # does not serialize native inventory operations across slots.
    supply=demand["supply"]
    require(supply["batch_id"]==batch.id and supply["delivery_date"]==str(batch.delivery_date)
            and supply["slot"]==batch.slot,"PCK review identity mismatch")
    pck=env["stock.warehouse"].sudo().browse(supply["pck_id"])
    require(pck.company_id==env.company and pck.code=="PCK","PCK company mismatch")
    root=pck.lot_stock_id
    locs=env["stock.location"].sudo().search([
        ("id","child_of",root.id),("usage","=","internal")])
    locset=set(locs.ids)
    kitchen={r["product_id"]:r for r in supply["rows"]}
    direct={r["product_id"]:r for r in demand["pck_component_rows"]}
    require(not set(kitchen)&set(direct),"Ambiguous PCK supply scope")
    ids=sorted(set(kitchen)|set(direct))
    def amount(uom,n,product):
        value=Decimal(str(uom._compute_quantity(n,product.uom_id,round=False)))
        require(value.is_finite() and value>=0,"Invalid PCK move quantity")
        return value
    def plain(line):
        return not(line.lot_id or line.owner_id or line.package_id)
    def claim():
        return dict(received=Decimal(0),done_out=Decimal(0),
                    open_demand=Decimal(0),reserved=Decimal(0))
    claims=defaultdict(lambda:defaultdict(claim))
    physical=defaultdict(Decimal)
    reserved=defaultdict(Decimal)
    Move=env["stock.move"].sudo()
    Quant=env["stock.quant"].sudo()
    products=env["product.product"].sudo().browse(ids)
    require(all(p.tracking=="none" and p.is_storable for p in products),"Unsupported PCK product")
    for q in Quant.search([("company_id","=",env.company.id),
            ("location_id","in",locs.ids),("product_id","in",ids)]):
        require(q.location_id==root and plain(q) or (not q.quantity and not q.reserved_quantity),
                "Non-root or nonplain PCK quant requires review")
        if q.location_id==root and plain(q):
            require(q.quantity>=0 and 0<=q.reserved_quantity<=q.quantity,
                    "Invalid native PCK quant")
            physical[q.product_id.id]+=Decimal(str(q.quantity))
            reserved[q.product_id.id]+=Decimal(str(q.reserved_quantity))

    def identity(m):
        p=m.picking_id
        linked=[]
        if p.ya_fg_batch_id:
            linked.append(("FG",p.ya_fg_batch_id.id))
        if p.ya_mo2_fg_release_line_id:
            linked.append(("FG",p.ya_mo2_fg_release_line_id.finalization_id.batch_id.id))
        if p.ya_store_batch_id:
            linked.append(("STORE_"+str(p.ya_store_stage),p.ya_store_batch_id.id))
        if m.raw_material_production_id.ya_package_assembly_batch_id:
            linked.append(("PAKET_RAW",m.raw_material_production_id.ya_package_assembly_batch_id.id))
        if m.production_id.ya_package_assembly_batch_id:
            linked.append(("PAKET_OUTPUT",m.production_id.ya_package_assembly_batch_id.id))
        require(len(linked)<=1,"Ambiguous native PCK batch linkage")
        return linked[0] if linked else ("UNLINKED",0)

    moves=Move.search([("company_id","=",env.company.id),("product_id","in",ids),
        ("state","!=","cancel"),"|",("location_id","in",locs.ids),
        ("location_dest_id","in",locs.ids)])
    states={"waiting","confirmed","partially_available","assigned"}
    covered_lines=set()
    for m in moves:
        pid=m.product_id.id
        src=m.location_id.id in locset
        dst=m.location_dest_id.id in locset
        require(not(src and dst),"PCK internal bin move requires review")
        require((m.location_id if src else m.location_dest_id)==root,
                "PCK move not at exact root")
        kind,bid=identity(m)
        c=claims[pid][bid]
        if m.state=="done":
            actual=amount(m.product_uom,m.quantity,m.product_id)
            for line in m.move_line_ids:
                require(plain(line) and line.location_id==m.location_id
                        and line.location_dest_id==m.location_dest_id,
                        "Historic nonplain PCK movement requires review")
            if dst and kind in ("FG","PAKET_OUTPUT"):
                c["received"]+=actual
            elif src:
                # Unknown completed withdrawals are not attributed to
                # another batch's receipts; preserve conservative cap.
                c["done_out"]+=actual
            continue
        if not src:
            continue
        require(m.state in states or m.state=="draft","Unsupported native PCK outbound state")
        c["open_demand"]+=amount(m.product_uom,m.product_uom_qty,m.product_id)
        held=Decimal(0)
        for line in m.move_line_ids:
            n=amount(line.product_uom_id,line.quantity,m.product_id)
            if not n:
                continue
            require(m.state in states and not (m.picked or line.picked)
                    and line.company_id==env.company and line.product_id==m.product_id
                    and plain(line) and line.location_id==root
                    and line.location_dest_id==m.location_dest_id,
                    "Native PCK reservation scope requires review")
            covered_lines.add(line.id)
            held+=n
        require(held<=amount(m.product_uom,m.product_uom_qty,m.product_id),
                "Native PCK reservation exceeds move demand")
        c["reserved"]+=held
    # Check move lines independently, not just those reached through the
    # selected move headers. A mismatching location cannot silently vanish.
    lines=env["stock.move.line"].sudo().search([
        ("company_id","=",env.company.id),("product_id","in",ids),
        ("location_id","in",locs.ids),("move_id.state","not in",["done","cancel"])])
    require({l.id for l in lines if l.quantity}==covered_lines,
            "Native PCK open move-line set mismatch")
    out=[]
    for pid in ids:
        rows=[dict(batch_id=bid,**c) for bid,c in sorted(claims[pid].items())]
        result=review_claims(physical[pid],reserved[pid],rows,batch.id)
        own=claims[pid][batch.id]
        require(not (own["open_demand"] or own["reserved"] or own["done_out"]),
                "Current batch already has PCK outbound claims; reconcile before review")
        if pid in kitchen:
            src=kitchen[pid]
            require(own["received"]==Decimal(str(src["mo1_mo2_received_qty"])),
                    "Current receipt provenance mismatch")
            require(physical[pid]==Decimal(str(src["pck_physical"])) and
                    reserved[pid]==Decimal(str(src["pck_reserved"])),
                    "PCK kitchen source changed")
            cap=min(result["conservative_preview_cap"],
                    Decimal(str(src["slot_supply_upper_bound"])))
            source="KITCHEN"
        else:
            src=direct[pid]
            require(physical[pid]==Decimal(str(src["physical"])) and
                    reserved[pid]==Decimal(str(src["reserved"])),
                    "PCK component source changed")
            # Shared components may have no batch receipt provenance.
            # This is an upper bound only; unissued claims remain unresolved.
            cap=result["shared_free_after_other_protection"]
            source="PCK"
        out.append(dict(product_id=pid,source_kind=source,
            physical=str(physical[pid]),reserved=str(reserved[pid]),
            global_free=str(result["global_free"]),
            other_protection=str(result["other_protection"]),
            preview_cap=str(cap),
            other_claim_shortfall=str(result["other_claim_shortfall"]),
            claims=[dict(batch_id=bid,**{k:str(v) for k,v in c.items()})
                    for bid,c in sorted(result["claims"].items())]))
    return dict(batch_id=batch.id,rows=out,preview_only=True,
                operational_allocation_allowed=False,
                unissued_claims_pending=True,shared_stock_lock_pending=True,
                surplus_policy_pending=True)


def read_claim_protected_packing_demand(batch):
    """New review path, not replacing existing operator or allocation core."""
    from .final_packing_demand import read_final_packing_demand
    demand=read_final_packing_demand(batch)
    review=native_pck_claim_review(batch,demand)
    caps={r["product_id"]:Decimal(r["preview_cap"]) for r in review["rows"]}
    for row in demand["supply"]["rows"]:
        cap=caps[row["product_id"]]
        require(cap==cap.to_integral_value(),"Fractional finished-goods preview cap")
        row["claim_preview_cap"]=int(cap)
    for row in demand["pck_component_rows"]:
        row["claim_preview_cap"]=float(caps[row["product_id"]])
    demand["pck_claim_review"]=review
    return demand
