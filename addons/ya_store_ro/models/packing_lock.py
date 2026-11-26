"""Shared date/slot mutex.

Fase1 retains the original advisory-lock behavior. RO_SO adds a persistent
transaction fence: under REPEATABLE READ a stale concurrent writer gets
PostgreSQL serialization_failure (40001), not a silently stale business read.
The caller must retry the WHOLE transaction, never just a savepoint.
"""
from datetime import date

CLONE_DB = "erp-yussyakmal-mrp-test-RO_SO"


def lock_ro_slot(cr, delivery_date, slot):
    if not delivery_date or not slot:
        raise ValueError('Delivery date and slot required for Packing mutex')
    key = 'ya_store_ro.packing:%s:%s' % (delivery_date, slot)
    cr.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (key,))
    if cr.dbname != CLONE_DB:
        return
    day = date.fromisoformat(str(delivery_date))
    if slot not in ("S1", "S2", "S3"):
        raise ValueError("Invalid slot for RO_SO transaction fence")
    # A plain SELECT or advisory lock cannot refresh a repeatable-read
    # snapshot. INSERT/UPDATE must conflict with any newer committed row,
    # even on first use of a date/slot. Let SQLSTATE 40001 propagate.
    # Never delete/reset an operational fence row.
    cr.execute("""
        INSERT INTO ya_consolidation_slot_fence (delivery_date, slot, revision)
        VALUES (%s, %s, 1)
        ON CONFLICT (delivery_date, slot) DO UPDATE
        SET revision = ya_consolidation_slot_fence.revision + 1
    """, (day, slot))
