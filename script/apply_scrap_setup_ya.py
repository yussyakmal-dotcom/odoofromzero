"""Apply one company-wide virtual Scrap location + Rusak/Expired tags.

Odoo 19 Community, ONLY erp-yussyakmal-mrp-test.
Requires YA_SCRAP_MODE=apply. Refuses duplicates. Single commit after verify.
Does not set a default destination, change Operation Types or create policy.
"""
import os

assert env.cr.dbname == "erp-yussyakmal-mrp-test", "Wrong DB"
assert os.environ.get("YA_SCRAP_MODE") == "apply", "Explicit YA_SCRAP_MODE=apply required"
Loc = env["stock.location"].sudo().with_context(active_test=False)
Tag = env["stock.scrap.reason.tag"].sudo().with_context(active_test=False)
Scrap = env["stock.scrap"].sudo()
B = env["mrp.bom"].sudo()
L = env["mrp.bom.line"].sudo()
assert "scrap_reason_tag_ids" in Scrap._fields
assert B.search_count([]) == 955 and L.search_count([]) == 8502

reference = Loc.search([
    ("usage", "=", "inventory"), ("name", "=", "Inventory adjustment")
], limit=2)
assert len(reference) == 1
reference = reference[0]
company = reference.company_id
assert company, "Reference loss location has no company"
parent = reference.location_id
if parent:
    assert parent.usage == "view", "Unexpected parent structure"

# We check all active/archived 'Scrap' names regardless of usage.
# A preexisting location must be reviewed, not silently duplicated.
assert not Loc.search([
    ("name", "=ilike", "Scrap"),
    ("company_id", "in", [False, company.id])
]), "Scrap location already exists; inspect instead of creating duplicate"
for reason in ["Rusak", "Expired"]:
    assert not Tag.search([("name", "=ilike", reason)]), (
        f"Tag {reason} already exists; inspect instead of duplicating")

before_loc = Loc.search_count([])
before_tags = Tag.search_count([])
try:
    location = Loc.create({
        "name": "Scrap",
        "usage": "inventory",
        "location_id": parent.id if parent else False,
        "company_id": company.id,
    })
    tags = [Tag.create({"name": name}) for name in ("Rusak", "Expired")]
    env.flush_all()
    assert Loc.search_count([]) == before_loc + 1
    assert Tag.search_count([]) == before_tags + 2
    assert location.usage == "inventory" and location.company_id == company
    assert location.location_id == parent
    assert [t.name for t in tags] == ["Rusak", "Expired"]
    assert B.search_count([]) == 955 and L.search_count([]) == 8502
    print("DATABASE:", env.cr.dbname)
    print("MODE: APPLY")
    print("SCRAP_LOCATION_CREATED:", location.id, location.complete_name)
    for tag in tags:
        print("SCRAP_REASON_TAG_CREATED:", tag.id, tag.name)
    print("NOTE: Scrap destination must be selected/configured in transactions; no default changed")
    env.cr.commit()
    print("SCRAP_SETUP_APPLY_OK COMMITTED")
except BaseException:
    env.cr.rollback()
    print("SCRAP_SETUP_APPLY_FAILED_ROLLED_BACK")
    raise
