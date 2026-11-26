"""Clone-only targeted SO Paket Confirm provenance test. No stock movement."""
from datetime import timedelta
from copy import deepcopy
from pathlib import Path
from odoo import fields
from odoo.exceptions import UserError
from odoo.addons.ya_sale_production_capacity.models import so_demand_snapshot as snapshot

assert env.cr.dbname=="erp-yussyakmal-mrp-test-RO_SO"
assert Path(snapshot.__file__).resolve().is_relative_to(Path("/var/lib/ya-fase2-testing/source/addons"))
Sale=env["sale.order"]
Plan=env["ya.production.planning"]
Line=env["ya.production.planning.line"]
Product=env["product.product"]
Ledger=env["ya.sale.capacity.reservation"].sudo()
assert "ya_confirmed_demand_snapshot" in Sale._fields
pkg=Product.search([("default_code","=","12114")])
component=Product.search([("default_code","=","11999")])
assert len(pkg)==len(component)==1
source=Line.search([("product_id","=",component.id),
    ("planning_id.state","=","published"),("planning_id.kitchen_code","=","PST"),
    ("max_capacity",">",0)],limit=1)
assert source and source._capacity_bom().product_qty==7
company=source._capacity_bom().picking_type_id.company_id
sample=Sale.sudo().search([("ya_is_capacity_so","=",True),("company_id","=",company.id)],limit=1)
assert sample
for days in range(20,75):
    date=fields.Date.context_today(Plan)+timedelta(days=days)
    domain=[("delivery_date","=",date),("slot","=","S1")]
    if (not any(env[model].sudo().search_count(domain) for model in
        ("ya.production.planning","ya.store.ro","ya.package.store.ro","ya.packing.batch","ya.sale.capacity.reservation"))
        and not Sale.sudo().search_count([("ya_delivery_date","=",date),("ya_slot","=","S1")])):
        break
else:
    raise AssertionError("No unused future date/slot")

def reject(fn,expected):
    try:
        with env.cr.savepoint():
            fn()
    except UserError as exc:
        assert expected in str(exc),(expected,str(exc))
    else:
        raise AssertionError("Expected rejection: "+expected)

try:
    plan=Plan.create(dict(delivery_date=date,slot="S1",
        kitchen_code=source.planning_id.kitchen_code,
        workcenter_id=source.planning_id.workcenter_id.id))
    line=Line.create(dict(planning_id=plan.id,product_id=component.id,
        reference=source.reference,max_capacity=14,uom_id=source.uom_id.id,
        bom_id=source._capacity_bom().id))
    plan.action_publish()
    order=Sale.with_company(company).with_context(default_ya_is_capacity_so=True,
        tracking_disable=True,mail_create_nosubscribe=True,mail_notify_force_send=False).create({
        "partner_id":sample.partner_id.id,"company_id":company.id,
        "warehouse_id":sample.warehouse_id.id,"pricelist_id":sample.pricelist_id.id,
        "order_line":[(0,0,dict(product_id=p.id,name=p.display_name,
            product_uom_qty=q,product_uom_id=p.uom_id.id,price_unit=p.lst_price))
            for p,q in [(component,1),(pkg,2)]]})
    assert not order.ya_confirmed_demand_snapshot
    preview=order._ya_prepare_capacity_confirm_readonly(date,"S1")
    assert len(preview["source_rows"])==2
    assert not Ledger.search_count([("order_id","=",order.id)])
    reject(lambda:order.write({"ya_confirmed_demand_snapshot":{"fake":True}}),"immutable")
    action=env["ya.sale.capacity.confirm.wizard"].with_context(
        tracking_disable=True,mail_notify_force_send=False).create({
        "order_id":order.id,"delivery_date":date,"slot":"S1"}).action_check_and_confirm()
    assert action["res_id"]==order.id and order.state in ("sale","done")
    assert not order.picking_ids
    frozen=order._ya_verified_confirmed_demand(preview["source_rows"])
    assert frozen["source_rows"]==preview["source_rows"]
    assert len(frozen["ledger_rows"])==1 and frozen["ledger_rows"][0]["qty_required"]==3
    assert frozen["ledger_rows"][0]["planning_line_id"]==line.id
    package=next(r for r in frozen["source_rows"] if r["kind"]=="SO_PAKET")
    assert package["product_id"]==pkg.id and package["qty"]==2 and package["bom_id"]==1405
    assert {Product.browse(p["product_id"]).default_code:(p["source_kind"],p["qty"])
        for p in package["components"]}=={"11999":("KITCHEN",2),"12014":("PCK",2.0),"12019":("PCK",2.0)}
    print("NATIVE_SO_PAKET_FULL_CONFIRMATION_SNAPSHOT_AND_LEDGER_PASS",package)
    reject(lambda:order.write({"ya_confirmed_demand_snapshot":False}),"immutable")
    changed=deepcopy(frozen["source_rows"])
    next(r for r in changed if r["kind"]=="SO_PAKET")["components"][-1]["qty"]+=1
    reject(lambda:order._ya_verified_confirmed_demand(changed),"Paket BoM changed")
    assert order._ya_verified_confirmed_demand()==frozen
    print("CONFIRMED_PAKET_SNAPSHOT_TAMPER_AND_COMPONENT_DRIFT_BLOCKED_PASS")
    assert not env["stock.move"].sudo().search_count([("sale_line_id","in",order.order_line.ids)])
    print("SO_CONFIRM_NO_PREMATURE_STOCK_MOVE_OR_DO_PASS")
    oid=order.id
    pid=plan.id
    lid=line.id
    ledger_ids=Ledger.search([("order_id","=",oid)]).ids
finally:
    env.cr.rollback()
    print("EXPLICIT_ROLLBACK_EXECUTED")
env.invalidate_all(flush=False)
assert not Sale.browse(oid).exists() and not Plan.browse(pid).exists()
assert not Line.browse(lid).exists() and not Ledger.browse(ledger_ids).exists()
print("FASE2_SO_PAKET_CONFIRMATION_SNAPSHOT_ROLLBACK_PASS")
print("NO_OPERATIONAL_RELEASE_NO_COMMIT")
