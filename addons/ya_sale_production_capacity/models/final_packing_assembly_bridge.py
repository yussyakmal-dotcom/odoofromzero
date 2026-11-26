"""Clone rollback QA only: adapt final recipient allocation to native Paket MO.

Reuse Fase1 existing PCK operation type and canonical batch-MO link.
No new allocation algorithm, no alternative reservation system, no public
button, no permanent release before final allocation approval is persisted.
"""
from collections import defaultdict
from odoo import fields
from .pp1_native_sources import DB, require
from .final_packing_demand import read_final_packing_demand
from .final_packing_proposal_rules import validate_proposal
from odoo.addons.ya_package_store_ro.models.package_finish_rules import group_package_finish_demands


def _qa_create_native_paket_assembly(batch, proposal):
    batch.ensure_one()
    env=batch.env
    require(env.cr.dbname==DB and env.user.has_group("ya_store_ro.group_ya_packing_admin"),
            "Clone Packing Admin required")
    with env.cr.savepoint():
        # Re-read and revalidate under the existing slot lock.
        demand=read_final_packing_demand(batch)
        validated=validate_proposal(demand,proposal)
        original={(r["kind"],r["source_id"],r["line_id"]):r for r in demand["recipient_rows"]}
        ro_paket=[]
        customer_paket=defaultdict(int)
        boms={}
        components=defaultdict(lambda:defaultdict(float))
        for r in validated["rows"]:
            qty=r["qty_allocated"]
            if not qty or r["kind"] not in ("SO_PAKET","RO_PAKET"):
                continue
            src=original[(r["kind"],r["source_id"],r["line_id"])]
            pid=r["product_id"]
            require(pid not in boms or boms[pid]==src["bom_id"],"Conflicting Paket BoM")
            boms[pid]=src["bom_id"]
            for c in src["components"]:
                components[pid][c["product_id"]]+=c["qty_per_package"]*qty
            if r["kind"]=="RO_PAKET":
                ro_paket.append(dict(product_id=pid,store_id=r["recipient_id"],qty=qty))
            else:
                customer_paket[pid]+=qty
        # Reuse existing Fase1 store/Paket grouping; SO recipients stay
        # separate (no fake store ID or synthetic RO).
        quantities=group_package_finish_demands(ro_paket)["assembly_mo_qty"]
        for pid,qty in customer_paket.items():
            quantities[pid]=quantities.get(pid,0)+qty
        if not quantities:
            return env["mrp.production"]
        pck=env["stock.warehouse"].sudo().browse(demand["supply"]["pck_id"])
        operation=batch._ya_pck_manufacturing_type(pck)
        root=pck.lot_stock_id
        require(pck.company_id==env.company and root.usage=="internal","Invalid PCK route")
        mos=env["mrp.production"]
        for pid,qty in sorted(quantities.items()):
            product=env["product.product"].browse(pid)
            bom=env["mrp.bom"].browse(boms[pid])
            require(bom.active and bom.type=="normal" and
                    bom.product_tmpl_id==product.product_tmpl_id and
                    (not bom.product_id or bom.product_id==product) and
                    (not bom.company_id or bom.company_id==env.company) and
                    abs(bom.product_uom_id._compute_quantity(bom.product_qty,product.uom_id,round=False)-1)<1e-9,
                    "Invalid assembly BoM")
            mo=mos.create(dict(product_id=pid,product_qty=float(qty),
                product_uom_id=product.uom_id.id,bom_id=bom.id,
                picking_type_id=operation.id,location_src_id=root.id,
                location_dest_id=root.id,company_id=env.company.id,
                date_start=fields.Datetime.now(),origin="%s / Paket %s"%(batch.name,product.default_code or pid),
                ya_package_assembly_batch_id=batch.id))
            mo.action_confirm()
            require(mo.state not in ("draft","cancel","done") and not mo.workorder_ids
                    and mo.location_src_id==root and mo.location_dest_id==root,
                    "Native Paket MO confirmation failed")
            actual=defaultdict(float)
            for m in mo.move_raw_ids:
                require(m.state not in ("cancel","done") and m.location_id==root,
                        "Invalid native Paket component route")
                actual[m.product_id.id]+=m.product_uom._compute_quantity(
                    m.product_uom_qty,m.product_id.uom_id,round=False)
            expected=components[pid]
            require(set(actual)==set(expected) and all(abs(actual[p]-expected[p])<1e-7 for p in expected),
                    "Native Paket raw demand differs from final allocation")
            mo.action_assign()
            for m in mo.move_raw_ids:
                require(m.state=="assigned" and abs(m.quantity-m.product_uom_qty)<1e-7,
                        "Native Paket raw stock not fully reserved")
                require(all(l.location_id==root and not(l.lot_id or l.owner_id or l.package_id)
                            for l in m.move_line_ids),"Unsupported native Paket reservation scope")
            mos|=mo
        return mos
