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
# Record actual committed stock BEFORE creating any fixtures, including
# reservations. Independent read-only SQL comparison follows rollback.
stock_template=Line.browse(3150)
assert stock_template.reference=="10042"
stock_bom=stock_template._capacity_bom()
stock_cdc=Warehouse.search([("code","=","CDC"),("company_id","=",company.id)])
stock_pck=Warehouse.search([("code","=","PCK"),("company_id","=",company.id)])
stock_kitchen=stock_bom.picking_type_id.warehouse_id
assert len(stock_cdc)==len(stock_pck)==1 and stock_kitchen
stock_pairs=sorted(set(
    (p.id,loc.id) for p in stock_bom.bom_line_ids.mapped("product_id")
    for loc in (stock_cdc.lot_stock_id,stock_kitchen.lot_stock_id)
)|{(stock_template.product_id.id,loc.id) for loc in
    (stock_kitchen.lot_stock_id,stock_pck.lot_stock_id)})
def sql_stock(cr):
    result={}
    for pid,lid in stock_pairs:
        cr.execute("""SELECT COALESCE(SUM(quantity),0),COALESCE(SUM(reserved_quantity),0)
            FROM stock_quant WHERE company_id=%s AND product_id=%s AND location_id=%s
            AND lot_id IS NULL AND owner_id IS NULL AND package_id IS NULL""",
            (company.id,pid,lid))
        result[(pid,lid)]=tuple(map(float,cr.fetchone()))
    return result
