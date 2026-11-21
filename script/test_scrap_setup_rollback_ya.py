"""YA Scrap setup DRY RUN (Odoo 19, MRP test ONLY).

Creates one common Inventory Loss/Scrap location and two built-in reason
tags, using native ORM, then ALWAYS rolls back. NO APPLY in this script.
Uses the same parent as existing Inventory adjustment location to keep
virtual losses together. No custom fields, no operation type changes.
"""
assert env.cr.dbname == "erp-yussyakmal-mrp-test", "Only MRP test DB"
Loc = env["stock.location"].sudo().with_context(active_test=False)
Tag = env["stock.scrap.reason.tag"].sudo().with_context(active_test=False)
Scrap = env["stock.scrap"].sudo().with_context(active_test=False)
assert "scrap_reason_tag_ids" in Scrap._fields
assert Scrap._fields["scrap_location_id"].comodel_name == "stock.location"
assert env["mrp.bom"].sudo().search_count([]) == 955
assert env["mrp.bom.line"].sudo().search_count([]) == 8502

inventory_adjustment = Loc.search([
    ("usage", "=", "inventory"), ("name", "=", "Inventory adjustment")
], limit=2)
assert len(inventory_adjustment) == 1, (
    "Expected one Inventory adjustment location; inspect actual locations")
reference = inventory_adjustment[0]
parent = reference.location_id
# Odoo may place its Inventory adjustment location at the root level.
# In that case, create the Scrap location at the same root level.
if parent:
    assert parent.usage == "view", (
        "Unexpected parent usage: " + parent.usage)
assert reference.company_id, "Expected company on inventory adjustment"
company = reference.company_id
existing = Loc.search([
    ("usage", "=", "inventory"), ("name", "=", "Scrap"),
    ("company_id", "=", company.id),
])
assert not existing, (
    "Scrap loss location already exists; do not create duplicate")
reasons = ["Rusak", "Expired"]
for reason in reasons:
    assert not Tag.search([("name", "=ilike", reason)]), (
        "Reason tag already exists: " + reason)

print("DATABASE:", env.cr.dbname)
print("MODE: TEST + ALWAYS ROLLBACK")
print("PARENT:", parent.complete_name if parent else "(root)", "| USAGE:", parent.usage if parent else "(none)")
print("REFERENCE:", reference.complete_name)
print("COMPANY:", company.name)
print("REASONS:", ", ".join(reasons))
loc_count = Loc.search_count([])
tag_count = Tag.search_count([])
try:
    location = Loc.create({
        "name": "Scrap",
        "usage": "inventory",
        "location_id": parent.id if parent else False,
        "company_id": company.id,
    })
    assert location.usage == "inventory"
    assert location.location_id == parent
    assert location.company_id == company
    print("TEST_SCRAP_LOCATION:", location.id, location.complete_name)
    new_tags = Tag.browse()
    for reason in reasons:
        tag = Tag.create({"name": reason})
        new_tags |= tag
        print("TEST_REASON_TAG:", tag.id, tag.name)
    assert len(new_tags) == 2
    assert Loc.search_count([]) == loc_count + 1
    assert Tag.search_count([]) == tag_count + 2
    assert env["mrp.bom"].sudo().search_count([]) == 955
    assert env["mrp.bom.line"].sudo().search_count([]) == 8502
    print("SCRAP_SETUP_TEST_OK: one location + two reasons created in rollback test")
finally:
    env.cr.rollback()
    env.invalidate_all()
    assert Loc.search_count([]) == loc_count
    assert Tag.search_count([]) == tag_count
    print("SCRAP_SETUP_ROLLBACK_CONFIRMED")
