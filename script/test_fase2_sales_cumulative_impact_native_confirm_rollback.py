"""Clone-only cumulative Sales Admin preview and atomic native Confirm QA."""
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
    sales=user("__ya_sales_impact_uat__@example.invalid","sales_team.group_sale_salesman")
    packing=user("__ya_sales_impact_packing__@example.invalid","ya_store_ro.group_ya_packing_admin")
    assert not sales.has_group("ya_store_ro.group_ya_packing_admin")
    def draft(qty):
        order=Sale.with_context(default_ya_is_capacity_so=True,tracking_disable=True,
            mail_create_nosubscribe=True,mail_notify_force_send=False).create({
            "partner_id":sample.partner_id.id,"company_id":company.id,"user_id":sales.id,
            "warehouse_id":sample.warehouse_id.id,"pricelist_id":sample.pricelist_id.id,
            "ya_delivery_date":day,"ya_slot":slot,
            "order_line":[(0,0,{"product_id":product.id,"name":product.display_name,
                "product_uom_qty":qty,"product_uom_id":product.uom_id.id,"price_unit":product.lst_price})]})
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
        assert order._ya_verified_confirmed_demand()["order_id"]==order.id
    plan=Plan.create({"delivery_date":day,"slot":slot,
        "kitchen_code":source.planning_id.kitchen_code,
        "workcenter_id":source.planning_id.workcenter_id.id})
    line=Line.create({"planning_id":plan.id,"product_id":product.id,
        "reference":source.reference,"max_capacity":500,
        "uom_id":source.uom_id.id,"bom_id":source._capacity_bom().id})
    plan.action_publish()
    view=env.ref("ya_sale_production_capacity.view_ya_sale_capacity_confirm_wizard_form")
    arch=SW.with_user(sales).get_view(view_id=view.id,view_type="form")["arch"]
    assert "action_review_impact" in arch and "impact_summary" in arch
    with patch.object(gate,"utc_now",return_value=clock["ro_cutoff"]-second):
        early,ew=draft(5)
        reject(ew.action_check_and_confirm,UserError,"Simulasi Dampak")
        native_counts=lambda:tuple(env[m].sudo().search_count([]) for m in
            ("mrp.production","stock.picking","stock.move","stock.move.line"))
        before=native_counts()
        x=sim(ew)
        assert ew.impact_payload["stage"]=="pp1" and not ew.impact_payload["ro_closed"]
        assert (x["so_before"],x["so_after"],x["output_before"],x["output_after"],
                x["additional_output"],x["new_surplus"])==(0,5,0,250,250,245)
        assert "RO belum ditutup" in ew.impact_summary
        assert early.state in ("draft","sent") and not Ledger.search_count(domain)
        assert native_counts()==before
        ro=RO.create({"planning_id":plan.id,"store_warehouse_id":store.id,
            "line_ids":[(0,0,{"product_id":product.id,"reference":product.default_code,
                "qty_requested":4,"uom_id":line.uom_id.id})]})
        ro.action_confirm()
        reject(ew.action_check_and_confirm,UserError,"Data berubah")
        assert not Ledger.search_count(domain)
        x=sim(ew)
        assert (x["ro_store"],x["output_before"],x["output_after"],x["absorbed_surplus"])==(4,250,250,5)
        confirm(ew,early)
        assert native_counts()==before
    print("SALES_PP1_KNOWN_RO_AND_LARGE_SURPLUS_WARNING_STALE_GATE_PASS")
    pw=Wizard.with_user(packing).create({"stage":"pp1","delivery_date":day,"slot":slot})
    with patch.object(gate,"utc_now",return_value=clock["ro_cutoff"]):
        pw.action_review()
        response=pw.action_release()
    batch=Batch.with_user(packing).browse(response["res_id"])
    frozen=batch._ya_pp1_frozen_facts()
    assert batch.line_ids.mo_id.product_qty==250
    with patch.object(gate,"utc_now",return_value=clock["so_cutoff"]-second):
        fill,fw=draft(245)
        crossing,cw=draft(1)
        before=native_counts()
        x=sim(fw)
        assert fw.impact_payload["stage"]=="pp2"
        assert (x["so_before"],x["so_after"],x["mo1"],x["mo2_before"],x["mo2_after"],
                x["ro_store_short_after"])==(5,250,250,0,0,4)
        y=sim(cw)
        assert (y["so_before"],y["so_after"],y["additional_output"])==(5,6,0)
        confirm(fw,fill)
        reject(cw.action_check_and_confirm,UserError,"Data berubah")
        x=sim(cw)
        assert (x["so_before"],x["so_after"],x["mo2_before"],x["mo2_after"],
                x["additional_output"],x["surplus_after"])==(250,251,0,250,250,245)
        confirm(cw,crossing)
        last,lw=draft(1)
        x=sim(lw)
        assert (x["so_before"],x["so_after"],x["mo2_before"],x["mo2_after"],
                x["additional_output"],x["absorbed_surplus"])==(251,252,250,250,0,1)
        confirm(lw,last)
        excessive,xw=draft(249)
        reject(xw.action_review_impact,UserError,"Published Planning Max")
        assert native_counts()==before
    print("SALES_PP2_CUMULATIVE_SO_ONLY_MARGINAL_BATCH_STALE_AND_MAX_PASS")
    assert batch._ya_pp1_frozen_facts()==frozen and ro.line_ids.qty_requested==4
    assert not Final.search_count(domain)
    pp2=batch._ya_read_pp2_design_b_review()["facts"]["sku_forecasts"][0]
    assert pp2["confirmed_so_qty"]==252 and pp2["mo2_increment_due_to_so_only"]==250
    assert pp2["theoretical_extra_not_automatically_allocated"]==244
    assert sum(Ledger.search(domain).mapped("qty_required"))==252
    assert not (early|fill|crossing|last|excessive).mapped("picking_ids")
    with patch.object(gate,"utc_now",return_value=clock["so_cutoff"]):
        reject(xw.action_review_impact,UserError,"Cutoff SO")
    transient=SW.with_user(sales).new({"order_id":excessive.id,"delivery_date":day,"slot":"S2",
        "impact_digest":"old","impact_summary":"old"})
    transient._onchange_impact_schedule()
    assert not transient.impact_digest and not transient.impact_summary
    print("SALES_FORECAST_MATCHES_PP2_SOURCE_NO_MO2_OR_DO_PASS")
    ids=(plan.id,ro.id,batch.id,batch.line_ids.mo_id.id,sales.id,packing.id,pw.id)
    order_ids=(early|fill|crossing|last|excessive).ids
    wizard_ids=(ew|fw|cw|lw|xw).ids
finally:
    env.cr.rollback()
    print("EXPLICIT_ROLLBACK_EXECUTED")
env.invalidate_all(flush=False)
for model,ident in zip((Plan,RO,Batch,env["mrp.production"],Users,Users,Wizard),ids):
    assert not model.sudo().browse(ident).exists(),model._name
assert not Sale.sudo().browse(order_ids).exists()
assert not SW.sudo().browse(wizard_ids).exists()
assert not Ledger.search_count(domain)
print("FASE2_SALES_CUMULATIVE_IMPACT_NATIVE_CONFIRM_ROLLBACK_PASS")
print("NO_BROWSER_NO_TIMER_NO_COMMIT")