persisted_stock=sql_stock(env.cr)
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
        ("name","=","ya_sale_production_capacity")],limit=1).installed_version == "19.0.1.4.0"
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
    Final=env["ya.sale.mo2.finalization"].sudo()
    Mo2Line=env["ya.sale.mo2.release.line"].sudo()
    assert "ya_pp2_design_b_snapshot" in Final._fields
    zero_review=batch._ya_read_pp2_design_b_review()
    class UndoZeroTest(Exception):
        pass
    try:
        with env.cr.savepoint():
            zero=batch._ya_release_pp2_design_b_core(zero_review["digest"])
            assert not zero.line_ids
            assert zero._ya_pp2_frozen_facts()==zero_review["facts"]
            rejected(lambda: batch._ya_release_pp2_design_b_core(zero_review["digest"]),
                     "PP2 already finalized")
            rejected(lambda: draft._ya_confirm_with_protected_capacity(test_date,"S1"),
                     "PP2 already finalized")
            assert draft.state in ("draft","sent")
            assert not Ledger.search_count([("order_id","=",draft.id)])
            assert mo1_identity()==baseline_mo1_identity
            zero_id=zero.id
            raise UndoZeroTest()
    except UndoZeroTest:
        env.invalidate_all()
    assert not Final.browse(zero_id).exists()
    assert not Final.search_count([("batch_id","=",batch.id)])
    print("PP2_ZERO_MO2_FINALIZATION_AND_SO_CLOSURE_PASS")

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
    rejected(lambda: batch._ya_release_pp2_design_b_core(zero_review["digest"]),
             "PP2 source changed; refresh review")
    assert not Final.search_count([("batch_id","=",batch.id)])
    current_review=batch._ya_read_pp2_design_b_review()
    final=batch._ya_release_pp2_design_b_core(current_review["digest"])
    assert final.batch_id==batch
    assert final.released_by.id==packing.id
    assert final._ya_pp2_frozen_facts()==current_review["facts"]
    assert len(final.line_ids)==1
    row=final.line_ids
    native=row.mo_id
    assert row.product_id==other.product_id and row.planning_line_id==line2
    assert row.qty_mo2==250 and row.qty_so==251 and row.qty_mo1==250
    assert row.published_max==500 and row.bom_output==250
    assert native.product_qty==250 and native.state not in ("draft","done","cancel")
    assert not native.ya_packing_batch_line_id and not native.workorder_ids
    from odoo.addons.ya_store_ro.models.date_labels import format_ymondd
    assert native.origin=="MO2 / %s / S1" % format_ymondd(test_date)
    assert native.id not in mos.ids
    print("PP2_NATIVE_MO2_SO_ONLY_RELEASE_PASS")
    assert mo1_identity()==baseline_mo1_identity and batch._ya_pp1_frozen_facts()==frozen
    rejected(lambda: final.write({"ya_pp2_design_b_snapshot":{}}),"immutable")
    rejected(lambda: final.unlink(),"cannot be deleted")
    rejected(lambda: row.write({"qty_mo2":0}),"immutable")
    rejected(lambda: row.unlink(),"cannot be deleted")
    rejected(lambda: batch._ya_release_pp2_design_b_core(current_review["digest"]),
             "PP2 already finalized")
    rejected(lambda: draft._ya_confirm_with_protected_capacity(test_date,"S1"),
             "PP2 already finalized")
    assert draft.state in ("draft","sent") and not draft.picking_ids
    assert not Ledger.search_count([("order_id","=",draft.id)])
    assert not batch.allocation_ids and not batch.ya_store_delivery_ids
    assert not batch.ya_fg_transfer_ids and not batch.ya_package_assembly_mo_ids
    assert final._ya_pp2_frozen_facts()==current_review["facts"]
    print("PP2_STALE_DUPLICATE_TAMPER_AND_POST_FINAL_SO_BLOCKED_PASS")
    print("PP2_MO1_UNCHANGED_NO_FINAL_ALLOCATION_OR_DO_PASS")
    # Reuse the existing native MO2 CDC bridge, not the MO1 transfer engine.
    from collections import defaultdict
    from odoo.tools import float_compare
    def raw_totals(mos):
        totals=defaultdict(float)
        for move in mos.mapped("move_raw_ids"):
            if move.state in ("done","cancel"):
                continue
            totals[move.product_id.id]+=move.product_uom._compute_quantity(
                move.product_uom_qty,move.product_id.uom_id,round=False)
        return dict(totals)
    expected=raw_totals(native)
    original_mo1_raw=raw_totals(mos)
    assert expected and original_mo1_raw
    assert set(expected)&set(original_mo1_raw)
    cdc=Warehouse.search([("code","=","CDC"),("company_id","=",company.id)])
    kitchen=native.picking_type_id.warehouse_id
    assert len(cdc)==1 and cdc!=kitchen
    Quant=env["stock.quant"].sudo()
    def physical():
        out=defaultdict(float)
        for q in Quant.search([("company_id","=",company.id),
            ("location_id","child_of",[cdc.lot_stock_id.id,kitchen.lot_stock_id.id]),
            ("product_id","in",list(expected))]):
            out[(q.location_id.id,q.product_id.id,q.lot_id.id,q.package_id.id,q.owner_id.id)]+=q.quantity
        return {k:v for k,v in out.items() if abs(v)>1e-9}
    before_stock=physical()
    before_mo1_pickings=set(batch.mr_native_transfer_ids.ids)
    transfer=row.with_env(env)._ya_create_mo2_cdc_transfer()
    assert transfer.ya_mo2_material_release_line_id.id==row.id
    assert transfer.location_id==cdc.lot_stock_id and transfer.location_dest_id==kitchen.lot_stock_id
    assert not transfer.ya_mr_batch_id and transfer.state not in ("done","cancel")
    assert len(transfer.move_ids)==len(expected)
    actual={}
    for move in transfer.move_ids:
        assert move.product_id.id not in actual
        actual[move.product_id.id]=move.product_uom._compute_quantity(
            move.product_uom_qty,move.product_id.uom_id,round=False)
    assert set(actual)==set(expected)
    for pid,qty in expected.items():
        assert float_compare(actual[pid],qty,precision_rounding=Product.browse(pid).uom_id.rounding)==0
    print("MR2_NATIVE_CDC_DEMAND_EXACT_MO2_ONLY_PASS",len(expected),"unique raw SKU")
    assert row.with_env(env)._ya_create_mo2_cdc_transfer().id==transfer.id
    assert len(row.ya_mo2_material_picking_ids)==1
    assert set(batch.mr_native_transfer_ids.ids)==before_mo1_pickings
    assert raw_totals(mos)==original_mo1_raw
    assert mo1_identity()==baseline_mo1_identity
    assert batch._ya_pp1_frozen_facts()==frozen
    assert final._ya_pp2_frozen_facts()==current_review["facts"]
    assert physical()==before_stock
    assert not batch.ya_store_delivery_ids and not row.ya_mo2_fg_picking_ids
    print("MR2_IDEMPOTENT_NO_MO1_DUPLICATION_NO_PHYSICAL_POSTING_PASS")
    # Native stock movement and native MRP only. Never manufacture stock
    # by writing quant quantity or force a document's state to Done.
    rejected(lambda: row.with_env(env)._ya_create_mo2_fg_transfer(),"DONE native MO2")
    assert not row.ya_mo2_fg_picking_ids
    print("DESIGN_B_MO2_UNFINISHED_FG_BLOCKED_PASS")
    assert all(Product.browse(pid).tracking=="none" for pid in expected)
    assert native.product_id.tracking=="none"
    pck=stock_pck
    fg_pid=native.product_id.id
    def stock_at(pid,loc):
        q=Quant.search([("company_id","=",company.id),("product_id","=",pid),
            ("location_id","=",loc.id),("lot_id","=",False),
            ("owner_id","=",False),("package_id","=",False)])
        return sum(q.mapped("quantity")),sum(q.mapped("reserved_quantity"))
    current_stock={k:stock_at(k[0],env["stock.location"].browse(k[1])) for k in stock_pairs}
    assert set(expected)==set(stock_bom.bom_line_ids.mapped("product_id").ids)
    for k,v in current_stock.items():
        assert abs(v[0]-persisted_stock[k][0])<1e-7, ("physical changed before test",k)
    real_cdc=transfer.with_env(env)
    real_cdc.action_confirm()
    real_cdc.action_assign()
    for m in real_cdc.move_ids:
        assert m.state=="assigned", ("CDC not fully reserved",m.product_id.default_code,m.state)
        assert abs(m.quantity-m.product_uom_qty)<1e-7, ("CDC not fully assigned",m.product_id.default_code,m.quantity,m.product_uom_qty)
        m.write({"quantity":m.product_uom_qty})
    result=real_cdc.with_context(skip_immediate=True,skip_backorder=True,
        cancel_backorder=True).button_validate()
    assert real_cdc.state=="done" and all(m.state=="done" for m in real_cdc.move_ids), str(result)
    for pid,qty in expected.items():
        src=stock_at(pid,cdc.lot_stock_id)[0]
        dst=stock_at(pid,kitchen.lot_stock_id)[0]
        assert abs(src-current_stock[(pid,cdc.lot_stock_id.id)][0]+qty)<1e-7, ("CDC delta",pid)
        assert abs(dst-current_stock[(pid,kitchen.lot_stock_id.id)][0]-qty)<1e-7, ("kitchen delta",pid)
        assert src>=-1e-7
    print("DESIGN_B_MR2_NATIVE_VALIDATE_FULL_STOCK_DELTAS_PASS")
    assert row.with_env(env)._ya_create_mo2_cdc_transfer().id==real_cdc.id

    # Native reservations may belong to MO1/other orders; do not steal them.
    real_mo2=native.with_env(env)
    real_mo2.action_assign()
    for m in real_mo2.move_raw_ids:
        assert m.state=="assigned", ("MO2 raw not fully reserved; review prior MO commitments",m.product_id.default_code,m.state)
    real_mo2.write({"qty_producing":float(row.qty_mo2)})
    real_mo2._set_qty_producing()
    consumed=defaultdict(float)
    for m in real_mo2.move_raw_ids:
        if m.picked and m.quantity>0:
            consumed[m.product_id.id]+=m.product_uom._compute_quantity(
                m.quantity,m.product_id.uom_id,round=False)
    assert set(consumed)==set(expected)
    for pid,qty in expected.items():
        assert abs(consumed[pid]-qty)<1e-7, ("native consumption mismatch",pid)
    assert not real_mo2._get_consumption_issues()
    result=real_mo2.with_context(skip_backorder=True,skip_redirection=True).button_mark_done()
    assert real_mo2.state=="done",str(result)
    assert all(m.state=="done" for m in real_mo2.move_raw_ids)
    finished=real_mo2.move_finished_ids.filtered(lambda m:m.state=="done"
        and m.product_id==real_mo2.product_id and m.location_dest_id==kitchen.lot_stock_id)
    qty_done=sum(m.product_uom._compute_quantity(m.quantity,real_mo2.product_id.uom_id,round=False) for m in finished)
    assert qty_done==250 and not real_mo2.workorder_ids
    for pid in expected:
        qty,res=stock_at(pid,kitchen.lot_stock_id)
        assert abs(qty-current_stock[(pid,kitchen.lot_stock_id.id)][0])<1e-7, ("raw consumption delta",pid)
        assert qty>=-1e-7 and res<=qty+1e-7
    assert abs(stock_at(fg_pid,kitchen.lot_stock_id)[0]-current_stock[(fg_pid,kitchen.lot_stock_id.id)][0]-qty_done)<1e-7
    print("DESIGN_B_MO2_NATIVE_DONE_RAW_AND_FG_STOCK_DELTAS_PASS")
    fg=row.with_env(env)._ya_create_mo2_fg_transfer()
    assert fg.state=="draft" and fg.ya_mo2_fg_release_line_id.id==row.id
    assert not fg.ya_fg_batch_id and len(fg.move_ids)==1
    move=fg.move_ids
    assert move.product_id.id==fg_pid and move.product_uom_qty==qty_done
    assert move.location_id==kitchen.lot_stock_id and move.location_dest_id==pck.lot_stock_id
    src_before=stock_at(fg_pid,kitchen.lot_stock_id)
    pck_before=stock_at(fg_pid,pck.lot_stock_id)
    assert src_before[0]-src_before[1]>=qty_done-1e-7
    fg.action_confirm()
    fg.action_assign()
    assert move.state=="assigned" and abs(move.quantity-qty_done)<1e-7
    move.write({"quantity":qty_done})
    result=fg.with_context(skip_immediate=True,skip_backorder=True,cancel_backorder=True).button_validate()
    assert fg.state=="done" and move.state=="done",str(result)
    src_after=stock_at(fg_pid,kitchen.lot_stock_id)
    pck_after=stock_at(fg_pid,pck.lot_stock_id)
    assert abs(src_after[0]-src_before[0]+qty_done)<1e-7 and src_after[0]>=-1e-7
    assert abs(pck_after[0]-pck_before[0]-qty_done)<1e-7
    assert abs(pck_after[1]-pck_before[1])<1e-7
    assert row.with_env(env)._ya_create_mo2_fg_transfer().id==fg.id
    assert len(row.ya_mo2_fg_picking_ids)==1
    assert mo1_identity()==baseline_mo1_identity and raw_totals(mos)==original_mo1_raw
    assert final._ya_pp2_frozen_facts()==current_review["facts"]
    assert not batch.ya_fg_transfer_ids and not batch.ya_store_delivery_ids
    assert not batch.allocation_ids and not batch.ya_package_assembly_mo_ids
    print("DESIGN_B_MO2_FG_NATIVE_PCK_VALIDATE_AND_IDEMPOTENCY_PASS",qty_done)
    fg_id=fg.id
    fg_move_ids=fg.move_ids.ids
    transfer_id=transfer.id
    move_ids=transfer.move_ids.ids
    final_id=final.id
    release_line_id=row.id
    mo2_id=native.id
    crossing_id=crossing.id
    batch_id=batch.id
    mo_ids=mos.ids
    late_id=late.id
    extra_ids=(plan2.id,so2.id,packing.id)
    ids=(plan.id,ro.id,paket.id,so.id,draft.id,creator.id)
