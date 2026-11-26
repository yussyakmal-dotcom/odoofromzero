"""Clone-only SQL diagnostic: independent Odoo cursors, no business DML.

Commit only an otherwise empty probe transaction (SELECT + advisory lock +
transaction ID), not the shell transaction or any business fixture. This is
NOT an actual simultaneous SO confirmation test. It establishes whether an
advisory lock alone refreshes the waiting Odoo transaction's snapshot.
"""
from datetime import date, timedelta
from odoo.addons.ya_store_ro.models.packing_lock import lock_ro_slot

DB="erp-yussyakmal-mrp-test-RO_SO"
assert env.cr.dbname==DB
day=date.today()+timedelta(days=730)
slot="S1"
key="ya_store_ro.packing:%s:%s"%(day,slot)

def one(cr,sql,args=()):
    cr.execute(sql,args)
    return cr.fetchone()[0]

def begin_probe(cr):
    assert one(cr,"SELECT current_database()")==DB
    cr.execute("SET LOCAL lock_timeout = '2s'")
    return one(cr,"SELECT pg_backend_pid()"),one(cr,"SHOW transaction_isolation")

with env.registry.cursor() as first, env.registry.cursor() as second:
    try:
        pid1,iso1=begin_probe(first)
        pid2,iso2=begin_probe(second)
        assert pid1!=pid2
        print("ODOO_INDEPENDENT_CURSOR_ISOLATION",iso1,iso2)
        # Fail quickly rather than wait on a real user's transaction.
        assert one(first,"SELECT pg_try_advisory_xact_lock(hashtext(%s))",(key,)), "Probe slot busy"
        lock_ro_slot(first,day,slot)
        xid=one(first,"SELECT txid_current()")
        before=str(one(second,"SELECT txid_current_snapshot()"))
        assert not one(second,"SELECT pg_try_advisory_xact_lock(hashtext(%s))",(key,))
        assert not one(second,"SELECT txid_visible_in_snapshot(%s,%s::txid_snapshot)",(xid,before))
        print("NATIVE_DATE_SLOT_LOCK_MUTUAL_EXCLUSION_PASS")
        # Only an empty SQL probe transaction is committed here.
        first.commit()
        assert one(second,"SELECT pg_try_advisory_xact_lock(hashtext(%s))",(key,))
        lock_ro_slot(second,day,slot)
        after=str(one(second,"SELECT txid_current_snapshot()"))
        visible=bool(one(second,"SELECT txid_visible_in_snapshot(%s,%s::txid_snapshot)",(xid,after)))
        print("PROBE_PREVIOUS_TRANSACTION_VISIBLE_AFTER_SLOT_LOCK",visible)
        second.rollback()
        _,fresh_iso=begin_probe(second)
        fresh=str(one(second,"SELECT txid_current_snapshot()"))
        fresh_visible=bool(one(second,"SELECT txid_visible_in_snapshot(%s,%s::txid_snapshot)",(xid,fresh)))
        assert fresh_visible,"Fresh transaction does not see completed probe xid"
        print("FRESH_TRANSACTION_VISIBILITY_PASS",fresh_iso)
        if not visible:
            print("SLOT_ADVISORY_LOCK_ALONE_STALE_SNAPSHOT_RISK_CONFIRMED")
        else:
            print("SLOT_ADVISORY_LOCK_PROBE_FRESH_SNAPSHOT_OBSERVED")
        print("FASE2_SLOT_LOCK_SNAPSHOT_DIAGNOSTIC_COMPLETE")
    finally:
        first.rollback()
        second.rollback()
env.cr.rollback()
print("NO_BUSINESS_DML_NO_BUSINESS_COMMIT_NO_TIMER_NO_FASE1_RUNTIME_CHANGE")
