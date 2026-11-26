"""Rollback QA adapter only; not an operational final allocation release.

Native Fase1 store dispatch identifiers and routes are preserved. Native
customer delivery uses the original sale lines, not fictitious store RO.
Input is the previously validated candidate in the same QA transaction.
A persistent approved allocation and authorized operator integration are
required before exposing any operational entry point.
"""
from collections import defaultdict
from odoo.addons.ya_store_ro.models.packing_lock import lock_ro_slot
from .pp1_native_sources import DB, require


def _qa_generate_native_deliveries(batch,demand,validated):
    batch.ensure_one()
    env=batch.env
    require(env.cr.dbname==DB and env.user.has_group("ya_store_ro.group_ya_packing_admin"),
            "Clone Packing Admin required")
    with env.cr.savepoint():
        lock_ro_slot(env.cr,batch.delivery_date,batch.slot)
        require(demand["supply"]["batch_id"]==batch.id and batch.state=="production_ok"
                and validated["preview_only"] and not validated["operational_allocation_allowed"],
                "Invalid QA allocation input")
        require(not batch.ya_store_delivery_ids,"Store DO already exists")
        pck=env["stock.warehouse"].sudo().browse(demand["supply"]["pck_id"])
        root=pck.lot_stock_id
        require(pck.code=="PCK" and pck.company_id==env.company and root.usage=="internal"
                and pck.out_type_id.code=="outgoing","Invalid native PCK dispatch route")
        transit=env["stock.location"].sudo().search([("usage","=","transit"),
            ("name","=","Inter-warehouse transit"),("company_id","in",[False,env.company.id])])
        require(len(transit)==1,"Invalid Fase1 transit route")
        stores=defaultdict(lambda:defaultdict(int))
        orders=defaultdict(list)
        package_qty=defaultdict(int)
        for row in validated["rows"]:
            qty=row["qty_allocated"]
            if not qty:
                continue
            kind=row["kind"]
            pid=row["product_id"]
            if kind in ("SO_PAKET","RO_PAKET"):
                package_qty[pid]+=qty
            if kind in ("SO","SO_PAKET"):
                require(qty==row["qty_requested"],"Confirmed SO must be fulfilled")
                orders[row["source_id"]].append(row)
            else:
                require(kind in ("RO","RO_PAKET"),"Unknown allocation class")
                stores[row["recipient_id"]][pid]+=qty
        mos=batch.ya_package_assembly_mo_ids
        require(set(mos.mapped("product_id").ids)==set(package_qty),"Paket assembly membership mismatch")
        for mo in mos:
            require(mo.state=="done" and mo.location_dest_id==root,"Paket assembly not DONE")
            actual=sum(m.product_uom._compute_quantity(m.quantity,mo.product_id.uom_id,round=False)
                       for m in mo.move_finished_ids if m.state=="done"
                       and m.product_id==mo.product_id and m.location_dest_id==root)
            require(abs(actual-package_qty[mo.product_id.id])<1e-7,"Paket actual output mismatch")
        Picking=env["stock.picking"]
        Move=env["stock.move"]
        Product=env["product.product"]
        customers=Picking
        dispatches=Picking
        def create_picking(dest,origin,extra,lines):
            picking=Picking.create(dict(picking_type_id=pck.out_type_id.id,
                company_id=env.company.id,location_id=root.id,location_dest_id=dest.id,
                origin=origin,**extra))
            vals=[]
            for pid,qty,sale_line in lines:
                product=Product.browse(pid)
                require(product.tracking=="none" and product.is_storable,"Unsupported dispatch product")
                v=dict(picking_id=picking.id,company_id=env.company.id,
                    product_id=pid,product_uom=product.uom_id.id,product_uom_qty=qty,
                    location_id=root.id,location_dest_id=dest.id)
                if sale_line:
                    v["sale_line_id"]=sale_line
                vals.append(v)
            Move.create(vals)
            picking.action_confirm()
            picking.action_assign()
            require(picking.state=="assigned","Native delivery not fully reserved")
            for m in picking.move_ids:
                require(m.state=="assigned" and abs(m.quantity-m.product_uom_qty)<1e-7
                        and all(l.location_id==root and not(l.lot_id or l.owner_id or l.package_id)
                                for l in m.move_line_ids),"Native dispatch reservation incomplete")
            return picking
        # SO first; standard Odoo quant reservations, no alternative ledger.
        for oid,rows in sorted(orders.items()):
            order=env["sale.order"].sudo().browse(oid)
            require(order.state in ("sale","done") and order.ya_is_capacity_so
                    and order.company_id==env.company and order.ya_delivery_date==batch.delivery_date
                    and order.ya_slot==batch.slot and not order.picking_ids,"SO delivery already exists or source mismatch")
            partner=order.partner_shipping_id
            dest=partner.with_company(env.company).property_stock_customer
            require(dest.usage=="customer","Invalid customer stock location")
            lines=[]
            for row in rows:
                line=order.order_line.filtered(lambda l:l.id==row["line_id"])
                require(len(line)==1 and line.product_id.id==row["product_id"]
                        and partner.id==row["recipient_id"],"Native SO line identity mismatch")
                qty=line.product_uom_id._compute_quantity(line.product_uom_qty,line.product_id.uom_id,round=False)
                require(abs(qty-row["qty_allocated"])<1e-7,"Native SO quantity changed")
                lines.append((row["product_id"],row["qty_allocated"],line.id))
            picking=create_picking(dest,order.name,dict(partner_id=partner.id),lines)
            require(set(picking.move_ids.mapped("sale_line_id").ids)=={x[2] for x in lines},
                    "Native customer DO lost original sale lines")
            require(picking in order.picking_ids,"Native SO delivery link missing")
            customers|=picking
        for wid,items in sorted(stores.items()):
            store=env["stock.warehouse"].sudo().browse(wid)
            require(store.company_id==env.company and store!=pck and store.lot_stock_id,
                    "Invalid store destination")
            dispatches|=create_picking(transit,"%s / %s"%(batch.name,store.code),
                dict(ya_store_batch_id=batch.id,ya_store_warehouse_id=wid,ya_store_stage="dispatch"),
                [(pid,qty,None) for pid,qty in sorted(items.items())])
        return customers,dispatches