finally:
    env.cr.rollback()
    print("EXPLICIT_ROLLBACK_EXECUTED")
env.invalidate_all(flush=False)
for model, ident in zip((Plan,RO,Package.sudo(),Sale,Sale,Users),ids):
    assert not model.browse(ident).exists(), model._name
assert not Ledger.search_count(domain)
assert not Batch.search_count(domain)
for model, ident in zip((Plan,Sale,Users),extra_ids):
    assert not model.browse(ident).exists(), model._name
assert not Sale.browse(late_id).exists()
assert not Sale.browse(crossing_id).exists()
assert not Batch.browse(batch_id).exists()
assert not env["mrp.production"].browse(mo_ids+[mo2_id]).exists()
assert not Final.browse(final_id).exists()
assert not Mo2Line.browse(release_line_id).exists()
print("FIXTURE_AND_NATIVE_MO_ROLLBACK_VERIFIED_PASS")
print("FASE2_PP1_NATIVE_SOURCES_ROLLBACK_PASS")
print("FASE2_PP1_REVIEW_REFRESH_ROLLBACK_PASS")
assert not env["stock.picking"].browse(transfer_id).exists()
assert not env["stock.move"].browse(move_ids).exists()
print("MR2_NATIVE_CDC_DOCUMENT_ROLLBACK_VERIFIED_PASS")
assert not env["stock.picking"].browse(fg_id).exists()
assert not env["stock.move"].browse(fg_move_ids).exists()
with env.registry.cursor() as check_cr:
    check_cr.execute("SET TRANSACTION READ ONLY")
    observed=sql_stock(check_cr)
    for key,values in persisted_stock.items():
        assert all(abs(x-y)<1e-7 for x,y in zip(values,observed[key])), ("ROLLBACK STOCK MISMATCH",key,values,observed[key])
print("DESIGN_B_NATIVE_STOCK_AND_RESERVATION_ROLLBACK_VERIFIED_PASS")
print("FASE2_PP2_NATIVE_MR2_MO2_FG_PCK_ROLLBACK_PASS")
print("NO_OPERATIONAL_RELEASE_NO_LEGACY_ALLOCATION_NO_COMMIT")
