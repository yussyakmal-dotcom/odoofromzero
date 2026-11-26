"""Mixed SO Paket/ordinary Sales simulation, real native confirmation, rollback."""
from datetime import timedelta
from unittest.mock import patch
from odoo.addons.ya_sale_production_capacity.models import consolidation_cutoff_gate as gate
from odoo.addons.ya_sale_production_capacity.models.consolidation_cutoff_rules import DEFAULT_POLICY, schedule
from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.addons.ya_sale_production_capacity.models.pp1_native_sources import DB
from odoo.addons.ya_sale_production_capacity.models.pp1_review_contract import read_locked_review

assert env.cr.dbname==DB
module=env["ir.module.module"].search([("name","=","ya_sale_production_capacity")])
assert module.installed_version=="19.0.1.14.0",module.installed_version
Wizard=env["ya.consolidation.review.wizard"]
Batch=env["ya.packing.batch"]
Plan=env["ya.production.planning"]
Line=env["ya.production.planning.line"]
Sale=env["sale.order"]
RO=env["ya.store.ro"]
Users=env["res.users"].sudo()
Final=env["ya.sale.mo2.finalization"].sudo()
company=env.company
Product=env["product.product"]
Package=env["ya.package.store.ro"]
product=Product.search([("default_code","=","11999")])
pkg=Product.search([("default_code","=","12114")])
pck_parts=Product.search([("default_code","in",["12014","12019"])])
assert len(product)==len(pkg)==1 and len(pck_parts)==2
source=Line.search([("product_id","=",product.id),
    ("planning_id.state","=","published"),("planning_id.kitchen_code","=","PST"),
    ("max_capacity",">",0)],limit=1)
assert source and source._capacity_bom().product_qty==7
pkg_store=env["stock.warehouse"].search([("code","=","T_BAN"),("company_id","=",company.id)])
assert len(pkg_store)==1
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
        group_field:[(6,0,[env.ref(group).id])]})
def reject(fn,exc_type,fragment=None):
    try:
        with env.cr.savepoint():
            fn()
    except exc_type as exc:
        assert not fragment or fragment in str(exc),str(exc)
    else:
        raise AssertionError("Unexpected acceptance")
