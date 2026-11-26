"""Clone-only read-only recipient demand review, not an allocation engine.

SO Paket expansion compares the current BoM with the immutable SO Confirm
snapshot when available. Legacy Paket rows without provenance are flagged.
RO Paket compares the full current expansion to frozen PP1 component rows.
No cross-slot entitlement, package assembly, reservation or DO creation.
"""
from collections import defaultdict
from math import isclose
from .pp1_native_sources import require, whole
from .final_packing_supply import read_final_packing_kitchen_supply


def read_final_packing_demand(batch):
    supply=read_final_packing_kitchen_supply(batch)
    env=batch.env
    pp1=batch._ya_pp1_frozen_facts()
    final=env["ya.sale.mo2.finalization"].sudo().browse(supply["finalization_id"])
    pp2=final._ya_pp2_frozen_facts()
    company=env.company
    domain=[("delivery_date","=",batch.delivery_date),("slot","=",batch.slot)]
    plans=env["ya.production.planning"].sudo().search(domain+[("state","=","published")])
    require(set(plans.ids)==set(pp1["published_plan_ids"]),"Published Planning identity changed")
    routes=defaultdict(list)
    for line in plans.line_ids:
        routes[line.product_id.id].append(line)
    ordinary=env["ya.store.ro"].sudo().search(domain+[("state","=","confirmed")])
    packages=env["ya.package.store.ro"].sudo().search(domain+[("state","=","confirmed")])
    require(set(ordinary.ids)==set(pp1["ordinary_ro_ids"])
            and set(packages.ids)==set(pp1["package_ro_ids"]),"Original RO membership changed")
    recipient_rows=[]
    ro_rows=[]
    pkg_rows={"KITCHEN":[],"PCK":[]}
    so_totals=defaultdict(int)
    so_pkg_unverified=[]
    pkg_category="All / Produk Jadi / Paket"

    def components(product,qty):
        require(product.categ_id.complete_name==pkg_category,"Not a Paket")
        boms=env["mrp.bom"].sudo().search([
            ("active","=",True),("type","=","normal"),
            ("product_tmpl_id","=",product.product_tmpl_id.id),
            "|",("product_id","=",False),("product_id","=",product.id)])
        require(len(boms)==1,"Missing/ambiguous Paket BoM")
        bom=boms[0]
        require(not bom.company_id or bom.company_id==company,"Paket BoM company mismatch")
        require(isclose(bom.product_uom_id._compute_quantity(
            bom.product_qty,product.uom_id,round=False),1,rel_tol=0,abs_tol=1e-9),
            "Paket BoM output must equal one")
        ratios=defaultdict(float)
        for line in bom.bom_line_ids:
            c=line.product_id
            require(c.categ_id.complete_name!=pkg_category,"Nested Paket requires review")
            require(not c.company_id or c.company_id==company,"Component company mismatch")
            ratio=line.product_uom_id._compute_quantity(line.product_qty,c.uom_id,round=False)
            require(ratio>0,"Invalid Paket component ratio")
            ratios[c.id]+=ratio
        require(bool(ratios),"Empty Paket BoM")
        parts=[]
        for pid,ratio in sorted(ratios.items()):
            require(len(routes[pid])<=1,"Ambiguous Paket route")
            kind="KITCHEN" if routes[pid] else "PCK"
            needed=whole(ratio*qty,pid) if kind=="KITCHEN" else ratio*qty
            require(needed>0,"Invalid Paket component quantity")
            parts.append(dict(product_id=pid,source_kind=kind,
                qty_per_package=ratio,qty=needed))
        return bom.id,parts

    for ro in ordinary:
        require(ro.store_warehouse_id.company_id==company and ro.packing_batch_id==batch,
                "Ordinary RO identity mismatch")
        for line in ro.line_ids:
            qty=whole(line.uom_id._compute_quantity(line.qty_requested,line.product_id.uom_id,round=False),line.id)
            if not qty:
                continue
            pid=line.product_id.id
            require(len(routes[pid])==1 and routes[pid][0].planning_id==ro.planning_id,
                    "Ordinary RO route changed")
            src=dict(ro_id=ro.id,line_id=line.id,store_id=ro.store_warehouse_id.id,
                     product_id=pid,qty=qty)
            ro_rows.append(src)
            recipient_rows.append(dict(kind="RO",source_id=ro.id,line_id=line.id,
                recipient_id=ro.store_warehouse_id.id,product_id=pid,qty=qty,
                bom_id=None,components=[dict(product_id=pid,source_kind="KITCHEN",qty=qty)]))
    for ro in packages:
        require(ro.store_warehouse_id.company_id==company,"RO Paket company mismatch")
        for line in ro.line_ids:
            product=line.product_id
            qty=whole(line.uom_id._compute_quantity(line.qty_requested,product.uom_id,round=False),line.id)
            if not qty:
                continue
            bom_id,parts=components(product,qty)
            for part in parts:
                pkg_rows[part["source_kind"]].append(dict(ro_id=ro.id,line_id=line.id,
                    store_id=ro.store_warehouse_id.id,package_id=product.id,
                    bom_id=bom_id,package_qty=qty,product_id=part["product_id"],
                    qty_per_package=part["qty_per_package"],qty=part["qty"]))
            recipient_rows.append(dict(kind="RO_PAKET",source_id=ro.id,line_id=line.id,
                recipient_id=ro.store_warehouse_id.id,product_id=product.id,qty=qty,
                bom_id=bom_id,components=parts))
    def canonical(rows):
        return sorted(rows,key=lambda r:(r["ro_id"],r["line_id"],r["product_id"]))
    require(canonical(ro_rows)==canonical(pp1["ordinary_ro_rows"]),"Original RO demand changed")
    require(canonical(pkg_rows["KITCHEN"])==canonical(pp1["ro_package_kitchen_rows"])
            and canonical(pkg_rows["PCK"])==canonical(pp1["ro_package_pck_rows"]),
            "RO Paket BoM or demand differs from PP1 snapshot")

    orders=env["sale.order"].sudo().search([
        ("ya_is_capacity_so","=",True),("ya_delivery_date","=",batch.delivery_date),
        ("ya_slot","=",batch.slot),("state","in",["sale","done"])])
    ledger=env["ya.sale.capacity.reservation"].sudo().search(domain)
    ledger_rows=[dict(ledger_id=r.id,order_id=r.order_id.id,
        planning_line_id=r.planning_line_id.id,product_id=r.product_id.id,qty=r.qty_required)
        for r in ledger]
    require(sorted(ledger_rows,key=lambda r:r["ledger_id"])==
            sorted(pp2["so_ledger_rows"],key=lambda r:r["ledger_id"]),"PP2 ledger changed")
    require(set(orders.ids)==set(ledger.mapped("order_id").ids),"SO membership changed")
    expected=defaultdict(int)
    for r in ledger:
        require(r.order_id.company_id==company and len(routes[r.product_id.id])==1
                and routes[r.product_id.id][0]==r.planning_line_id,"SO ledger route mismatch")
        expected[(r.order_id.id,r.product_id.id)]+=whole(r.qty_required,r.id)
    for order in orders:
        require(order.company_id==company and not order.picking_ids,
                "SO company mismatch or delivery already exists")
        count=0
        for line in order.order_line:
            if line.display_type or line.is_downpayment or line._is_global_discount():
                continue
            p=line.product_id
            require(bool(p),"SO line has no product")
            qty=whole(line.product_uom_id._compute_quantity(line.product_uom_qty,p.uom_id,round=False),line.id)
            require(qty>0,"SO line quantity not positive")
            count+=1
            if p.categ_id.complete_name==pkg_category:
                bom_id,parts=components(p,qty)
                kind="SO_PAKET"
                if not order.ya_confirmed_demand_snapshot:
                    so_pkg_unverified.append(line.id)
            else:
                require(len(routes[p.id])==1,"SO direct route missing/ambiguous")
                bom_id=None
                parts=[dict(product_id=p.id,source_kind="KITCHEN",qty=qty)]
                kind="SO"
            for part in parts:
                if part["source_kind"]=="KITCHEN":
                    so_totals[(order.id,part["product_id"])]+=part["qty"]
            recipient_rows.append(dict(kind=kind,source_id=order.id,line_id=line.id,
                recipient_id=order.partner_shipping_id.id,product_id=p.id,qty=qty,
                bom_id=bom_id,components=parts))
        require(count>0,"Confirmed SO without commercial demand")
        if order.ya_confirmed_demand_snapshot:
            order._ya_verified_confirmed_demand([r for r in recipient_rows
                if r["kind"] in ("SO","SO_PAKET") and r["source_id"]==order.id])
    require(dict(so_totals)==dict(expected),"SO current expanded demand differs from frozen ledger")
    totals=defaultdict(float)
    for row in recipient_rows:
        for part in row["components"]:
            totals[(row["kind"],part["source_kind"],part["product_id"])]+=part["qty"]
    for row in supply["rows"]:
        pid=row["product_id"]
        require(totals[("SO","KITCHEN",pid)]+totals[("SO_PAKET","KITCHEN",pid)]
                ==row["confirmed_so_qty"]
                and totals[("RO_PAKET","KITCHEN",pid)]==row["original_ro_package_qty"]
                and totals[("RO","KITCHEN",pid)]==row["original_ro_store_qty"],
                "Recipient demand differs from consolidated source")
    pck=env["stock.warehouse"].sudo().browse(supply["pck_id"])
    pck_rows=[]
    for pid in sorted({p for (k,source,p),q in totals.items() if source=="PCK" and q>0}):
        product=env["product.product"].sudo().browse(pid)
        quants=env["stock.quant"].sudo().search([
            ("company_id","=",company.id),("product_id","=",pid),
            ("location_id","=",pck.lot_stock_id.id),("lot_id","=",False),
            ("owner_id","=",False),("package_id","=",False)])
        physical=sum(quants.mapped("quantity"))
        reserved=sum(quants.mapped("reserved_quantity"))
        require(physical>=reserved>=0,"Invalid PCK component stock")
        pck_rows.append(dict(product_id=pid,sku=product.default_code,uom_id=product.uom_id.id,
            physical=physical,reserved=reserved,free=physical-reserved,
            so_paket_required=totals[("SO_PAKET","PCK",pid)],
            ro_paket_required=totals[("RO_PAKET","PCK",pid)],
            tracking=product.tracking))
    return dict(supply=supply,recipient_rows=sorted(recipient_rows,key=lambda r:(r["kind"],r["source_id"],r["line_id"])),
                pck_component_rows=pck_rows,so_paket_confirmation_provenance_missing=sorted(so_pkg_unverified),
                preview_only=True,operational_allocation_allowed=False,
                cross_slot_claims_pending=True,recipient_shortage_policy_pending=True)
