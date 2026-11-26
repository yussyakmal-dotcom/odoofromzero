"""Native RO/Paket/SO inputs -> Design B forecast; rollback only."""
from datetime import timedelta
from pathlib import Path
from odoo import fields
from odoo.addons.ya_sale_production_capacity.models import pp1_native_sources as adapter

assert env.cr.dbname == adapter.DB
assert Path(adapter.__file__).resolve().is_relative_to(
    Path("/var/lib/ya-fase2-testing/source/addons"))
Plan = env["ya.production.planning"]
Line = env["ya.production.planning.line"]
RO = env["ya.store.ro"]
Package = env["ya.package.store.ro"]
Sale = env["sale.order"]
Ledger = env["ya.sale.capacity.reservation"].sudo()
Users = env["res.users"].sudo()
Product = env["product.product"]
Warehouse = env["stock.warehouse"]
Batch = env["ya.packing.batch"]
pkg = Product.search([("default_code","=","12114")])
component = Product.search([("default_code","=","11999")])
assert len(pkg)==len(component)==1
source = Line.search([("product_id","=",component.id),
    ("planning_id.state","=","published"),("planning_id.kitchen_code","=","PST"),
    ("max_capacity",">",0)],limit=1)
assert source and source._capacity_bom().product_qty==7
assert source.uom_id==component.uom_id
pkg_store = Warehouse.search([("code","=","T_BAN")])
ro_store = Warehouse.search([("code","=","T_KD")])
assert len(pkg_store)==len(ro_store)==1
company = pkg_store.company_id
assert company==ro_store.company_id
sample = Sale.sudo().search([("ya_is_capacity_so","=",True),
    ("partner_id","!=",False),("company_id","=",company.id)],limit=1)
assert sample
test_date = fields.Date.context_today(Plan)+timedelta(days=19)
domain = [("delivery_date","=",test_date),("slot","=","S1")]
for model in [Plan,RO,Package,Ledger,Batch]:
    assert not model.sudo().search_count(domain), model._name
assert not Sale.sudo().search_count([("ya_delivery_date","=",test_date),("ya_slot","=","S1")])
login = "__ya_pp1_sources_uat__@example.invalid"
assert not Users.search_count([("login","=",login)])
group_field = next(n for n in ("group_ids","groups_id") if n in Users._fields)
try:
    creator = Users.with_context(no_reset_password=True,tracking_disable=True,
        mail_create_nosubscribe=True,mail_notify_force_send=False).create({
        "name":login,"login":login,"company_id":company.id,
        "company_ids":[(6,0,[company.id])],
        group_field:[(6,0,[env.ref("ya_package_store_ro.group_ya_package_ro_creator").id])],
    })
    plan = Plan.create({"delivery_date":test_date,"slot":"S1",
        "kitchen_code":source.planning_id.kitchen_code,
        "workcenter_id":source.planning_id.workcenter_id.id})
    line = Line.create({"planning_id":plan.id,"product_id":component.id,
        "reference":source.reference,"max_capacity":14,
        "uom_id":source.uom_id.id,"bom_id":source._capacity_bom().id})
    plan.action_publish()
    ro = RO.create({"planning_id":plan.id,"store_warehouse_id":ro_store.id,
        "line_ids":[(0,0,{"product_id":component.id,"reference":component.default_code,
            "qty_requested":4,"uom_id":line.uom_id.id})]})
    ro.action_confirm()
    paket = Package.with_user(creator).sudo().create({
        "delivery_date":test_date,"slot":"S1","store_warehouse_id":pkg_store.id,
        "line_ids":[(0,0,{"product_id":pkg.id,"qty_requested":8})]})
    paket.action_confirm()
    assert ro.state==paket.state=="confirmed"

    def read():
        facts=adapter.read_pp1_sources(env,test_date,"S1",company)
        rows=[r for r in facts["sku_forecasts"] if r["product_id"]==component.id]
        assert len(rows)==1
        return facts,rows[0]

    facts,before=read()
    assert before["original_ro_store_qty"]==4
    assert before["original_ro_package_qty"]==8
    assert before["confirmed_so_qty"]==0
    assert before["forecast_mo1_qty"]==14
    assert before["forecast_unallocated_surplus"]==2
    assert len(facts["ordinary_ro_rows"])==1
    assert sum(r["qty"] for r in facts["ro_package_kitchen_rows"])==8
    assert facts["ordinary_ro_rows"][0]["ro_id"]==ro.id
    assert facts["ro_package_kitchen_rows"][0]["ro_id"]==paket.id
    print("NATIVE_RO_AND_PAKET_SOURCE_FORECAST_PASS",before)

    def quote(qty):
        return Sale.with_context(default_ya_is_capacity_so=True,tracking_disable=True,
            mail_create_nosubscribe=True,mail_notify_force_send=False).create({
            "partner_id":sample.partner_id.id,"company_id":company.id,
            "warehouse_id":sample.warehouse_id.id,"pricelist_id":sample.pricelist_id.id,
            "ya_delivery_date":test_date,"ya_slot":"S1",
            "order_line":[(0,0,{"product_id":component.id,"name":component.display_name,
                "product_uom_qty":qty,"product_uom_id":component.uom_id.id,
                "price_unit":component.lst_price})]})
    so=quote(5)
    draft=quote(1)
    assert so.state in ("draft","sent")
    assert read()[1]==before
    print("DRAFT_SO_NOT_COUNTED_PASS")
    env["ya.sale.capacity.confirm.wizard"].with_context(
        tracking_disable=True,mail_notify_force_send=False).create({
        "order_id":so.id,"delivery_date":test_date,"slot":"S1"
    }).action_check_and_confirm()
    assert so.state in ("sale","done") and not so.picking_ids
    facts,after=read()
    assert after["confirmed_so_qty"]==5
    assert after["forecast_mo1_qty"]==14
    assert after["forecast_so_covered"]==5
    assert after["forecast_ro_package_covered"]==8
    assert after["forecast_ro_store_covered"]==1
    assert after["forecast_ro_store_shortage"]==3
    assert after["forecast_unallocated_surplus"]==0
    assert len(facts["so_ledger_rows"])==1
    assert facts["so_ledger_rows"][0]["order_id"]==so.id
    assert facts["so_ledger_rows"][0]["qty"]==5
    assert read()[0]==facts
    print("NATIVE_EARLY_SO_FIRST_DISPLACEMENT_PASS",after)
    assert ro.line_ids.qty_requested==4 and paket.line_ids.qty_requested==8
    assert draft.state in ("draft","sent")
    assert not Batch.search_count(domain)
    print("ORIGINAL_DEMAND_UNCHANGED_NO_PP1_OR_DO_PASS")
    ids=(plan.id,ro.id,paket.id,so.id,draft.id,creator.id)
finally:
    env.cr.rollback()
    print("EXPLICIT_ROLLBACK_EXECUTED")
env.invalidate_all()
for model, ident in zip((Plan,RO,Package.sudo(),Sale,Sale,Users),ids):
    assert not model.browse(ident).exists(), model._name
assert not Ledger.search_count(domain)
assert not Batch.search_count(domain)
print("FIXTURE_ROLLBACK_VERIFIED_PASS")
print("FASE2_PP1_NATIVE_SOURCES_ROLLBACK_PASS")
print("FORECAST_ONLY_NO_MO1_RELEASE_NO_FINAL_ALLOCATION")