SW=env["ya.sale.capacity.confirm.wizard"]
Ledger=env["ya.sale.capacity.reservation"].sudo()
try:
    sales=user("__ya_sales_paket_uat__@example.invalid","sales_team.group_sale_salesman")
    packing=user("__ya_sales_paket_packing__@example.invalid","ya_store_ro.group_ya_packing_admin")
    creator=user("__ya_sales_paket_ro__@example.invalid","ya_package_store_ro.group_ya_package_ro_creator")
    assert not sales.has_group("ya_store_ro.group_ya_packing_admin")
    def draft(items):
        order=Sale.with_context(default_ya_is_capacity_so=True,tracking_disable=True,
            mail_create_nosubscribe=True,mail_notify_force_send=False).create({
            "partner_id":sample.partner_id.id,"company_id":company.id,"user_id":sales.id,
            "warehouse_id":sample.warehouse_id.id,"pricelist_id":sample.pricelist_id.id,
            "ya_delivery_date":day,"ya_slot":slot,
            "order_line":[(0,0,{"product_id":p.id,"name":p.display_name,
                "product_uom_qty":qty,"product_uom_id":p.uom_id.id,"price_unit":p.lst_price})
                for p,qty in items]})
        w=SW.with_user(sales).with_context(tracking_disable=True,mail_notify_force_send=False,
            mail_create_nosubscribe=True).create({"order_id":order.id,"delivery_date":day,"slot":slot})
        assert not w.env.su and w.env.uid==sales.id
        return order,w
    def sim(w):
        action=w.action_review_impact()
        assert action["res_id"]==w.id and len(w.impact_digest)==64
        assert len(w.impact_payload["lines"])==1
        return w.impact_payload["lines"][0]
    def confirm(w,order):
        w.action_check_and_confirm()
        assert order.state in ("sale","done") and not order.picking_ids
        return order._ya_verified_confirmed_demand()
    plan=Plan.create({"delivery_date":day,"slot":slot,
        "kitchen_code":source.planning_id.kitchen_code,
        "workcenter_id":source.planning_id.workcenter_id.id})
    line=Line.create({"planning_id":plan.id,"product_id":product.id,
        "reference":source.reference,"max_capacity":14,
        "uom_id":source.uom_id.id,"bom_id":source._capacity_bom().id})
    plan.action_publish()
    counts=lambda:tuple(env[m].sudo().search_count([]) for m in
            ("mrp.production","stock.picking","stock.move","stock.move.line"))
    with patch.object(gate,"utc_now",return_value=clock["ro_cutoff"]-second):
        ro=RO.create({"planning_id":plan.id,"store_warehouse_id":store.id,
            "line_ids":[(0,0,{"product_id":product.id,"reference":product.default_code,
                "qty_requested":4,"uom_id":line.uom_id.id})]})
        ro.action_confirm()
        rp=Package.with_user(creator).sudo().create({
            "delivery_date":day,"slot":slot,"store_warehouse_id":pkg_store.id,
            "line_ids":[(0,0,{"product_id":pkg.id,"qty_requested":8})]})
        rp.action_confirm()
        assert ro.state==rp.state=="confirmed"
        early,ew=draft([(product,3),(pkg,2)])
        before=counts()
        x=sim(ew)
        assert ew.impact_payload["stage"]=="pp1" and not ew.impact_payload["ro_closed"]
        assert (x["new_qty"],x["so_before"],x["so_after"],x["ro_package"],x["ro_store"],
                x["output_before"],x["output_after"],x["surplus_before"],x["surplus_after"],
                x["ro_package_short_after"],x["ro_store_short_after"])==(5,0,5,8,4,14,14,2,0,0,3)
        assert x["product_id"]==product.id and x["additional_output"]==0
        assert dict(ew.impact_payload["pck_requirements"])=={p.id:2 for p in pck_parts}
        assert len(ew.impact_payload["source_rows"])==2
        assert not Ledger.search_count(domain) and counts()==before
        snap=confirm(ew,early)
        assert len(snap["source_rows"])==2 and len(snap["ledger_rows"])==1
        assert snap["ledger_rows"][0]["qty_required"]==5
        assert counts()==before
    print("SALES_MIXED_DIRECT_PAKET_PP1_NO_DOUBLE_COUNT_RO_DISPLACEMENT_PASS")
    pw=Wizard.with_user(packing).create({"stage":"pp1","delivery_date":day,"slot":slot})
    with patch.object(gate,"utc_now",return_value=clock["ro_cutoff"]):
        pw.action_review()
        response=pw.action_release()
    batch=Batch.with_user(packing).browse(response["res_id"])
    frozen=batch._ya_pp1_frozen_facts()
    assert len(batch.line_ids)==1 and batch.line_ids.mo_id.product_qty==14
    with patch.object(gate,"utc_now",return_value=clock["so_cutoff"]-second):
        late,lw=draft([(pkg,2)])
        before=counts()
        x=sim(lw)
        assert lw.impact_payload["stage"]=="pp2" and lw.impact_payload["ro_closed"]
        assert (x["new_qty"],x["so_before"],x["so_after"],x["mo1"],
                x["mo2_before"],x["mo2_after"],x["additional_output"],
                x["ro_package_short_before"],x["ro_package_short_after"],
                x["ro_store_short_before"],x["ro_store_short_after"])==(2,5,7,14,0,0,0,0,1,3,4)
        assert dict(lw.impact_payload["pck_requirements"])=={p.id:2 for p in pck_parts}
        snap=confirm(lw,late)
        assert len(snap["ledger_rows"])==1 and snap["ledger_rows"][0]["qty_required"]==2
        excessive,xw=draft([(pkg,8)])
        reject(xw.action_review_impact,UserError,"Published Planning Max")
        assert excessive.state in ("draft","sent") and not excessive.picking_ids
        assert counts()==before
    print("SALES_PAKET_PP2_RO_PAKET_DISPLACEMENT_NO_MO2_MAX_GATE_PASS")
    facts=batch._ya_read_pp2_design_b_review()["facts"]["sku_forecasts"]
    assert len(facts)==1
    f=facts[0]
    assert (f["confirmed_so_qty"],f["early_so_qty"],f["late_so_qty"],
            f["mo2_increment_due_to_so_only"],f["forecast_ro_package_shortage"],
            f["forecast_ro_store_shortage"])==(7,5,2,0,1,4)
    assert sum(Ledger.search(domain).mapped("qty_required"))==7
    assert batch._ya_pp1_frozen_facts()==frozen
    assert ro.line_ids.qty_requested==4 and rp.line_ids.qty_requested==8
    assert not Final.search_count(domain)
    assert not (early|late|excessive).mapped("picking_ids")
    print("SALES_PAKET_FORECAST_MATCHES_PP2_NATIVE_SOURCE_PASS")
    ids=(plan.id,ro.id,rp.id,batch.id,batch.line_ids.mo_id.id,sales.id,packing.id,creator.id,pw.id)
    order_ids=(early|late|excessive).ids
    wizard_ids=(ew|lw|xw).ids
finally:
    env.cr.rollback()
    print("EXPLICIT_ROLLBACK_EXECUTED")
env.invalidate_all(flush=False)
for model,ident in zip((Plan,RO,Package,Batch,env["mrp.production"],Users,Users,Users,Wizard),ids):
    assert not model.sudo().browse(ident).exists(),model._name
assert not Sale.sudo().browse(order_ids).exists()
assert not SW.sudo().browse(wizard_ids).exists()
assert not Ledger.search_count(domain)
print("FASE2_SALES_PAKET_CUMULATIVE_IMPACT_ROLLBACK_PASS")
print("NO_BROWSER_NO_TIMER_NO_COMMIT")
