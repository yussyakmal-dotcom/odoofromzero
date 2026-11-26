"""RO correction boundary and native Confirm entrypoint QA; clone rollback."""
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
    packing=Users.with_context(no_reset_password=True,tracking_disable=True,
        mail_create_nosubscribe=True,mail_notify_force_send=False).create({
        "name":"RO correction QA","login":"__ya_ro_correction_smoke__@example.invalid",
        "company_id":company.id,"company_ids":[(6,0,[company.id])],
        gf:[(6,0,[env.ref("ya_store_ro.group_ya_packing_admin").id])]})
    # Both real native Confirm actions still work; direct status writes
    # cannot replace them, even using the old boolean context.
    with patch.object(gate,"utc_now",return_value=s["ro_cutoff"]-second):
        rejected(lambda:ro.write({"state":"confirmed"}),"Gunakan tombol Confirm")
        rejected(lambda:paket.with_context(ya_package_confirm=True).write(
            {"state":"confirmed"}),"Gunakan tombol Confirm")
        assert ro.state==paket.state=="draft"
        ro.action_confirm()
        paket.action_confirm()
        assert ro.state==paket.state=="confirmed"
        assert ro.confirmed_by and paket.confirmed_by==creator
    print("RO_NATIVE_CONFIRM_ONLY_NO_DIRECT_STATUS_BYPASS_PASS")
    ordinary_line=ro.line_ids.with_user(packing)
    package_line=paket.line_ids.with_user(packing)
    assert not ordinary_line.env.su and not package_line.env.su
    OW=env["ya.packing.qty.correction"].with_user(packing)
    PW=env["ya.package.ro.qty.correction"].with_user(packing)
    def correction(W,parent,line,qty):
        return W.create({"ro_id":parent.id,"line_id":line.id,"new_qty":qty,
                         "reason":"QA: koreksi sebelum cutoff"})
    ow=correction(OW,ro,ordinary_line,5)
    pw=correction(PW,paket,package_line,2)
    with patch.object(gate,"utc_now",return_value=s["ro_cutoff"]-second):
        ow.action_apply()
        pw.action_apply()
    assert ordinary_line.qty_requested==5 and package_line.qty_requested==2
    oa=ro.correction_ids
    pa=paket.correction_ids
    assert len(oa)==len(pa)==1
    assert (oa.qty_before,oa.qty_after,oa.changed_by.id)==(4,5,packing.id)
    assert (pa.qty_before,pa.qty_after,pa.changed_by.id)==(1,2,packing.id)
    assert not Batch.search_count(domain)
    print("RO_AND_PAKET_BEFORE_CUTOFF_EXISTING_CORRECTION_AUDIT_PASS")
    # Prepare before deadline, attempt at exact deadline, even though
    # no PP1 batch exists. Test wizard and direct line write with reason.
    ow2=correction(OW,ro,ordinary_line,6)
    pw2=correction(PW,paket,package_line,3)
    with patch.object(gate,"utc_now",return_value=s["ro_cutoff"]):
        rejected(ow2.action_apply,"Cutoff RO")
        rejected(pw2.action_apply,"Cutoff RO")
        rejected(lambda:ordinary_line.with_context(packing_qty_correction_reason="QA").write(
            {"qty_requested":6}),"Cutoff RO")
        rejected(lambda:package_line.with_context(ya_package_packing_qty_correction_reason="QA").write(
            {"qty_requested":3}),"Cutoff RO")
    assert ordinary_line.qty_requested==5 and package_line.qty_requested==2
    assert ro.correction_ids==oa and paket.correction_ids==pa
    assert not Batch.search_count(domain)
    assert not env["ya.sale.capacity.reservation"].sudo().search_count(domain)
    print("RO_AND_PAKET_EXACT_CUTOFF_CORRECTION_BLOCKED_WITHOUT_BATCH_PASS")
    ids=(plan.id,ro.id,paket.id,creator.id,packing.id,oa.id,pa.id)
    ordinary_wizard_ids=(ow|ow2).ids
    package_wizard_ids=(pw|pw2).ids
finally:
    env.cr.rollback()
    print("EXPLICIT_ROLLBACK_EXECUTED")
env.invalidate_all(flush=False)
for model,ident in zip((Plan,RO,Package,Users,Users,env["ya.store.ro.qty.audit"],
                       env["ya.package.ro.qty.audit"]),ids):
    assert not model.sudo().browse(ident).exists(),model._name
assert not OW.sudo().browse(ordinary_wizard_ids).exists()
assert not PW.sudo().browse(package_wizard_ids).exists()
print("FASE2_RO_CORRECTION_CUTOFF_ROLLBACK_PASS")
print("NO_COMMIT_NO_FASE1_RUNTIME_CHANGE")
