"""Odoo shell only, after explicit clone module upgrade. Never commits."""
from datetime import date, timedelta
from odoo.exceptions import UserError

assert env.cr.dbname == "erp-yussyakmal-mrp-test-RO_SO"
assert env.user.has_group("mrp.group_mrp_manager")
Line = env["ya.production.planning.line"]
Audit = env["ya.planning.revision.audit"]

class RollbackTest(Exception):
    pass

def rejected(fn):
    try:
        with env.cr.savepoint():
            fn()
    except UserError:
        return
    raise AssertionError("Expected UserError")

try:
    with env.cr.savepoint():
        # Only a future unused line; no synthetic SO/RO, no historic batch edits.
        candidates = Line.search([
            ("planning_id.state", "=", "published"),
            ("planning_id.delivery_date", ">", date.today() + timedelta(days=2)),
            ("max_capacity", ">", 0)], limit=500)
        target = Line.browse()
        for line in candidates:
            try:
                ro, so, locked, referenced = line._ya_revision_facts()
                if not (ro or so or locked or referenced):
                    target = line
                    break
            except UserError:
                continue
        if not target:
            raise RuntimeError("BLOCKED: no eligible future unused Published Planning line; prepare approved fixture")
        ident = target.id
        old = target.max_capacity
        batch = int(target._capacity_bom().product_qty)
        n = Audit.search_count([("planning_line_ref", "=", ident)])
        rejected(lambda: target.write({"max_capacity": old + batch}))
        rejected(lambda: target._ya_controlled_revision(old + batch, "", old))
        target._ya_controlled_revision(old + batch, "ROLLBACK UAT ONLY", old)
        assert target.max_capacity == old + batch
        assert target.planning_id.state == "published"
        audit = Audit.search([("planning_line_ref", "=", ident)], limit=1)
        assert audit.old_max == old and audit.new_max == old + batch
        assert audit.actor_id == env.user
        assert Audit.search_count([("planning_line_ref", "=", ident)]) == n + 1
        rejected(lambda: audit.write({"reason": "tamper"}))
        rejected(lambda: audit.unlink())
        rejected(lambda: target._ya_controlled_revision(old + 2*batch, "stale", old))
        target._ya_controlled_revision(old, "ROLLBACK UAT restore", old + batch)
        assert target.max_capacity == old
        raise RollbackTest()
except RollbackTest:
    env.invalidate_all()
    assert Line.browse(ident).max_capacity == old
    assert Audit.search_count([("planning_line_ref", "=", ident)]) == n
    print("FASE2_PLANNING_REVISION_UNUSED_NATIVE_ROLLBACK_PASS")
finally:
    env.cr.rollback()
