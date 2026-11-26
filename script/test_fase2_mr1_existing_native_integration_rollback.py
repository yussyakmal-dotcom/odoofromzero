"""Actual Fase1 MR1 generator and native validation, clone-only rollback."""
from collections import defaultdict
from pathlib import Path
from odoo.addons.ya_material_requirement.models import material_requirement_batch as mr_base
from datetime import timedelta
from unittest.mock import patch
from odoo.addons.ya_sale_production_capacity.models import consolidation_cutoff_gate as gate
from odoo.addons.ya_sale_production_capacity.models.consolidation_cutoff_rules import DEFAULT_POLICY, schedule
from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.addons.ya_sale_production_capacity.models.pp1_native_sources import DB
from odoo.addons.ya_sale_production_capacity.models.pp1_review_contract import read_locked_review

assert env.cr.dbname==DB
assert Path(mr_base.__file__).resolve().is_relative_to(Path("/var/lib/ya-fase2-testing/source/addons/ya_material_requirement")),mr_base.__file__
module=env["ir.module.module"].search([("name","=","ya_sale_production_capacity")])
assert module.installed_version=="19.0.1.9.0",module.installed_version
Wizard=env["ya.consolidation.review.wizard"]
Batch=env["ya.packing.batch"]
Plan=env["ya.production.planning"]
Line=env["ya.production.planning.line"]
Sale=env["sale.order"]
RO=env["ya.store.ro"]
Users=env["res.users"].sudo()
Final=env["ya.sale.mo2.finalization"].sudo()
company=env.company
source=Line.browse(3150)
assert source.reference=="10042" and source._capacity_bom().product_qty==250
product=source.product_id
store=env["stock.warehouse"].search([("code","=","T_KD"),("company_id","=",company.id)])
assert len(store)==1
sample=Sale.sudo().search([("ya_is_capacity_so","=",True),
    ("partner_id","!=",False),("company_id","=",company.id)],limit=1)
assert sample
day=fields.Date.context_today(Plan)+timedelta(days=19)
slot="S1"
assert not env["ya.consolidation.cutoff.settings"].sudo().search_count([]),"Fresh default policy required for this fixture"
clock=schedule(day,slot,DEFAULT_POLICY)
second=timedelta(seconds=1)
domain=[("delivery_date","=",day),("slot","=",slot)]
for model in (Batch,Plan,RO,Final,env["ya.package.store.ro"],env["ya.sale.capacity.reservation"]):
    assert not model.sudo().search_count(domain),model._name
assert not Sale.sudo().search_count([("ya_delivery_date","=",day),("ya_slot","=",slot)])
group_field=next(n for n in ("group_ids","groups_id") if n in Users._fields)
def user(login,group):
    assert not Users.search_count([("login","=",login)])
    return Users.with_context(no_reset_password=True,tracking_disable=True,
        mail_create_nosubscribe=True,mail_notify_force_send=False).create({
        "name":login,"login":login,"company_id":company.id,"company_ids":[(6,0,[company.id])],
        group_field:[(6,0,[env.ref(g).id for g in group])]})
def reject(fn,exc_type,fragment=None):
    try:
        with env.cr.savepoint():
            fn()
    except exc_type as exc:
        assert not fragment or fragment in str(exc),str(exc)
    else:
        raise AssertionError("Unexpected acceptance")
def quote(qty):
    order=Sale.with_context(default_ya_is_capacity_so=True,tracking_disable=True,
        mail_create_nosubscribe=True,mail_notify_force_send=False).create({
        "partner_id":sample.partner_id.id,"company_id":company.id,
        "warehouse_id":sample.warehouse_id.id,"pricelist_id":sample.pricelist_id.id,
        "ya_delivery_date":day,"ya_slot":slot,
        "order_line":[(0,0,{"product_id":product.id,"name":product.display_name,
            "product_uom_qty":qty,"product_uom_id":product.uom_id.id,"price_unit":product.lst_price})]})
    env["ya.sale.capacity.confirm.wizard"].with_context(
        tracking_disable=True,mail_notify_force_send=False).create({
        "order_id":order.id,"delivery_date":day,"slot":slot}).action_check_and_confirm()
    assert order.state in ("sale","done") and not order.picking_ids
    return order
