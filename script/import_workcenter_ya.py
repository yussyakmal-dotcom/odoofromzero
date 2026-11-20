"""Import work centers from a PRIVATE CSV via Odoo ORM.

CSV headings: Work Center,Code
Usage: YA_TARGET_DB=<test-db> YA_WORKCENTER_CSV=/private/path/WORK_CENTRE.csv
By default PREVIEW only; YA_APPLY=1 commits on validated test database.
No business master data or infrastructure identifiers are embedded in Git.
"""
import csv
import os
from pathlib import Path

db = os.environ.get("YA_TARGET_DB", "").strip()
source = os.environ.get("YA_WORKCENTER_CSV", "").strip()
apply = os.environ.get("YA_APPLY") == "1"

assert db and db.endswith("-mrp-test"), "Only a named MRP test database is permitted"
assert env.cr.dbname == db, "Connected database is not YA_TARGET_DB"
assert source, "Specify YA_WORKCENTER_CSV pointing to a private CSV"

path = Path(source)
assert path.is_file(), f"CSV not found: {path}"
with path.open("r", encoding="utf-8-sig", newline="") as handle:
    reader = csv.DictReader(handle)
    assert reader.fieldnames, "CSV missing header"
    assert {"Work Center", "Code"} <= set(reader.fieldnames), (
        f"Unexpected CSV columns: {reader.fieldnames}"
    )
    rows = [
        (r["Code"].strip(), r["Work Center"].strip())
        for r in reader
    ]

assert rows, "Empty CSV"
assert all(code and name for code, name in rows), "Blank code/name"
assert len(rows) == len({code.casefold() for code, _ in rows}), "Duplicate source code"
assert len(rows) == len({name.casefold() for _, name in rows}), "Duplicate source name"

module = env["ir.module.module"].sudo().search(
    [("name", "=", "mrp"), ("state", "=", "installed")], limit=1
)
assert module, "Manufacturing module not installed"

wc_model = env["mrp.workcenter"].sudo().with_context(active_test=False)
print("DATABASE:", env.cr.dbname)
print("SOURCE ROWS:", len(rows))
print("MODE:", "APPLY" if apply else "PREVIEW")
print("EXISTING:", wc_model.search_count([]))

plan = []
blockers = []
for code, name in rows:
    by_code = wc_model.search([("code", "=", code)])
    by_name = wc_model.search([("name", "=", name)])
    if len(by_code) > 1 or len(by_name) > 1:
        blockers.append(f"Ambiguous existing records: {code} / {name}")
        continue
    if by_code and by_name and by_code != by_name:
        blockers.append(f"Code/name refer to different records: {code} / {name}")
        continue
    existing = by_code or by_name
    if existing:
        if existing.code != code or existing.name != name:
            blockers.append(
                f"Existing conflict: {code} / {name}; "
                f"database has {existing.code} / {existing.name}"
            )
        else:
            plan.append(("SKIP", code, name))
    else:
        plan.append(("CREATE", code, name))

for action, code, name in plan:
    print(f"{action:6} | {code:8} | {name}")
for issue in blockers:
    print("BLOCKER:", issue)
assert not blockers, "Import stopped: conflicting master data"
create_count = sum(action == "CREATE" for action, _, _ in plan)
print("PLAN: create=", create_count, "skip=", len(plan) - create_count)

if not apply:
    print("PREVIEW_OK (no changes made)")
else:
    try:
        for action, code, name in plan:
            if action == "CREATE":
                wc = wc_model.create({"name": name, "code": code, "active": True})
                assert wc.resource_id, f"Required resource missing: {code}"
        for code, name in rows:
            assert wc_model.search_count([
                ("code", "=", code), ("name", "=", name)
            ]) == 1, f"Verification failed: {code}"
        env.cr.commit()
        print("IMPORT_OK committed", "created=", create_count, "total=", len(rows))
    except Exception:
        env.cr.rollback()
        print("IMPORT_FAILED rolled back")
        raise
