"""Transaction-level mutex shared by Packing correction and Generate MO.

The same delivery date+slot must be serialized to prevent correction racing
against the production release snapshot. Transactional PostgreSQL advisory
locks are released automatically on commit/rollback.
"""


def lock_ro_slot(cr, delivery_date, slot):
    if not delivery_date or not slot:
        raise ValueError('Delivery date and slot required for Packing mutex')
    key = 'ya_store_ro.packing:%s:%s' % (delivery_date, slot)
    cr.execute('SELECT pg_advisory_xact_lock(hashtext(%s))', (key,))