Picking=env["stock.picking"]
Quant=env["stock.quant"].sudo()
cdc=env["stock.warehouse"].search([("code","=","CDC"),("company_id","=",company.id)])
kitchen=source._capacity_bom().picking_type_id.warehouse_id
assert len(cdc)==1 and kitchen!=cdc
raw_ids=source._capacity_bom().bom_line_ids.mapped("product_id").ids
roots=(cdc.lot_stock_id|kitchen.lot_stock_id).ids
def sql_stock(cr):
    cr.execute("""SELECT product_id,location_id,company_id,lot_id,owner_id,package_id,
                         SUM(quantity),SUM(reserved_quantity)
        FROM stock_quant WHERE product_id IN %s AND location_id IN %s
        GROUP BY product_id,location_id,company_id,lot_id,owner_id,package_id
        HAVING SUM(quantity)<>0 OR SUM(reserved_quantity)<>0""",(tuple(raw_ids),tuple(roots)))
    return {tuple(r[:6]):(float(r[6]),float(r[7])) for r in cr.fetchall()}
persisted=sql_stock(env.cr)
def physical(pid,loc):
    return sum(Quant.search([("product_id","=",pid),("location_id","=",loc.id),
                             ("company_id","=",company.id)]).mapped("quantity"))
def totals(moves):
    out=defaultdict(float)
    for m in moves:
        out[m.product_id.id]+=m.product_uom._compute_quantity(
            m.product_uom_qty,m.product_id.uom_id,round=False)
    return dict(out)
