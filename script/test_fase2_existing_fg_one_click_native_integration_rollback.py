"""Actual one-click native FG handoff; existing MR1 and grouped MR2 fixtures."""
from odoo.addons.ya_finished_packing_transfer.models import finished_packing as fg_base
from odoo.addons.ya_sale_production_capacity.models.final_packing_supply import read_final_packing_kitchen_supply
from odoo.addons.ya_sale_production_capacity.models.cdc_commitment_diagnostic import read_cdc_commitments
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
assert Path(fg_base.__file__).resolve().is_relative_to(Path("/var/lib/ya-fase2-testing/source/addons/ya_finished_packing_transfer")),fg_base.__file__
assert Path(mr_base.__file__).resolve().is_relative_to(Path("/var/lib/ya-fase2-testing/source/addons/ya_material_requirement")),mr_base.__file__
module=env["ir.module.module"].search([("name","=","ya_sale_production_capacity")])
assert module.installed_version=="19.0.1.10.0",module.installed_version
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
second_source=Line.browse(3151)
second_product=second_source.product_id
second_bom=second_source._capacity_bom()
assert second_product!=product and second_bom.picking_type_id.warehouse_id==source._capacity_bom().picking_type_id.warehouse_id
second_output=int(second_bom.product_uom_id._compute_quantity(second_bom.product_qty,second_product.uom_id,round=False))
assert second_output>0 and second_product.uom_id==second_source.uom_id
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
def quote(qty,product=product):
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
raw_ids=(source._capacity_bom().bom_line_ids|second_bom.bom_line_ids).mapped("product_id").ids
pck=env["stock.warehouse"].search([("code","=","PCK"),("company_id","=",company.id)])
assert len(pck)==1
raw_ids=sorted(set(raw_ids+[product.id,second_product.id]))
roots=(cdc.lot_stock_id|kitchen.lot_stock_id|pck.lot_stock_id).ids
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
    Line.create({"planning_id":plan.id,"product_id":second_product.id,
        "reference":second_source.reference,"max_capacity":second_output,
        "uom_id":second_source.uom_id.id,"bom_id":second_bom.id})
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
    assert set(expected)==set(source._capacity_bom().bom_line_ids.mapped("product_id").ids)
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
    reject(batch.action_ya_fg_move_to_packing,UserError,"Finalisasi PP2")
    # Later PP2 must not cause the already issued MR1 to be regenerated.
    with patch.object(gate,"utc_now",return_value=clock["so_cutoff"]-second):
        late=quote(250)
        late2=quote(1,second_product)
    w2=W.create({"stage":"pp2","delivery_date":day,"slot":slot})
    with patch.object(gate,"utc_now",return_value=clock["pp2_earliest"]):
        w2.action_review()
        w2.action_release()
    final=Final.search(domain)
    assert len(final)==1 and len(final.line_ids)==2
    assert {l.product_id.id:l.qty_mo2 for l in final.line_ids}=={product.id:250,second_product.id:second_output}
    lines=final.line_ids.with_env(batch.env)
    need=totals(lines.mapped("mo_id.move_raw_ids"))
    assert need and len(lines.mapped("mo_id.picking_type_id.warehouse_id"))==1
    assert not Picking.search_count([("ya_mr2_finalization_id","=",final.id)])
    reject(lambda:batch.with_user(packing).action_mr2_generate_native_transfers(),UserError,"Inventory Administrator")
    before2={pid:(physical(pid,cdc.lot_stock_id),physical(pid,kitchen.lot_stock_id)) for pid in need}
    action=batch.action_mr2_generate_native_transfers()
    mr2=Picking.with_user(inventory).search([("ya_mr2_finalization_id","=",final.id)])
    assert len(mr2)==1 and mr2.ya_mr2_kitchen_id==kitchen
    assert not mr2.ya_mr_batch_id and not mr2.ya_mo2_material_release_line_id
    assert mr2.ya_mr2_issued_demand["line_ids"]==sorted(lines.ids)
    assert totals(mr2.move_ids)==need and len(mr2.move_ids)==len(need)
    assert all(l._ya_mr2_pickings()==mr2 for l in lines)
    assert before2=={pid:(physical(pid,cdc.lot_stock_id),physical(pid,kitchen.lot_stock_id)) for pid in need}
    assert action["res_model"]=="stock.picking"
    batch.action_mr2_generate_native_transfers()
    assert Picking.search_count([("ya_mr2_finalization_id","=",final.id)])==1
    assert all(l._ya_create_mo2_cdc_transfer()==mr2 for l in lines)
    print("MR2_TWO_MO2_ONE_KITCHEN_ONE_NATIVE_PICKING_FULL_DEMAND_PASS",mr2.id,sorted(lines.ids),len(need))
    diagnostic=read_cdc_commitments(batch.env,company,list(need))
    rows=[r for r in diagnostic["outbound_rows"] if r["picking_id"]==mr2.id]
    assert len(rows)==len(need) and all(r["kind"]=="MR2" for r in rows)
    assert {r["product_id"]:r["qty"] for r in rows}==need
    print("MR2_CDC_DIAGNOSTIC_COUNTS_SHARED_PICKING_ONCE_PASS")
    def zero_qty():
        mr2.move_ids[:1].write({"quantity":0})
        mr2.button_validate()
    reject(zero_qty,UserError,"Qty harus sama")
    reject(lambda:mr2.write({"ya_mr2_issued_demand":{}}),UserError,"immutable")
    mr2.action_confirm()
    mr2.action_assign()
    missing=[(m.product_id.default_code,m.quantity,m.product_uom_qty) for m in mr2.move_ids
             if abs(m.quantity-m.product_uom_qty)>1e-7 or m.state!="assigned"]
    if missing:
        print("MR2_NATIVE_CDC_FIXTURE_SHORTAGE",missing)
        reject(mr2.button_validate,UserError)
        raise AssertionError("Fixture CDC stock insufficient for full MR2 Validate; no stock seeded")
    mr2.move_ids.write({"picked":True})
    mr2.move_ids.mapped("move_line_ids").write({"picked":True})
    result=mr2.with_context(skip_sms=True,mail_notify_force_send=False).button_validate()
    assert mr2.state=="done" and all(m.state=="done" for m in mr2.move_ids),result
    assert not Picking.sudo().search_count([("backorder_id","=",mr2.id)])
    for pid,qty in need.items():
        assert abs(physical(pid,cdc.lot_stock_id)-before2[pid][0]+qty)<1e-7
        assert abs(physical(pid,kitchen.lot_stock_id)-before2[pid][1]-qty)<1e-7
    print("MR2_FULL_NATIVE_VALIDATE_PHYSICAL_DELTA_NO_BACKORDER_PASS")
    batch.action_mr_generate_native_transfers()
    assert batch.mr_native_transfer_ids.ids==[p_id] and picking.move_ids.ids==move_ids
    assert totals(picking.move_ids)==expected and picking.state=="done"
    assert batch._ya_pp1_frozen_facts()==frozen and ro.line_ids.qty_requested==4
    assert not (early|late|late2).mapped("picking_ids")
    assert not batch.ya_fg_transfer_ids and not batch.ya_store_delivery_ids
    print("MR1_UNCHANGED_MR2_SHARED_SOURCE_LINK_NO_PREMATURE_FG_DO_PASS")
    # Reject incomplete manufacturing before producing any handoff document.
    reject(batch.action_ya_fg_move_to_packing,UserError,"Semua MO1/MO2 harus Done")
    assert not batch.ya_fg_transfer_ids and not lines.mapped("ya_mo2_fg_picking_ids")
    mos=mo|lines.mapped("mo_id")
    assert len(mos)==3
    for native in mos:
        native.action_assign()
        for m in native.move_raw_ids:
            assert m.state=="assigned" and abs(m.quantity-m.product_uom_qty)<1e-7, (
                "Native MO material reservation incomplete",native.name,m.product_id.default_code,m.state,m.quantity,m.product_uom_qty)
        material=totals(native.move_raw_ids)
        initial={pid:physical(pid,kitchen.lot_stock_id) for pid in material}
        fg_pid=native.product_id.id
        initial_fg=physical(fg_pid,kitchen.lot_stock_id)
        native.write({"qty_producing":native.product_qty})
        native._set_qty_producing()
        assert not native._get_consumption_issues()
        response=native.with_context(skip_backorder=True,skip_redirection=True).button_mark_done()
        assert native.state=="done" and not native.workorder_ids,response
        assert all(m.state=="done" for m in native.move_raw_ids)
        for pid,qty in material.items():
            assert abs(physical(pid,kitchen.lot_stock_id)-initial[pid]+qty)<1e-7
        assert abs(physical(fg_pid,kitchen.lot_stock_id)-initial_fg-native.product_qty)<1e-7
    print("MO1_AND_TWO_MO2_NATIVE_DONE_ACTUAL_STOCK_PASS")
    pp2=final._ya_pp2_frozen_facts()
    expected_fg={product.id:500,second_product.id:second_output}
    before_fg={pid:(physical(pid,kitchen.lot_stock_id),physical(pid,pck.lot_stock_id)) for pid in expected_fg}
    action=batch.action_ya_fg_move_to_packing()
    fg1=batch.ya_fg_transfer_ids
    fg2=lines.mapped("ya_mo2_fg_picking_ids")
    fg=fg1|fg2
    assert len(fg1)==1 and len(fg2)==2 and len(fg)==3
    assert fg1.ya_fg_kitchen_id==kitchen
    assert all(p.state=="done" and p.location_id==kitchen.lot_stock_id and
               p.location_dest_id==pck.lot_stock_id for p in fg)
    assert totals(fg1.move_ids)=={product.id:250}
    assert totals(fg2.move_ids)=={product.id:250,second_product.id:second_output}
    assert action["res_model"]=="stock.picking" and set(action["domain"][0][2])==set(fg.ids)
    for pid,qty in expected_fg.items():
        assert abs(physical(pid,kitchen.lot_stock_id)-before_fg[pid][0]+qty)<1e-7
        assert abs(physical(pid,pck.lot_stock_id)-before_fg[pid][1]-qty)<1e-7
    supply=read_final_packing_kitchen_supply(batch)
    assert {r["product_id"]:r["mo1_mo2_received_qty"] for r in supply["rows"]}==expected_fg
    assert len(supply["receipt_proofs"])==3
    print("ACTUAL_FASE1_MO1_AND_NATIVE_MO2_ONE_CLICK_PCK_SUPPLY_PASS",expected_fg)
    fg_ids=fg.ids
    fg_move_ids=fg.mapped("move_ids").ids
    after_fg={pid:(physical(pid,kitchen.lot_stock_id),physical(pid,pck.lot_stock_id)) for pid in expected_fg}
    repeated=batch.action_ya_fg_move_to_packing()
    assert set(repeated["domain"][0][2])==set(fg_ids)
    assert set((batch.ya_fg_transfer_ids|lines.mapped("ya_mo2_fg_picking_ids")).ids)==set(fg_ids)
    assert after_fg=={pid:(physical(pid,kitchen.lot_stock_id),physical(pid,pck.lot_stock_id)) for pid in expected_fg}
    assert batch._ya_pp1_frozen_facts()==frozen and final._ya_pp2_frozen_facts()==pp2
    assert not batch.ya_store_delivery_ids and not batch.ya_package_assembly_mo_ids and not batch.allocation_ids
    assert not (early|late|late2).mapped("picking_ids")
    print("FG_REPEAT_NO_DUPLICATE_NO_PREMATURE_ALLOCATION_OR_DO_PASS")
    ids=(plan.id,ro.id,early.id,late.id,late2.id,batch.id,mo.id,final.id,
         p_id,mr2.id,w.id,w2.id,packing.id,inventory.id)
    mo2_ids=lines.mapped("mo_id").ids
    mr2_moves=mr2.move_ids.ids
finally:
    env.cr.rollback()
    print("EXPLICIT_ROLLBACK_EXECUTED")
env.invalidate_all(flush=False)
for model,ident in zip((Plan,RO,Sale,Sale,Sale,Batch,env["mrp.production"],Final,
    Picking,Picking,Wizard,Wizard,Users,Users),ids):
    assert not model.sudo().browse(ident).exists(),model._name
assert not env["mrp.production"].sudo().browse(mo2_ids).exists()
assert not Picking.sudo().browse(fg_ids).exists()
assert not env["stock.move"].sudo().browse(move_ids+mr2_moves+fg_move_ids).exists()
with env.registry.cursor() as cr:
    observed=sql_stock(cr)
    assert set(observed)==set(persisted)
    for k,v in persisted.items():
        assert all(abs(a-b)<1e-7 for a,b in zip(v,observed[k])),(k,v,observed[k])
print("FASE2_EXISTING_FG_ONE_CLICK_NATIVE_INTEGRATION_ROLLBACK_PASS")
print("NO_COMMIT_NO_FASE1_RUNTIME_CHANGE")
