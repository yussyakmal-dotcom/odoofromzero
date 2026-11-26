"""Native Design B PP2 source forecast; clone rollback only."""
from datetime import timedelta
from pathlib import Path
from odoo import fields
from odoo.addons.ya_sale_production_capacity.models import pp1_native_sources as adapter
from odoo.addons.ya_sale_production_capacity.models import pp1_review_contract as review
from odoo.addons.ya_sale_production_capacity.models import pp1_mo1_proposals as mo1
from odoo.addons.ya_sale_production_capacity.models.pp2_native_sources import read_pp2_forecast

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

    reviewed = review.read_locked_review(env,test_date,'S1',company)
    assert reviewed['facts']==facts
    assert review.revalidate_review(env,test_date,'S1',company,reviewed['digest'])==reviewed
    print('PP1_LOCKED_REVIEW_BASELINE_PASS')

    def quote(qty, product=component):
        return Sale.with_context(default_ya_is_capacity_so=True,tracking_disable=True,
            mail_create_nosubscribe=True,mail_notify_force_send=False).create({
            "partner_id":sample.partner_id.id,"company_id":company.id,
            "warehouse_id":sample.warehouse_id.id,"pricelist_id":sample.pricelist_id.id,
            "ya_delivery_date":test_date,"ya_slot":"S1",
            "order_line":[(0,0,{"product_id":product.id,"name":product.display_name,
                "product_uom_qty":qty,"product_uom_id":product.uom_id.id,
                "price_unit":product.lst_price})]})
    so=quote(5)
    draft=quote(1)
    assert so.state in ("draft","sent")
    assert read()[1]==before
    assert review.read_locked_review(env,test_date,"S1",company)["digest"]==reviewed["digest"]
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
    try:
        review.revalidate_review(env,test_date,"S1",company,reviewed["digest"])
    except adapter.PP1SourceError as exc:
        assert "PP1 source changed; refresh review" in str(exc), str(exc)
    else:
        raise AssertionError("Stale PP1 review incorrectly accepted")
    print("PP1_STALE_REVIEW_AFTER_SO_CONFIRM_BLOCKED_PASS")
    refreshed=review.read_locked_review(env,test_date,"S1",company)
    assert refreshed["digest"]!=reviewed["digest"] and refreshed["facts"]==facts
    assert review.revalidate_review(env,test_date,"S1",company,refreshed["digest"])==refreshed
    reordered=dict(facts)
    for key in review.ROW_KEYS:
        reordered[key]=list(reversed(facts[key]))
    assert review.source_digest(reordered)==refreshed["digest"]
    print("PP1_REFRESHED_REVIEW_AND_CANONICAL_DIGEST_PASS")
    assert ro.line_ids.qty_requested==4 and paket.line_ids.qty_requested==8
    assert draft.state in ("draft","sent")
    assert not Batch.search_count(domain)
    print("ORIGINAL_DEMAND_UNCHANGED_NO_PP1_OR_DO_PASS")
    # A second kitchen SKU with SO demand only must enter MO1, even
    # without an ordinary RO or RO Paket for that SKU.
    other = Line.browse(3150)
    assert other.reference == "10042"
    assert other._capacity_bom().product_qty == 250
    assert other.uom_id == other.product_id.uom_id
    plan2 = Plan.create({
        "delivery_date":test_date,"slot":"S1",
        "kitchen_code":other.planning_id.kitchen_code,
        "workcenter_id":other.planning_id.workcenter_id.id})
    line2 = Line.create({
        "planning_id":plan2.id,"product_id":other.product_id.id,
        "reference":other.reference,"max_capacity":500,
        "uom_id":other.uom_id.id,"bom_id":other._capacity_bom().id})
    plan2.action_publish()
    so2 = quote(1,other.product_id)
    env["ya.sale.capacity.confirm.wizard"].with_context(
        tracking_disable=True,mail_notify_force_send=False).create({
        "order_id":so2.id,"delivery_date":test_date,"slot":"S1"
    }).action_check_and_confirm()
    assert so2.state in ("sale","done") and not so2.picking_ids
    packing_login = "__ya_pp1_mo1_payload_uat__@example.invalid"
    assert not Users.search_count([("login","=",packing_login)])
    packing = Users.with_context(no_reset_password=True,tracking_disable=True,
        mail_create_nosubscribe=True,mail_notify_force_send=False).create({
        "name":packing_login,"login":packing_login,"company_id":company.id,
        "company_ids":[(6,0,[company.id])],
        group_field:[(6,0,[env.ref("ya_store_ro.group_ya_packing_admin").id])],
    })
    packing_env = Batch.with_user(packing).sudo().env
    assert packing_env.user.has_group("ya_store_ro.group_ya_packing_admin")
    try:
        mo1.prepare_mo1_proposals(packing_env,test_date,"S1",company,refreshed["digest"])
    except adapter.PP1SourceError as exc:
        assert "PP1 source changed; refresh review" in str(exc)
    else:
        raise AssertionError("Stale release proposal accepted")
    fresh = review.read_locked_review(packing_env,test_date,"S1",company)
    proposal = mo1.prepare_mo1_proposals(packing_env,test_date,"S1",company,fresh["digest"])
    assert not proposal["operational_release_allowed"]
    items = {p["reference"]:p for p in proposal["proposals"]}
    assert set(items)=={"11999","10042"}
    assert items["11999"]["native_mo_vals"]["product_qty"]==14
    assert items["10042"]["native_mo_vals"]["product_qty"]==250
    assert items["10042"]["forecast"]["confirmed_so_qty"]==1
    assert items["10042"]["forecast"]["original_ro_store_qty"]==0
    assert items["10042"]["forecast"]["original_ro_package_qty"]==0
    print("PP1_SO_ONLY_SKU_INCLUDED_NATIVE_MO1_PAYLOAD_PASS")

    # Exercise the actual private model core, not a hand-built batch.
    # The final operational cutoff/GUI gates are not wired; this is QA only.
    from odoo.exceptions import UserError
    assert "ya_pp1_design_b_snapshot" in Batch._fields
    assert env["ir.module.module"].search([
        ("name","=","ya_sale_production_capacity")],limit=1).installed_version == "19.0.1.3.0"
    def rejected(fn, expected):
        try:
            with env.cr.savepoint():
                fn()
        except UserError as exc:
            assert expected in str(exc), str(exc)
        else:
            raise AssertionError("Unexpected acceptance: "+expected)

    release = packing_env["ya.packing.batch"]._ya_create_pp1_design_b_release_core
    rejected(lambda: release(test_date,"S1",refreshed["digest"]),
             "PP1 source changed; refresh review")
    assert not Batch.search_count(domain)
    batch = release(test_date,"S1",fresh["digest"])
    assert batch.state=="production_ok"
    assert len(batch.line_ids)==2
    assert set(batch.ro_ids.ids)=={ro.id}
    assert set(batch.ya_package_ro_ids.ids)=={paket.id}
    assert ro.packing_batch_id.id==batch.id
    assert batch.released_by.id==packing.id
    frozen=batch._ya_pp1_frozen_facts()
    assert frozen==fresh["facts"]
    assert batch.ya_pp1_design_b_snapshot["digest"]==fresh["digest"]
    assert batch.ya_pp1_design_b_snapshot["actor_id"]==packing.id
    assert not batch.allocation_ids and not batch.ya_package_demand_ids
    mos=batch.line_ids.mapped("mo_id")
    assert len(mos)==2
    for row in batch.line_ids:
        native=row.mo_id
        payload=items[row.reference]["native_mo_vals"]
        assert native.state not in ("draft","cancel","done")
        assert native.ya_packing_batch_line_id==row
        assert native.product_qty==row.qty_production==payload["product_qty"]
        assert native.origin==payload["origin"]
        assert not native.workorder_ids
    print("PP1_CANONICAL_BATCH_AND_IMMUTABLE_SOURCE_SNAPSHOT_PASS")
    print("PP1_NATIVE_MO1_ATOMIC_RELEASE_CORE_PASS")

    rejected(lambda: batch.write({"ya_pp1_design_b_snapshot":{}}),"snapshot is immutable")
    rejected(lambda: batch.line_ids[:1].with_context(
        ya_release_production_batch=True).write({"mo_id":False}),"batch link is immutable")
    rejected(lambda: release(test_date,"S1",fresh["digest"]),"already released")
    rejected(lambda: batch._ya_prepare_mo2_final_release(),"SO-only PP2")
    rejected(lambda: Batch.with_context(ya_create_production_batch=True).create({
        "delivery_date":test_date+timedelta(days=1),"slot":"S1",
        "ya_pp1_design_b_snapshot":{"version":1}}),"only be created")
    assert len(batch.line_ids.mapped("mo_id"))==2
    print("PP1_DUPLICATE_RELEASE_AND_SNAPSHOT_TAMPER_BLOCKED_PASS")
    print("PP1_LEGACY_MO2_BLOCKED_PASS")

    # Record immutable SKU/batch-line/MO links and native quantities.
    # Odoo mapped() recordsets need not preserve order after cache invalidation.
    def mo1_identity():
        return sorted((row.id, row.product_id.id, row.mo_id.id,
                       row.qty_production, row.mo_id.product_qty,
                       row.mo_id.state, row.mo_id.ya_packing_batch_line_id.id)
                      for row in batch.line_ids)
    baseline_mo1_identity = mo1_identity()
    assert len(baseline_mo1_identity)==2
    assert len(set(mos.ids))==2

    # Late SO remains a native commercial confirmation; it must not modify
    # the immutable early-SO snapshot or recreate any MO1.
    late=quote(1,other.product_id)
    env["ya.sale.capacity.confirm.wizard"].with_context(
        tracking_disable=True,mail_notify_force_send=False).create({
        "order_id":late.id,"delivery_date":test_date,"slot":"S1"
    }).action_check_and_confirm()
    assert late.state in ("sale","done") and not late.picking_ids
    assert batch._ya_pp1_frozen_facts()==frozen
    assert sum(Ledger.search(domain).filtered(
        lambda x:x.product_id==other.product_id).mapped("qty_required"))==2
    assert len(batch.line_ids.mapped("mo_id"))==2
    assert ro.line_ids.qty_requested==4 and paket.line_ids.qty_requested==8
    assert not so.picking_ids and not so2.picking_ids
    print("PP1_LATE_SO_LEDGER_WITHOUT_MO1_OR_SNAPSHOT_MUTATION_PASS")
    def pp2():
        data=read_pp2_forecast(batch)
        return {r["sku"]:r for r in data["sku_forecasts"]}
    p=pp2()
    assert p["11999"]["confirmed_so_qty"]==5
    assert p["11999"]["early_so_qty"]==5 and p["11999"]["late_so_qty"]==0
    assert p["11999"]["forecast_ro_store_shortage"]==3
    assert p["11999"]["mo2_increment_due_to_so_only"]==0
    assert p["10042"]["early_so_qty"]==1 and p["10042"]["late_so_qty"]==1
    assert p["10042"]["confirmed_so_qty"]==2
    assert p["10042"]["preexisting_mo1_qty"]==250
    assert p["10042"]["mo2_increment_due_to_so_only"]==0
    print("PP2_EARLY_SO_COUNTED_ONCE_AND_RO_SHORTAGE_NO_MO2_PASS")
    crossing=quote(249,other.product_id)
    env["ya.sale.capacity.confirm.wizard"].with_context(
        tracking_disable=True,mail_notify_force_send=False).create({
        "order_id":crossing.id,"delivery_date":test_date,"slot":"S1"
    }).action_check_and_confirm()
    p=pp2()
    assert p["10042"]["confirmed_so_qty"]==251
    assert p["10042"]["early_so_qty"]==1 and p["10042"]["late_so_qty"]==250
    assert p["10042"]["mo2_increment_due_to_so_only"]==250
    assert p["10042"]["forecast_total_output"]==500
    assert p["10042"]["theoretical_extra_not_automatically_allocated"]==249
    assert p["11999"]["mo2_increment_due_to_so_only"]==0
    assert p["11999"]["forecast_ro_store_shortage"]==3
    print("PP2_INCREMENT_ONLY_FOR_SO_BATCH_CROSSING_PASS",p["10042"])
    assert batch._ya_pp1_frozen_facts()==frozen
    current_mo1_identity = mo1_identity()
    print("PP2_MO1_IDENTITY_BEFORE:",baseline_mo1_identity)
    print("PP2_MO1_IDENTITY_AFTER:",current_mo1_identity)
    assert current_mo1_identity==baseline_mo1_identity, "MO1 link, qty or state actually changed"
    assert len(batch.line_ids)==2
    assert set(batch.line_ids.mapped("mo_id").ids)==set(mos.ids), "MO1 ID set changed"
    assert not crossing.picking_ids
    assert not env["ya.sale.mo2.finalization"].search_count([("batch_id","=",batch.id)])
    print("PP2_FORECAST_NO_MO2_NO_DO_NO_PP1_MUTATION_PASS")
    crossing_id=crossing.id
    batch_id=batch.id
    mo_ids=mos.ids
    late_id=late.id
    extra_ids=(plan2.id,so2.id,packing.id)
    ids=(plan.id,ro.id,paket.id,so.id,draft.id,creator.id)
finally:
    env.cr.rollback()
    print("EXPLICIT_ROLLBACK_EXECUTED")
env.invalidate_all()
for model, ident in zip((Plan,RO,Package.sudo(),Sale,Sale,Users),ids):
    assert not model.browse(ident).exists(), model._name
assert not Ledger.search_count(domain)
assert not Batch.search_count(domain)
for model, ident in zip((Plan,Sale,Users),extra_ids):
    assert not model.browse(ident).exists(), model._name
assert not Sale.browse(late_id).exists()
assert not Sale.browse(crossing_id).exists()
assert not Batch.browse(batch_id).exists()
assert not env["mrp.production"].browse(mo_ids).exists()
print("FIXTURE_AND_NATIVE_MO_ROLLBACK_VERIFIED_PASS")
print("FASE2_PP1_NATIVE_SOURCES_ROLLBACK_PASS")
print("FASE2_PP1_REVIEW_REFRESH_ROLLBACK_PASS")
print("FASE2_PP2_NATIVE_SO_ONLY_FORECAST_ROLLBACK_PASS")
print("NO_OPERATIONAL_RELEASE_NO_LEGACY_ALLOCATION_NO_COMMIT")