try:
    packing=user("__ya_mr1_packing_uat__@example.invalid",["ya_store_ro.group_ya_packing_admin"])
    inventory=user("__ya_mr1_inventory_uat__@example.invalid",
                   ["ya_store_ro.group_ya_packing_admin","stock.group_stock_manager"])
    W=Wizard.with_user(packing)
    w=W.create({"stage":"pp1","delivery_date":day,"slot":slot})
    plan=Plan.create({"delivery_date":day,"slot":slot,
        "kitchen_code":source.planning_id.kitchen_code,
        "workcenter_id":source.planning_id.workcenter_id.id})
    line=Line.create({"planning_id":plan.id,"product_id":product.id,
        "reference":source.reference,"max_capacity":500,
        "uom_id":source.uom_id.id,"bom_id":source._capacity_bom().id})
    plan.action_publish()
    ro=RO.create({"planning_id":plan.id,"store_warehouse_id":store.id,
        "line_ids":[(0,0,{"product_id":product.id,"reference":product.default_code,
            "qty_requested":4,"uom_id":line.uom_id.id})]})
    ro.action_confirm()
    early=quote(1)
    with patch.object(gate,"utc_now",return_value=clock["ro_cutoff"]):
        w.action_review()
        response=w.action_release()
    batch=Batch.with_user(inventory).browse(response["res_id"])
    assert not batch.env.su and batch.env.user.has_group("stock.group_stock_manager")
    frozen=batch._ya_pp1_frozen_facts()
    mo=batch.line_ids.mo_id
    assert mo.state=="confirmed" and mo.product_qty==250
    expected=totals(mo.move_raw_ids)
    assert set(expected)==set(raw_ids)
    assert not batch.mr_native_transfer_ids
    reject(lambda:batch.with_user(packing).action_mr_generate_native_transfers(),UserError,
           "Inventory Administrator")
    batch.action_mr_refresh()
    assert len(batch.mr_kitchen_line_ids)==len(expected)
    actual={l.product_id.id:l.required_qty for l in batch.mr_kitchen_line_ids}
    assert set(actual)==set(expected) and all(abs(actual[p]-expected[p])<1e-7 for p in expected)
    assert not batch.mr_native_transfer_ids
    before={pid:(physical(pid,cdc.lot_stock_id),physical(pid,kitchen.lot_stock_id)) for pid in expected}
    # Actual existing Fase1 generator and report snapshot, not fixture picking.
    action=batch.action_mr_generate_native_transfers()
    picking=batch.mr_native_transfer_ids
    assert len(picking)==1 and picking.ya_mr_kitchen_id==kitchen
    assert picking.location_id==cdc.lot_stock_id and picking.location_dest_id==kitchen.lot_stock_id
    assert picking.picking_type_id==cdc.int_type_id and picking.state not in ("done","cancel")
    assert action["res_model"]=="stock.picking"
    assert totals(picking.move_ids)==expected and len(picking.move_ids)==len(expected)
    assert not batch.mr_pick_confirmation_ids
    assert before=={pid:(physical(pid,cdc.lot_stock_id),physical(pid,kitchen.lot_stock_id)) for pid in expected}
    print("NATIVE_EXISTING_MR1_GENERATOR_FULL_DEMAND_ONE_PER_KITCHEN_NO_POSTING_PASS")
    p_id=picking.id
    move_ids=picking.move_ids.ids
    batch.action_mr_generate_native_transfers()
    assert batch.mr_native_transfer_ids.ids==[p_id] and picking.move_ids.ids==move_ids
    assert totals(picking.move_ids)==expected
    print("NATIVE_EXISTING_MR1_REPEAT_NO_DUPLICATE_PASS")
    # The same native Validate guard must run without changing TEST_DB globals.
    def zero_qty():
        picking.move_ids[:1].write({"quantity":0})
        picking.button_validate()
    reject(zero_qty,UserError,"Qty = 0")
    picking.action_confirm()
    picking.action_assign()
    for m in picking.move_ids:
        assert abs(m.quantity-m.product_uom_qty)<1e-7,("CDC supply fixture shortage",m.product_id.default_code,m.quantity,m.product_uom_qty)
    picking.move_ids.write({"picked":True})
    picking.move_ids.mapped("move_line_ids").write({"picked":True})
    response=picking.with_context(skip_sms=True,mail_notify_force_send=False).button_validate()
    assert picking.state=="done" and all(m.state=="done" for m in picking.move_ids),response
    assert not Picking.sudo().search_count([("backorder_id","=",p_id)])
    for pid,qty in expected.items():
        assert abs(physical(pid,cdc.lot_stock_id)-before[pid][0]+qty)<1e-7
        assert abs(physical(pid,kitchen.lot_stock_id)-before[pid][1]-qty)<1e-7
        assert physical(pid,cdc.lot_stock_id)>=-1e-7
    print("NATIVE_EXISTING_MR1_VALIDATE_GUARD_AND_PHYSICAL_DELTA_PASS")
    # Later PP2 must not cause the already issued MR1 to be regenerated.
    with patch.object(gate,"utc_now",return_value=clock["so_cutoff"]-second):
        late=quote(250)
    w2=W.create({"stage":"pp2","delivery_date":day,"slot":slot})
    with patch.object(gate,"utc_now",return_value=clock["pp2_earliest"]):
        w2.action_review()
        w2.action_release()
    final=Final.search(domain)
    assert len(final)==1 and final.line_ids.qty_mo2==250
    batch.action_mr_generate_native_transfers()
    assert batch.mr_native_transfer_ids.ids==[p_id] and picking.move_ids.ids==move_ids
    assert totals(picking.move_ids)==expected and picking.state=="done"
    assert batch._ya_pp1_frozen_facts()==frozen and ro.line_ids.qty_requested==4
    assert not final.line_ids.ya_mo2_material_picking_ids
    assert not (early|late).mapped("picking_ids")
    print("MR1_EXISTING_DOC_UNCHANGED_AFTER_MO2_RELEASE_PASS")
    ids=(plan.id,ro.id,early.id,late.id,batch.id,mo.id,final.id,final.line_ids.mo_id.id,
         p_id,w.id,w2.id,packing.id,inventory.id)
finally:
    env.cr.rollback()
    print("EXPLICIT_ROLLBACK_EXECUTED")
env.invalidate_all(flush=False)
for model,ident in zip((Plan,RO,Sale,Sale,Batch,env["mrp.production"],Final,
    env["mrp.production"],Picking,Wizard,Wizard,Users,Users),ids):
    assert not model.sudo().browse(ident).exists(),model._name
assert not env["stock.move"].sudo().browse(move_ids).exists()
assert not env["ya.material.requirement.snapshot.line"].sudo().search_count([("batch_id","=",ids[4])])
with env.registry.cursor() as cr:
    observed=sql_stock(cr)
    assert set(observed)==set(persisted)
    for k,v in persisted.items():
        assert all(abs(a-b)<1e-7 for a,b in zip(v,observed[k])),(k,v,observed[k])
print("FASE2_MR1_EXISTING_NATIVE_INTEGRATION_ROLLBACK_PASS")
print("NO_MONKEYPATCH_DB_GUARD_NO_COMMIT_NO_FASE1_RUNTIME_CHANGE")
