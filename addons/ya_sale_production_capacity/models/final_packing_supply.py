"""Read-only Design B final Packing kitchen supply gate, clone only.

Receipts are bounded by the frozen batch identity and native DONE output.
Global free PCK stock is not automatically entitled to this slot.
No claim of complete package availability or recipient allocation.
"""
from collections import defaultdict

from odoo.addons.ya_store_ro.models.packing_lock import lock_ro_slot
from .pp1_native_sources import DB, require, whole


def read_final_packing_kitchen_supply(batch):
    batch.ensure_one()
    env = batch.env
    require(env.cr.dbname == DB, "Wrong database")
    require(env.user.has_group("ya_store_ro.group_ya_packing_admin"),
            "Packing Admin required")
    lock_ro_slot(env.cr,batch.delivery_date,batch.slot)
    env.invalidate_all()
    require(batch.state=="production_ok", "PP1 not released")
    pp1=batch._ya_pp1_frozen_facts()
    require(pp1["company_id"]==env.company.id,"Company mismatch")
    finals=env["ya.sale.mo2.finalization"].sudo().search([("batch_id","=",batch.id)])
    require(len(finals)==1,"PP2 must be finalized")
    final=finals[0]
    pp2=final._ya_pp2_frozen_facts()
    require(not (batch.ya_store_delivery_ids or batch.ya_package_assembly_mo_ids
                 or batch.allocation_ids),"Final Packing already started")
    pck=env["stock.warehouse"].sudo().search([
        ("code","=","PCK"),("company_id","=",env.company.id)])
    require(len(pck)==1 and pck.lot_stock_id.usage=="internal","Invalid PCK")
    dest=pck.lot_stock_id
    forecasts={r["product_id"]:r for r in pp2["sku_forecasts"]}
    require(len(forecasts)==len(pp2["sku_forecasts"]),"Duplicate PP2 SKU")
    excluded=set(x.strip() for x in (env["ir.config_parameter"].sudo().get_param(
        "ya_finished_packing_transfer.exclude_sku_codes","11076") or "").split(",") if x.strip())
    receipts=defaultdict(int)
    proofs=[]
    def output(mo,fact,qty):
        product=mo.product_id
        route=fact["kitchen_route"]
        require(product.id==fact["product_id"] and mo.state=="done"
                and mo.company_id==env.company and mo.bom_id.id==fact["bom_id"]
                and mo.picking_type_id.id==route["picking_type_id"]
                and mo.picking_type_id.warehouse_id.id==route["warehouse_id"]
                and mo.location_dest_id.id==route["destination_id"]
                and mo.location_src_id.id==route["source_id"],"Native MO not DONE or route mismatch")
        require(product.default_code not in excluded and product.tracking=="none",
                "WIP/tracked product needs separate Packing review")
        require(whole(mo.product_uom_id._compute_quantity(mo.product_qty,product.uom_id,round=False),mo.id)==qty,
                "Native MO planned quantity changed")
        moves=mo.move_finished_ids.filtered(lambda m:m.product_id==product)
        require(bool(moves) and all(m.state=="done" and m.location_dest_id==mo.location_dest_id
                for m in moves),"Native MO finished moves incomplete")
        actual=whole(sum(m.product_uom._compute_quantity(m.quantity,product.uom_id,round=False)
                    for m in moves),mo.id)
        require(actual==qty,"Native MO output discrepancy; reconcile")
        return actual
    def picking_qty(picking,wh):
        require(picking.state=="done" and picking.company_id==env.company
                and picking.picking_type_id==wh.int_type_id
                and picking.location_id==wh.lot_stock_id
                and picking.location_dest_id==dest,"Native PCK receipt not DONE or route mismatch")
        out=defaultdict(int)
        for m in picking.move_ids:
            require(m.state=="done" and m.location_id==wh.lot_stock_id
                    and m.location_dest_id==dest,"Native receipt move incomplete")
            q=whole(m.product_uom._compute_quantity(m.quantity,m.product_id.uom_id,round=False),m.id)
            require(q>0,"Nonpositive PCK receipt")
            out[m.product_id.id]+=q
        return dict(out)
    # Canonical MO1 picking is per batch/kitchen, not per MO.
    groups=defaultdict(dict)
    for row in batch.line_ids:
        pid=row.product_id.id
        fact=forecasts[pid]
        mo=row.mo_id
        require(mo.ya_packing_batch_line_id==row and fact["mo1_id"]==mo.id,
                "MO1 linkage mismatch")
        qty=output(mo,fact,fact["preexisting_mo1_qty"])
        wh=mo.picking_type_id.warehouse_id
        require(pid not in groups[wh.id],"Duplicate MO1 product")
        groups[wh.id][pid]=qty
    require(set(batch.line_ids.mapped("product_id").ids)==
            {pid for pid,f in forecasts.items() if f["preexisting_mo1_qty"]>0},
            "MO1 membership mismatch")
    require(len(batch.ya_fg_transfer_ids)==len(groups),"MO1 kitchen PCK receipts incomplete")
    seen=set()
    for picking in batch.ya_fg_transfer_ids:
        wh=picking.ya_fg_kitchen_id
        require(wh.id in groups and wh.id not in seen and not picking.ya_mo2_fg_release_line_id,
                "MO1 receipt linkage mismatch")
        seen.add(wh.id)
        actual=picking_qty(picking,wh)
        require(actual==groups[wh.id],"MO1 receipt differs from DONE output")
        for pid,qty in actual.items():
            receipts[pid]+=qty
            proofs.append(dict(wave="MO1",picking_id=picking.id,product_id=pid,qty=qty))
    for line in final.line_ids:
        pid=line.product_id.id
        fact=forecasts[pid]
        qty=output(line.mo_id,fact,line.qty_mo2)
        picking=line.ya_mo2_fg_picking_ids
        require(len(picking)==1 and not picking.ya_fg_batch_id
                and picking.ya_mo2_fg_release_line_id==line,"MO2 PCK receipt missing")
        require(picking_qty(picking,line.mo_id.picking_type_id.warehouse_id)=={pid:qty},
                "MO2 receipt differs from DONE output")
        receipts[pid]+=qty
        proofs.append(dict(wave="MO2",picking_id=picking.id,product_id=pid,qty=qty))
    rows=[]
    for pid,fact in sorted(forecasts.items()):
        product=env["product.product"].sudo().browse(pid)
        quants=env["stock.quant"].sudo().search([
            ("company_id","=",env.company.id),("location_id","=",dest.id),
            ("product_id","=",pid),("lot_id","=",False),
            ("owner_id","=",False),("package_id","=",False)])
        physical=whole(sum(quants.mapped("quantity")),pid)
        reserved=whole(sum(quants.mapped("reserved_quantity")),pid)
        require(physical>=reserved,"Invalid PCK physical/reserved")
        free=physical-reserved
        # This is only an upper bound. A different slot may also have
        # prior claims on fungible unreserved units; no reservation here.
        rows.append(dict(product_id=pid,sku=product.default_code,
                         mo1_mo2_received_qty=receipts[pid],pck_physical=physical,
                         pck_reserved=reserved,pck_free=free,
                         slot_supply_upper_bound=min(receipts[pid],free),
                         confirmed_so_qty=fact["confirmed_so_qty"],
                         original_ro_package_qty=fact["original_ro_package_qty"],
                         original_ro_store_qty=fact["original_ro_store_qty"]))
    return dict(batch_id=batch.id,finalization_id=final.id,
                delivery_date=str(batch.delivery_date),slot=batch.slot,pck_id=pck.id,
                rows=rows,receipt_proofs=sorted(proofs,key=lambda r:(r["wave"],r["picking_id"],r["product_id"])),
                preview_only=True,cross_slot_claims_not_reconciled=True,
                package_pck_components_not_verified=True,no_allocation_or_reservation=True)
