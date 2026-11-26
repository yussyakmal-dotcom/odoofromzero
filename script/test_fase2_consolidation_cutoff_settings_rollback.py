"""Clone-only settings smoke QA. Hypothetical changed times are rollback fixtures."""
from datetime import timedelta
from unittest.mock import patch
from odoo import fields
from odoo.exceptions import UserError, AccessError
from odoo.addons.ya_sale_production_capacity.models import consolidation_cutoff_gate as gate
from odoo.addons.ya_sale_production_capacity.models.consolidation_cutoff_rules import DEFAULT_POLICY, schedule

assert env.cr.dbname==gate.DB
assert env["ir.module.module"].search([("name","=","ya_sale_production_capacity")]).installed_version=="19.0.1.7.0"
Settings=env["ya.consolidation.cutoff.settings"]
assert not Settings.sudo().search_count([]),"Expected fresh Settings history; do not overwrite real versions"
assert env.user.has_group("base.group_system")
today=fields.Date.context_today(Settings)
last=env["ya.packing.batch"].sudo().search([],order="delivery_date desc",limit=1)
day=max(today+timedelta(days=30),last.delivery_date+timedelta(days=3) if last else today)
older=day-timedelta(days=1)
old=schedule(day,"S1",DEFAULT_POLICY)
before_old=schedule(older,"S1",DEFAULT_POLICY)
vals=dict(effective_date=day,reason="ROLLBACK QA ONLY",ro_days_before=2,ro_time="10:00",
          s1_days_before=1,s1_time="16:00",s2_enabled=False,s3_enabled=False,mo2_delay_minutes=45)
def reject(fn,kind,fragment=None):
    try:
        with env.cr.savepoint():
            fn()
    except kind as exc:
        assert not fragment or fragment in str(exc),str(exc)
    else:
        raise AssertionError("Unexpected acceptance")
Users=env["res.users"].sudo()
gf=next(n for n in ("group_ids","groups_id") if n in Users._fields)
def user(login,groups):
    assert not Users.search_count([("login","=",login)])
    return Users.with_context(no_reset_password=True,tracking_disable=True,
        mail_create_nosubscribe=True,mail_notify_force_send=False).create({
        "name":login,"login":login,"company_id":env.company.id,
        "company_ids":[(6,0,[env.company.id])],
        gf:[(6,0,[env.ref(g).id for g in groups])]})
try:
    admin=user("__ya_cutoff_settings_admin__@example.invalid",["base.group_system","mrp.group_mrp_manager"])
    operator=user("__ya_cutoff_settings_operator__@example.invalid",["ya_store_ro.group_ya_packing_admin"])
    S=Settings.with_user(admin)
    assert not S.env.su and admin.has_group("base.group_system")
    reject(lambda:Settings.with_user(operator).create(vals),(AccessError,UserError))
    menu=env.ref("ya_sale_production_capacity.menu_ya_cutoff_settings")
    assert menu.parent_id==env.ref("ya_workflow_navigation.menu_ya_before_production")
    view=env.ref("ya_sale_production_capacity.view_ya_cutoff_settings_form")
    assert "ro_time" in S.get_view(view_id=view.id,view_type="form")["arch"]
    print("CUTOFF_SETTINGS_ADMIN_ACL_MENU_VIEW_PASS")
    assert Settings._policy_for_delivery(day)==(DEFAULT_POLICY,False)
    with patch.object(gate,"utc_now",return_value=old["ro_cutoff"]):
        reject(lambda:S.create(vals),UserError,"Tanggal berlaku terlalu dekat")
    with patch.object(gate,"utc_now",return_value=old["ro_cutoff"]-timedelta(seconds=1)):
        reject(lambda:S.create(dict(vals,ro_time="25:00")),UserError,"HH:MM")
        reject(lambda:S.create(dict(vals,s2_enabled=True,s2_time=False)),UserError,"HH:MM")
        version=S.create(vals)
    assert version.create_uid==admin and version.create_date and version.reason==vals["reason"]
    assert Settings._policy_for_delivery(older)==(DEFAULT_POLICY,False)
    policy,vid=Settings._policy_for_delivery(day)
    assert vid==version.id and policy["ro_minute"]==600 and policy["so"]["S1"]["minute"]==960
    assert policy["mo2_delay_minutes"]==45 and policy["so"]["S2"] is None and policy["so"]["S3"] is None
    assert Settings._policy_for_delivery(day+timedelta(days=1))==(policy,vid)
    with patch.object(gate,"utc_now",return_value=before_old["ro_cutoff"]):
        state=gate.current_clock(Settings.with_user(operator).env,older,"S1")
        assert state["ro_closed"] and not state["cutoff_settings_version_id"]
    with patch.object(gate,"utc_now",return_value=old["ro_cutoff"]):
        state=gate.current_clock(Settings.with_user(operator).env,day,"S1")
        assert state["ro_admission_allowed"] and state["cutoff_settings_version_id"]==vid
    new=schedule(day,"S1",policy)
    with patch.object(gate,"utc_now",return_value=new["ro_cutoff"]):
        assert not gate.current_clock(Settings.with_user(operator).env,day,"S1")["ro_admission_allowed"]
    with patch.object(gate,"utc_now",return_value=new["so_cutoff"]):
        state=gate.current_clock(Settings.with_user(operator).env,day,"S1")
        assert not state["so_admission_allowed"] and not state["pp2_clock_ready"]
    with patch.object(gate,"utc_now",return_value=new["pp2_earliest"]):
        assert gate.current_clock(Settings.with_user(operator).env,day,"S1")["pp2_clock_ready"]
        assert not gate.current_clock(Settings.with_user(operator).env,day,"S2")["pp2_clock_ready"]
        assert not gate.current_clock(Settings.with_user(operator).env,day,"S3")["pp2_clock_ready"]
    print("CUTOFF_SETTINGS_EFFECTIVE_DATE_NO_REOPEN_AND_NATIVE_CLOCK_PASS")
    reject(lambda:version.sudo().write({"ro_time":"11:00"}),UserError,"tidak dapat diubah")
    reject(lambda:version.sudo().unlink(),UserError,"tidak boleh dihapus")
    reject(lambda:S.create(dict(vals,effective_date=older)),UserError,"setelah versi terakhir")
    print("CUTOFF_SETTINGS_IMMUTABLE_HISTORY_ACTOR_REASON_PASS")
    ids=(version.id,admin.id,operator.id)
finally:
    env.cr.rollback()
    print("EXPLICIT_ROLLBACK_EXECUTED")
env.invalidate_all(flush=False)
assert not Settings.sudo().browse(ids[0]).exists()
assert not Users.browse(list(ids[1:])).exists()
assert not Settings.sudo().search_count([])
print("FASE2_CONSOLIDATION_CUTOFF_SETTINGS_ROLLBACK_PASS")
print("NO_REAL_POLICY_CHANGE_NO_TIMER_NO_RELEASE")
