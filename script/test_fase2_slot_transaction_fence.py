"""Clone-only technical transaction fence QA; no business fixtures or DML.

Independent transactions commit ONLY sentinel fence rows to demonstrate
MVCC conflicts. Delete only those sentinel rows after the test. Never
delete an operational fence row. Actual concurrent business UAT follows.
"""
from datetime import date
from pathlib import Path
from psycopg2 import Error
from odoo.addons.ya_store_ro.models import packing_lock

DB="erp-yussyakmal-mrp-test-RO_SO"
DAY=date(2199,12,29)
assert env.cr.dbname==DB
assert Path(packing_lock.__file__).resolve().is_relative_to(
    Path("/var/lib/ya-fase2-testing/source/addons/ya_store_ro"))
assert env["ir.module.module"].search([("name","=","ya_sale_production_capacity")]).installed_version=="19.0.1.15.0"
domain=[("delivery_date","=",DAY)]
for name in ("ya.production.planning","ya.store.ro","ya.package.store.ro",
             "ya.packing.batch","ya.sale.capacity.reservation","ya.consolidation.timer.queue"):
    assert not env[name].sudo().search_count(domain),name
assert not env["sale.order"].sudo().search_count([("ya_delivery_date","=",DAY)])
def one(cr,sql,args=()):
    cr.execute(sql,args)
    return cr.fetchone()[0]
def count(cr):
    return one(cr,"SELECT count(*) FROM ya_consolidation_slot_fence WHERE delivery_date=%s",(DAY,))
def revision(cr,slot):
    return one(cr,"SELECT revision FROM ya_consolidation_slot_fence WHERE delivery_date=%s AND slot=%s",(DAY,slot))
def begin(cr):
    assert one(cr,"SELECT current_database()")==DB
    assert one(cr,"SHOW transaction_isolation")=="repeatable read"
    cr.execute("SET LOCAL lock_timeout='3s'")
    one(cr,"SELECT txid_current_snapshot()")
def stale_failure(cr):
    try:
        packing_lock.lock_ro_slot(cr,DAY,"S1")
    except Error as exc:
        assert exc.pgcode=="40001",(exc.pgcode,str(exc))
        print("EXPECTED_SQLSTATE_40001",exc.pgcode)
        cr.rollback()
    else:
        cr.rollback()
        raise AssertionError("Stale transaction accepted")
# Dedicated session advisory lock prevents two copies of this diagnostic
# from using the sentinel concurrently.
with env.registry.cursor() as sentinel:
    key="ya_fase2_slot_fence_qa_2199_12_29"
    assert one(sentinel,"SELECT pg_try_advisory_lock(hashtext(%s))",(key,))
    claimed=False
    try:
        assert count(sentinel)==0,"Sentinel already exists; do not delete"
        claimed=True
        sentinel.rollback()
        with env.registry.cursor() as first, env.registry.cursor() as second:
            try:
                begin(first)
                begin(second)
                assert count(second)==0
                packing_lock.lock_ro_slot(first,DAY,"S1")
                assert revision(first,"S1")==1
                first.commit()
                stale_failure(second)
                begin(second)
                packing_lock.lock_ro_slot(second,DAY,"S1")
                assert revision(second,"S1")==2
                second.commit()
                print("SLOT_FENCE_FIRST_USE_STALE_REJECT_FRESH_RETRY_PASS")
                begin(first)
                begin(second)
                assert revision(second,"S1")==2
                packing_lock.lock_ro_slot(first,DAY,"S1")
                assert revision(first,"S1")==3
                first.commit()
                stale_failure(second)
                begin(second)
                packing_lock.lock_ro_slot(second,DAY,"S1")
                assert revision(second,"S1")==4
                second.rollback()
                print("SLOT_FENCE_EXISTING_ROW_STALE_REJECT_FRESH_RETRY_PASS")
                # Concurrent open transactions on different slots do not
                # share a row or advisory key.
                begin(first)
                begin(second)
                packing_lock.lock_ro_slot(first,DAY,"S1")
                packing_lock.lock_ro_slot(second,DAY,"S2")
                assert revision(first,"S1")==4
                assert revision(second,"S2")==1
                first.rollback()
                second.rollback()
                print("SLOT_FENCE_DIFFERENT_SLOT_INDEPENDENT_PASS")
            finally:
                first.rollback()
                second.rollback()
    finally:
        sentinel.rollback()
        if claimed:
            sentinel.execute("DELETE FROM ya_consolidation_slot_fence WHERE delivery_date=%s",(DAY,))
            sentinel.commit()
            assert count(sentinel)==0
            sentinel.rollback()
        one(sentinel,"SELECT pg_advisory_unlock(hashtext(%s))",(key,))
        sentinel.rollback()
env.cr.rollback()
print("FASE2_SLOT_TRANSACTION_FENCE_PASS")
print("ONLY_SENTINEL_TECHNICAL_COMMITS_CLEANED_NO_BUSINESS_DML")
