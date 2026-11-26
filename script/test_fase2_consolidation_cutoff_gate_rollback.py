"""Native admission QA; simulated clock only, no timer or release, rollback."""
from datetime import timedelta
from unittest.mock import patch
from odoo import fields
from odoo.exceptions import UserError
from odoo.addons.ya_sale_production_capacity.models import consolidation_cutoff_gate as gate
from odoo.addons.ya_sale_production_capacity.models.consolidation_cutoff_rules import (
    DEFAULT_POLICY, schedule, clock_state)
assert env.cr.dbname==gate.DB
day=fields.Date.context_today(env["ya.production.planning"])+timedelta(days=21)
slot="S1"
s=schedule(day,slot,DEFAULT_POLICY)
second=timedelta(seconds=1)
for x in ("S1","S2","S3"):
    d=schedule(day,x,DEFAULT_POLICY)
    assert d["ro_cutoff"]==s["ro_cutoff"]
    assert clock_state(day,x,d["ro_cutoff"]-second,DEFAULT_POLICY)["ro_admission_allowed"]
    assert not clock_state(day,x,d["ro_cutoff"],DEFAULT_POLICY)["ro_admission_allowed"]
    assert clock_state(day,x,d["ro_cutoff"],DEFAULT_POLICY)["pp1_clock_ready"]
    if x!="S1":
        assert not clock_state(day,x,d["dispatch"]-second,DEFAULT_POLICY)["pp2_clock_ready"]
assert clock_state(day,slot,s["so_cutoff"]-second,DEFAULT_POLICY)["so_admission_allowed"]
assert not clock_state(day,slot,s["so_cutoff"],DEFAULT_POLICY)["so_admission_allowed"]
assert not clock_state(day,slot,s["pp2_earliest"]-second,DEFAULT_POLICY)["pp2_clock_ready"]
assert clock_state(day,slot,s["pp2_earliest"],DEFAULT_POLICY)["pp2_clock_ready"]
assert not clock_state(day,slot,s["dispatch"],DEFAULT_POLICY)["pp2_clock_ready"]
print("CUTOFF_WIB_EXACT_BOUNDARY_AND_UNKNOWN_SLOT_PP2_PASS")
def rejected(fn,fragment):
    try:
        with env.cr.savepoint():
            fn()
    except UserError as exc:
        assert fragment in str(exc),str(exc)
    else:
        raise AssertionError("Unexpected acceptance: "+fragment)
Plan=env["ya.production.planning"]
Line=env["ya.production.planning.line"]
RO=env["ya.store.ro"]
Package=env["ya.package.store.ro"]
Sale=env["sale.order"]
Batch=env["ya.packing.batch"]
company=env.company
domain=[("delivery_date","=",day),("slot","=",slot)]
for model in (Plan,RO,Package,Batch,env["ya.sale.capacity.reservation"]):
    assert not model.sudo().search_count(domain),model._name
source=Line.browse(3150)
assert source.reference=="10042"
product=source.product_id
store=env["stock.warehouse"].search([("code","=","T_KD"),("company_id","=",company.id)])
pkgstore=env["stock.warehouse"].search([("code","=","T_BAN"),("company_id","=",company.id)])
pkg=env["product.product"].search([("default_code","=","12114")])
assert len(store)==len(pkgstore)==len(pkg)==1
sample=Sale.sudo().search([("ya_is_capacity_so","=",True),("partner_id","!=",False),
    ("company_id","=",company.id)],limit=1)
