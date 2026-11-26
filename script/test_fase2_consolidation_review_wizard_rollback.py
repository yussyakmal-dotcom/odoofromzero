"""Clone-only focused operator wizard smoke test; no actual release by wizard."""
from datetime import timedelta
from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.addons.ya_sale_production_capacity.models.pp1_native_sources import DB
from odoo.addons.ya_sale_production_capacity.models.pp1_review_contract import read_locked_review

assert env.cr.dbname==DB
module=env["ir.module.module"].search([("name","=","ya_sale_production_capacity")])
assert module.installed_version=="19.0.1.6.0",module.installed_version
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
try:
    packing=user("__ya_review_packing_smoke__@example.invalid","ya_store_ro.group_ya_packing_admin")
    outsider=user("__ya_review_stock_smoke__@example.invalid","stock.group_stock_user")
    W=Wizard.with_user(packing)
    assert not W.env.su and W.env.user.has_group("ya_store_ro.group_ya_packing_admin")
    assert not outsider.has_group("ya_store_ro.group_ya_packing_admin")
    view=env.ref("ya_sale_production_capacity.view_ya_consolidation_review_wizard")
    menu=env.ref("ya_sale_production_capacity.menu_ya_consolidation_review_wizard")
    action=env.ref("ya_sale_production_capacity.action_ya_consolidation_review_wizard")
    assert menu.parent_id==env.ref("ya_workflow_navigation.menu_ya_before_production")
    assert menu.action==action and action.res_model==Wizard._name
    arch=W.get_view(view_id=view.id,view_type="form")["arch"]
    assert "action_review" in arch and "qty_mo2" in arch
    print("FASE2_REVIEW_MENU_ACTION_VIEW_PACKING_ADMIN_PASS")
    vals={"stage":"pp1","delivery_date":day,"slot":slot}
    reject(lambda:Wizard.with_user(outsider).create(vals),AccessError)
    w=W.create(vals)
    w2=W.create(dict(vals,stage="pp2"))
    reject(w2.action_review,UserError,"PP2 membutuhkan PP1")
    assert not Batch.search_count(domain)
    print("FASE2_REVIEW_ACL_AND_PP2_BEFORE_PP1_BLOCKED_PASS")
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
    response=w.action_review()
    assert response["res_id"]==w.id and response["res_model"]==Wizard._name
    assert len(w.line_ids)==1
    row=w.line_ids
    assert (row.product_id.id,row.qty_so,row.qty_ro,row.qty_ro_paket,row.qty_mo1,row.qty_mo2,
            row.bom_output,row.published_max,row.surplus)==(product.id,1,4,0,250,0,250,500,245)
    assert w.digest==read_locked_review(W.env,day,slot,company)["digest"]
    assert not Batch.search_count(domain) and not early.picking_ids
    digest=w.digest
    w.action_review()
    assert w.digest==digest and len(w.line_ids)==1
    print("FASE2_PP1_REVIEW_REFRESH_NO_RELEASE_PASS")
    # Private fixture release only; the wizard itself cannot release.
    # This reuses the already passed PP1 core to provide a real PP2 source.
    batch=Batch.with_user(packing).sudo()._ya_create_pp1_design_b_release_core(day,slot,digest)
    frozen=batch._ya_pp1_frozen_facts()
    assert batch.state=="production_ok" and len(batch.line_ids)==1
    late=quote(250)
    w2.action_review()
    assert len(w2.line_ids)==1
    row=w2.line_ids
    assert (row.qty_so,row.qty_ro,row.qty_mo1,row.qty_mo2,row.surplus)==(251,4,250,250,245)
    assert row.shortage_ro==0 and row.shortage_ro_paket==0
    assert w2.digest==batch._ya_read_pp2_design_b_review()["digest"]
    assert not Final.search_count(domain)
    assert batch._ya_pp1_frozen_facts()==frozen and len(batch.line_ids.mapped("mo_id"))==1
    assert ro.line_ids.qty_requested==4 and not (early|late).mapped("picking_ids")
    print("FASE2_PP2_REVIEW_INCREMENT_ONLY_NO_RELEASE_PASS")
    # Form onchange is checked on an in-memory record, not an actual web session.
    transient=W.new({"stage":"pp1","delivery_date":day,"slot":"S2",
                    "digest":digest,"reviewed_identity":"old"})
    transient._onchange_review_identity()
    assert not transient.digest and not transient.reviewed_identity and not transient.line_ids
    print("FASE2_REVIEW_SELECTOR_ONCHANGE_CLEARS_OLD_RESULT_PASS")
    fixture_ids=(plan.id,ro.id,early.id,late.id,batch.id,batch.line_ids.mo_id.id,w.id,w2.id,packing.id,outsider.id)
finally:
    env.cr.rollback()
    print("EXPLICIT_ROLLBACK_EXECUTED")
env.invalidate_all(flush=False)
for model,ident in zip((Plan,RO,Sale,Sale,Batch,env["mrp.production"],Wizard,Wizard,Users,Users),fixture_ids):
    assert not model.sudo().browse(ident).exists(),model._name
print("FASE2_CONSOLIDATION_REVIEW_WIZARD_ROLLBACK_PASS")
print("GUI_MODEL_VIEW_ACL_SMOKE_ONLY_NO_BROWSER_NO_OPERATIONAL_RELEASE_NO_COMMIT")
