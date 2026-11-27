"""READ ONLY: audit exact released MR1/MR2 and stock commitments before shortage revision."""
from collections import defaultdict
assert env.cr.dbname == "erp-yussyakmal-mrp-test-RO_SO", "wrong database"
print("DATABASE:", env.cr.dbname)
batch = env["ya.packing.batch"].sudo().search([
    ("delivery_date","=","2026-11-30"),("slot","=","S1")])
assert len(batch)==1 and batch.ya_pp1_design_b_snapshot, "expected test batch"
final = env["ya.sale.mo2.finalization"].sudo().search([("batch_id","=",batch.id)])
assert len(final)==1 and final.ya_pp2_design_b_snapshot, "PP2 not finalized"
print("BATCH:",batch.id,batch.name)
for stage, mos in (("MR1",batch.line_ids.mapped("mo_id")),("MR2",final.line_ids.mapped("mo_id"))):
    print("STAGE:",stage)
    for mo in mos:
        print("MO:",mo.id,mo.name,mo.product_id.default_code,mo.product_qty,mo.state,mo.picking_type_id.warehouse_id.code)
    for wh in mos.mapped("picking_type_id.warehouse_id"):
        raw = mos.filtered(lambda m:m.picking_type_id.warehouse_id==wh).move_raw_ids
        products = raw.mapped("product_id")
        locs = env["stock.location"].sudo().search([("id","child_of",wh.lot_stock_id.id),("usage","=","internal")])
        for p in products:
            d = raw.filtered(lambda m:m.product_id==p and m.state not in ("done","cancel"))
            def qty(ms):
                return sum(m.product_uom._compute_quantity(m.product_uom_qty,p.uom_id,round=False) for m in ms)
            quants = env["stock.quant"].sudo().search([("company_id","=",wh.company_id.id),("location_id","in",locs.ids),("product_id","=",p.id)])
            others = env["stock.move"].sudo().search([("company_id","=",wh.company_id.id),("location_id","in",locs.ids),("product_id","=",p.id),("state","not in",["done","cancel","draft"]),("raw_material_production_id","!=",False),("id","not in",d.ids)])
            incoming = env["stock.move"].sudo().search([("company_id","=",wh.company_id.id),("location_dest_id","in",locs.ids),("location_id","not in",locs.ids),("product_id","=",p.id),("state","not in",["done","cancel","draft"]),("picking_id","!=",False)])
            print("MATERIAL:",wh.code,p.default_code,p.uom_id.name,"need",qty(d),"physical",sum(quants.mapped("quantity")),"reserved",sum(quants.mapped("reserved_quantity")),"other_open_mo",qty(others),"incoming_open",qty(incoming),"incoming_ids",incoming.mapped("picking_id").ids)
pickings=env["stock.picking"].sudo().search(["|",("ya_mr_batch_id","=",batch.id),("ya_mr2_finalization_id","=",final.id)])
for p in pickings:
    print("TRANSFER:",p.id,p.name,p.state,p.origin,"MR1",p.ya_mr_batch_id.id,"MR2",p.ya_mr2_finalization_id.id)
report=env.ref("stock.action_report_picking",raise_if_not_found=False)
if report:
    print("PICKING_REPORT:",report.report_name)
    v=env.ref(report.report_name,raise_if_not_found=False)
    if v:
        print("REPORT_VIEW:",v.id,v.key)
        children=env["ir.ui.view"].sudo().search([("inherit_id","=",v.id),("active","=",True)])
        print("REPORT_INHERIT:",[(x.id,x.name,x.key) for x in children])
env.cr.rollback()
print("MR_STAGE_COMMITMENT_AUDIT_READ_ONLY_DONE")
