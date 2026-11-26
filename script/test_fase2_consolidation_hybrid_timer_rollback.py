"""Focused hybrid timer QA. No actual scheduler activation or commit."""
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
        group_field:[(6,0,[env.ref(group).id])]})
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
Queue=env["ya.consolidation.timer.queue"]
cron=env.ref("ya_sale_production_capacity.ir_cron_ya_prepare_consolidation")
assert not cron.active and cron.interval_number==5 and cron.interval_type=="minutes"
assert not Queue.sudo().search_count(domain)
try:
    packing=user("__ya_timer_packing_smoke__@example.invalid","ya_store_ro.group_ya_packing_admin")
    outsider=user("__ya_timer_stock_smoke__@example.invalid","stock.group_stock_user")
    Q=Queue.with_user(packing)
    assert not Q.env.su
    reject(lambda:Queue.with_user(outsider)._cron_prepare_consolidation(),UserError,"Packing Admin")
    menu=env.ref("ya_sale_production_capacity.menu_ya_consolidation_timer_queue")
    view=env.ref("ya_sale_production_capacity.view_ya_consolidation_timer_queue_list")
    assert menu.parent_id==env.ref("ya_workflow_navigation.menu_ya_before_production")
    assert "action_open_review" in Q.get_view(view_id=view.id,view_type="list")["arch"]
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
    def entry(stage):
        return Q.search(domain+[("stage","=",stage)])
    def tick(at):
        before=(env["mrp.production"].sudo().search_count([]),
                Batch.sudo().search_count([]),Final.search_count([]),
                env["stock.picking"].sudo().search_count([]))
        with patch.object(gate,"utc_now",return_value=at):
            Q._cron_prepare_consolidation()
        after=(env["mrp.production"].sudo().search_count([]),
               Batch.sudo().search_count([]),Final.search_count([]),
               env["stock.picking"].sudo().search_count([]))
        assert before==after,"Timer created business documents"
    tick(clock["ro_cutoff"]-second)
    assert not entry("pp1") and not entry("pp2")
    tick(clock["ro_cutoff"])
    pp1=entry("pp1")
    assert len(pp1)==1 and pp1.state=="ready" and pp1.sku_count==1 and pp1.digest
    initial=(pp1.id,pp1.digest,pp1.prepared_at)
    tick(clock["ro_cutoff"])
    assert (entry("pp1").id,pp1.digest,pp1.prepared_at)==initial
    assert not entry("pp2") and not Batch.search_count(domain)
    reject(lambda:pp1.write({"state":"released"}),(UserError,AccessError))
    print("TIMER_PP1_AT_RO_CUTOFF_IDEMPOTENT_NO_MO_PASS")
    # A new SO between preparation and review must appear in fresh review.
    with patch.object(gate,"utc_now",return_value=clock["ro_cutoff"]):
        extra=quote(1)
        action=pp1.action_open_review()
        w=Wizard.with_user(packing).browse(action["res_id"])
        assert w.digest!=initial[1] and w.line_ids.qty_so==2
        tick(clock["ro_cutoff"])
        assert pp1.id==initial[0] and pp1.digest==w.digest
        response=w.action_release()
    batch=Batch.with_user(packing).browse(response["res_id"])
    assert batch.ya_pp1_design_b_snapshot and batch.line_ids.mo_id.product_qty==250
    tick(clock["ro_cutoff"])
    assert pp1.state=="released" and pp1.batch_id==batch
    print("TIMER_FRESH_OPERATOR_REVIEW_AND_PP1_RELEASE_STATUS_PASS")
    with patch.object(gate,"utc_now",return_value=clock["so_cutoff"]-second):
        late=quote(249)
    tick(clock["so_cutoff"]-second)
    assert not entry("pp2")
    tick(clock["so_cutoff"])
    pp2=entry("pp2")
    assert len(pp2)==1 and pp2.state=="waiting" and pp2.digest
    with patch.object(gate,"utc_now",return_value=clock["so_cutoff"]):
        action=pp2.action_open_review()
        w2=Wizard.with_user(packing).browse(action["res_id"])
        assert w2.line_ids.qty_so==251 and w2.line_ids.qty_mo2==250
        reject(w2.action_release,UserError,"jeda MO2")
    tick(clock["pp2_earliest"])
    assert entry("pp2").id==pp2.id and pp2.state=="ready"
    assert not Final.search_count(domain)
    with patch.object(gate,"utc_now",return_value=clock["pp2_earliest"]):
        response=w2.action_release()
    final=Final.search(domain)
    assert len(final)==1 and final.line_ids.qty_mo2==250
    tick(clock["pp2_earliest"])
    assert pp2.state=="released" and pp2.batch_id==batch
    assert not (early|extra|late).mapped("picking_ids")
    assert not cron.active
    print("TIMER_PP2_PREPARE_AT_CUTOFF_DELAY_MANUAL_RELEASE_PASS")
    ids=(plan.id,ro.id,early.id,extra.id,late.id,batch.id,batch.line_ids.mo_id.id,
         final.id,final.line_ids.mo_id.id,pp1.id,pp2.id,w.id,w2.id,packing.id,outsider.id)
finally:
    env.cr.rollback()
    print("EXPLICIT_ROLLBACK_EXECUTED")
env.invalidate_all(flush=False)
for model,ident in zip((Plan,RO,Sale,Sale,Sale,Batch,env["mrp.production"],Final,
                       env["mrp.production"],Queue,Queue,Wizard,Wizard,Users,Users),ids):
    assert not model.sudo().browse(ident).exists(),model._name
assert not Queue.sudo().search_count(domain)
assert not env["ya.sale.capacity.reservation"].sudo().search_count(domain)
assert not cron.active
print("FASE2_CONSOLIDATION_HYBRID_TIMER_ROLLBACK_PASS")
print("CRON_INACTIVE_NO_BACKGROUND_EXECUTION_NO_COMMIT")
