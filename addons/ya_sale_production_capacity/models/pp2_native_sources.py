"""Design B PP2 pre-finalization forecast. No business writes.

Native MO1 planned output is a projection, never PCK inventory.
Cancelled, changed or incompletely finished MO1 requires reconciliation.
Existing MO2 finalization closes this pre-finalization reader.
The caller still needs cutoff, final review and release authorization.
"""
from collections import defaultdict
from odoo.addons.ya_store_ro.models.packing_lock import lock_ro_slot
from .pp1_native_sources import DB, require, whole
from .mo2_owner_so_first_rules import plan_so_first_only

def read_pp2_forecast(batch):
    batch.ensure_one()
    env = batch.env
    require(env.cr.dbname == DB, "Wrong database")
    require(env.user.has_group("ya_store_ro.group_ya_packing_admin"),
            "PP2 requires Packing Admin")
    lock_ro_slot(env.cr, batch.delivery_date, batch.slot)
    env.invalidate_all()
    require(batch.state == "production_ok", "PP1 must be released")
    frozen = batch._ya_pp1_frozen_facts()
    require(frozen["company_id"] == env.company.id, "PP1 company mismatch")
    require(not env["ya.sale.mo2.finalization"].sudo().search_count(
        [("batch_id","=",batch.id)]), "PP2 already finalized")
    require(not (batch.ya_store_delivery_ids or batch.ya_package_assembly_mo_ids
                 or batch.ya_fg_transfer_ids), "Physical Packing already started")
    domain = [("delivery_date","=",batch.delivery_date),("slot","=",batch.slot)]
    for model, key in (("ya.store.ro","ordinary_ro_ids"),
                       ("ya.package.store.ro","package_ro_ids")):
        current = env[model].sudo().search(domain+[("state","=","confirmed")])
        require(set(current.ids)==set(frozen[key]), "Confirmed RO identity changed")
    plans = env["ya.production.planning"].sudo().search(domain+[("state","=","published")])
    routes = defaultdict(list)
    for line in plans.line_ids:
        routes[line.product_id.id].append(line)
    orders = env["sale.order"].sudo().search([
        ("ya_is_capacity_so","=",True),("ya_delivery_date","=",batch.delivery_date),
        ("ya_slot","=",batch.slot),("state","in",["sale","done"])])
    ledger = env["ya.sale.capacity.reservation"].sudo().search(domain)
    require(set(orders.ids)==set(ledger.mapped("order_id").ids), "SO/ledger mismatch")
    rows = {}
    keys = set()
    so = defaultdict(int)
    for r in ledger:
        pid = r.product_id.id
        require(r.order_id in orders and r.order_id.company_id==env.company,
                "SO company or identity mismatch")
        require(len(routes[pid])==1 and routes[pid][0]==r.planning_line_id,
                "SO ledger route mismatch")
        key = (r.order_id.id,r.planning_line_id.id)
        require(key not in keys and r.qty_required>0, "Duplicate/invalid SO ledger")
        keys.add(key)
        rows[r.id] = dict(ledger_id=r.id,order_id=r.order_id.id,
                          planning_line_id=r.planning_line_id.id,product_id=pid,qty=r.qty_required)
        so[pid] += r.qty_required
    early = defaultdict(int)
    for r in frozen["so_ledger_rows"]:
        require(rows.get(r["ledger_id"])==r, "Frozen early SO ledger changed")
        early[r["product_id"]] += r["qty"]
    old = {r["product_id"]:r for r in frozen["sku_forecasts"]}
    require(len(old)==len(frozen["sku_forecasts"]), "Duplicate frozen SKU")
    mo1 = {}
    for line in batch.line_ids:
        pid = line.product_id.id
        require(pid not in mo1 and pid in old, "Unexpected MO1 route")
        mo1[pid] = line
    require(set(mo1)=={pid for pid,r in old.items() if r["forecast_mo1_qty"]>0},
            "MO1 lines differ from frozen PP1")
    result = []
    for pid in sorted(set(old)|set(so)):
        require(len(routes[pid])==1, "Missing/ambiguous Published route")
        line = routes[pid][0]
        product = line.product_id
        bom = line._capacity_bom()
        pt = bom.picking_type_id
        expected = " ".join(("Dapur "+(line.planning_id.workcenter_id.name or "")).casefold().split())
        actual = " ".join((pt.warehouse_id.name or "").casefold().split()) if pt else ""
        require(bom.active and bom.type=="normal" and bom.product_tmpl_id==product.product_tmpl_id
                and (not bom.product_id or bom.product_id==product)
                and (not bom.company_id or bom.company_id==env.company)
                and pt and pt.company_id==env.company and pt.warehouse_id
                and pt.default_location_src_id and pt.default_location_dest_id
                and pt.default_location_dest_id==pt.warehouse_id.lot_stock_id and actual==expected,
                "Invalid kitchen BoM or route")
        output = whole(bom.product_uom_id._compute_quantity(bom.product_qty,product.uom_id,round=False),pid)
        maximum = whole(line.uom_id._compute_quantity(line.max_capacity,product.uom_id,round=False),pid)
        baseline = old.get(pid)
        qty1 = 0
        if baseline:
            route=dict(picking_type_id=pt.id,warehouse_id=pt.warehouse_id.id,
                       source_id=pt.default_location_src_id.id,destination_id=pt.default_location_dest_id.id)
            components=sorted([dict(id=p.id,product_id=p.product_id.id,
                uom_id=p.product_uom_id.id,qty=p.product_qty) for p in bom.bom_line_ids],
                key=lambda p:p["id"])
            require(baseline["planning_line_id"]==line.id and baseline["bom_id"]==bom.id
                    and baseline["bom_output"]==output and baseline["published_max"]==maximum
                    and baseline["kitchen_route"]==route
                    and baseline["kitchen_bom_components"]==components,
                    "Frozen PP1 capacity/BoM/route changed")
            qty1=baseline["forecast_mo1_qty"]
            require(early[pid]==baseline["confirmed_so_qty"], "Frozen early SO qty mismatch")
        row=mo1.get(pid)
        if row:
            mo=row.mo_id
            require(mo and mo.state not in ("draft","cancel")
                    and mo.ya_packing_batch_line_id==row
                    and mo.product_id==product and mo.bom_id==bom
                    and mo.picking_type_id==pt and mo.company_id==env.company
                    and mo.location_src_id==pt.default_location_src_id
                    and mo.location_dest_id==pt.default_location_dest_id
                    and row.planning_id==line.planning_id and row.bom_id==bom
                    and row.uom_id==product.uom_id and row.qty_production==qty1
                    and whole(mo.product_uom_id._compute_quantity(mo.product_qty,product.uom_id,round=False),pid)==qty1,
                    "MO1 invalid or changed; reconcile before PP2")
            if mo.state=="done":
                done=sum(m.product_uom._compute_quantity(m.quantity,product.uom_id,round=False)
                    for m in mo.move_finished_ids if m.state=="done" and m.product_id==product)
                require(abs(done-qty1)<1e-9, "MO1 done output differs; reconcile before PP2")
        calculation=plan_so_first_only(confirmed_so_qty=so[pid],existing_mo1_output=qty1,
            existing_mo2_output=0,published_max=maximum,kitchen_bom_output=output,
            original_ro_package_qty=baseline["original_ro_package_qty"] if baseline else 0,
            original_ro_store_qty=baseline["original_ro_store_qty"] if baseline else 0)
        result.append(dict(product_id=pid,sku=product.default_code,planning_line_id=line.id,
                           early_so_qty=early[pid],late_so_qty=so[pid]-early[pid],
                           mo1_id=row.mo_id.id if row else None,**calculation))
    return dict(batch_id=batch.id,delivery_date=str(batch.delivery_date),slot=batch.slot,
                pp1_digest=batch.ya_pp1_design_b_snapshot["digest"],
                so_ledger_rows=[rows[k] for k in sorted(rows)],sku_forecasts=result,
                cutoff_not_verified=True,forecast_only=True,physical_stock_not_verified=True)
