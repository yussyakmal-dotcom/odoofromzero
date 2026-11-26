"""Read-only preflight for the two-kitchen Design B native test.
No picking, reservation, MO, inventory adjustment or stock mutation.
"""
from collections import defaultdict
from odoo.tools import float_compare

assert env.cr.dbname=="erp-yussyakmal-mrp-test-RO_SO"
env.cr.execute("SET TRANSACTION READ ONLY")
env.cr.execute("SHOW transaction_read_only")
assert env.cr.fetchone()[0]=="on"
Line=env["ya.production.planning.line"].sudo()
Product=env["product.product"].sudo()
Warehouse=env["stock.warehouse"].sudo()
Quant=env["stock.quant"].sudo()
Move=env["stock.move"].sudo()
component=Product.search([("default_code","=","11999")])
assert len(component)==1
pst=Line.search([("product_id","=",component.id),
    ("planning_id.state","=","published"),("planning_id.kitchen_code","=","PST"),
    ("max_capacity",">",0)],limit=1)
asn=Line.browse(3150).exists()
assert pst and asn and asn.reference=="10042"
company=asn._capacity_bom().picking_type_id.company_id
cdc=Warehouse.search([("code","=","CDC"),("company_id","=",company.id)])
assert len(cdc)==1
need=defaultdict(lambda:defaultdict(float))
products={}
for line,count in [(pst,2),(asn,2)]:
    bom=line._capacity_bom()
    wh=bom.picking_type_id.warehouse_id
    assert wh and wh.company_id==company
    print("FIXTURE_BOM",line.reference,bom.id,wh.code,bom.product_qty,"batches",count)
    for b in bom.bom_line_ids:
        p=b.product_id
        products[p.id]=p
        need[p.id][wh.id]+=b.product_uom_id._compute_quantity(
            b.product_qty,p.uom_id,round=False)*count
root=cdc.lot_stock_id
blockers=[]
for pid,by_wh in sorted(need.items(),key=lambda x:products[x[0]].default_code or ""):
    p=products[pid]
    required=sum(by_wh.values())
    q=Quant.search([("company_id","=",company.id),("product_id","=",pid),
        ("location_id","child_of",root.id),("location_id.usage","=","internal")])
    exact=q.filtered(lambda x:x.location_id==root and not (x.lot_id or x.owner_id or x.package_id))
    plain=q.filtered(lambda x:not (x.lot_id or x.owner_id or x.package_id))
    physical=sum(q.mapped("quantity"))
    reserved=sum(q.mapped("reserved_quantity"))
    eligible=sum(plain.mapped("quantity"))-sum(plain.mapped("reserved_quantity"))
    exact_free=sum(exact.mapped("quantity"))-sum(exact.mapped("reserved_quantity"))
    gap=max(required-eligible,0)
    status="ENOUGH_UNTRACKED_SUBTREE"
    if p.tracking!="none":
        status="TRACKING_REVIEW"
    elif float_compare(eligible,required,precision_rounding=p.uom_id.rounding)<0:
        status="INSUFFICIENT_FREE"
    elif float_compare(exact_free,required,precision_rounding=p.uom_id.rounding)<0:
        status="SUBLOCATION_REVIEW"
    info=dict(sku=p.default_code,product_id=pid,uom=p.uom_id.name,
        fixture_need_by_kitchen={Warehouse.browse(w).code:v for w,v in by_wh.items()},
        total_need=required,cdc_physical=physical,cdc_reserved=reserved,
        cdc_plain_subtree_free=eligible,cdc_exact_free=exact_free,gap=gap,status=status)
    print("CDC_MATERIAL",info)
    if status!="ENOUGH_UNTRACKED_SUBTREE" or p.default_code=="10741":
        blockers.append(info)
        open_moves=Move.search([("company_id","=",company.id),("product_id","=",pid),
            ("location_id","child_of",root.id),
            ("state","not in",["done","cancel"])])
        print("CDC_OPEN_MOVE_CLAIMS",p.default_code,[
            (m.id,m.state,m.picking_id.id,m.raw_material_production_id.id,
             m.product_uom._compute_quantity(m.product_uom_qty,p.uom_id,round=False),
             m.product_uom._compute_quantity(m.quantity,p.uom_id,round=False))
            for m in open_moves])
        for wh_id in by_wh:
            wh=Warehouse.browse(wh_id)
            kq=Quant.search([("company_id","=",company.id),("product_id","=",pid),
                ("location_id","child_of",wh.lot_stock_id.id),
                ("location_id.usage","=","internal")])
            print("KITCHEN_EXISTING_STOCK",p.default_code,wh.code,
                sum(kq.mapped("quantity")),sum(kq.mapped("reserved_quantity")))
print("CDC_FIXTURE_REVIEW_ROWS",blockers)
print("CDC_MATERIAL_SKU_COUNT",len(need))
print("FASE2_FINAL_PACKING_CDC_PREFLIGHT_READONLY_OK")
env.cr.rollback()