assert sample
try:
    plan=Plan.create({"delivery_date":day,"slot":slot,
        "kitchen_code":source.planning_id.kitchen_code,
        "workcenter_id":source.planning_id.workcenter_id.id})
    line=Line.create({"planning_id":plan.id,"product_id":product.id,
        "reference":source.reference,"max_capacity":500,
        "uom_id":source.uom_id.id,"bom_id":source._capacity_bom().id})
    plan.action_publish()
    rovals={"planning_id":plan.id,"store_warehouse_id":store.id,
        "line_ids":[(0,0,{"product_id":product.id,"reference":product.default_code,
            "qty_requested":4,"uom_id":line.uom_id.id})]}
    ro=RO.create(rovals)
    Users=env["res.users"].sudo()
    gf=next(n for n in ("group_ids","groups_id") if n in Users._fields)
    login="__ya_cutoff_paket_smoke__@example.invalid"
    assert not Users.search_count([("login","=",login)])
    creator=Users.with_context(no_reset_password=True,tracking_disable=True,
        mail_create_nosubscribe=True,mail_notify_force_send=False).create({
        "name":login,"login":login,"company_id":company.id,
        "company_ids":[(6,0,[company.id])],
        gf:[(6,0,[env.ref("ya_package_store_ro.group_ya_package_ro_creator").id])]})
    paket=Package.with_user(creator).sudo().create({
        "delivery_date":day,"slot":slot,"store_warehouse_id":pkgstore.id,
        "line_ids":[(0,0,{"product_id":pkg.id,"qty_requested":1})]})
    with patch.object(gate,"utc_now",return_value=s["ro_cutoff"]):
        rejected(ro.action_confirm,"Cutoff RO")
        rejected(paket.action_confirm,"Cutoff RO")
        rejected(lambda:ro.write({"state":"confirmed"}),"Cutoff RO")
        rejected(lambda:RO.create(dict(rovals,state="confirmed")),"Buat RO dalam Draft")
    assert ro.state==paket.state=="draft"
    assert not Batch.search_count(domain)
    with patch.object(gate,"utc_now",return_value=s["ro_cutoff"]-second):
        ro.action_confirm()
        paket.action_confirm()
    assert ro.state==paket.state=="confirmed"
    print("NATIVE_RO_AND_PAKET_CUTOFF_WITHOUT_BATCH_PASS")
    order=Sale.with_context(default_ya_is_capacity_so=True,tracking_disable=True,
        mail_create_nosubscribe=True,mail_notify_force_send=False).create({
        "partner_id":sample.partner_id.id,"company_id":company.id,
        "warehouse_id":sample.warehouse_id.id,"pricelist_id":sample.pricelist_id.id,
        "ya_delivery_date":day,"ya_slot":slot,
        "order_line":[(0,0,{"product_id":product.id,"name":product.display_name,
            "product_uom_qty":1,"product_uom_id":product.uom_id.id,"price_unit":product.lst_price})]})
    with patch.object(gate,"utc_now",return_value=s["so_cutoff"]):
        rejected(lambda:order._ya_confirm_with_protected_capacity(day,slot),"Cutoff SO")
    assert order.state in ("draft","sent") and not order.picking_ids
    assert not env["ya.sale.capacity.reservation"].sudo().search_count(domain)
    with patch.object(gate,"utc_now",return_value=s["so_cutoff"]-second):
        order._ya_confirm_with_protected_capacity(day,slot)
    assert order.state in ("sale","done") and not order.picking_ids
    assert env["ya.sale.capacity.reservation"].sudo().search_count(domain)==1
    assert not Batch.search_count(domain)
    print("NATIVE_SO_S1_EXACT_CUTOFF_CONFIRM_AND_LEDGER_PASS")
    ids=(plan.id,ro.id,paket.id,order.id,creator.id)
finally:
    env.cr.rollback()
    print("EXPLICIT_ROLLBACK_EXECUTED")
env.invalidate_all(flush=False)
for model,ident in zip((Plan,RO,Package,Sale,Users),ids):
    assert not model.sudo().browse(ident).exists(),model._name
assert not env["ya.sale.capacity.reservation"].sudo().search_count(domain)
print("FASE2_CONSOLIDATION_CUTOFF_GATE_ROLLBACK_PASS")
print("DEFAULT_POLICY_ONLY_NO_SETTINGS_NO_TIMER_NO_RELEASE")
