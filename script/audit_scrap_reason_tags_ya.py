"""Read-only inspection of stock.scrap reason tags on YA MRP test.

No tag or location is created. Find actual relation comodel, tag records,
and reason-related fields on stock.scrap before deciding configuration.
"""
assert env.cr.dbname == "erp-yussyakmal-mrp-test", "Wrong database"
S = env["stock.scrap"].sudo().with_context(active_test=False)
Loc = env["stock.location"].sudo().with_context(active_test=False)
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY")
f = S._fields.get("scrap_reason_tag_ids")
assert f is not None, "Scrap reason tags not installed"
print("SCRAP_REASON_FIELD:", f.name, "TYPE:", f.type,
      "COMODEL:", f.comodel_name,
      "REQUIRED:", f.required, "READONLY:", f.readonly)
Tag = env[f.comodel_name].sudo().with_context(active_test=False)
print("TAG_MODEL:", Tag._name)
print("TAG_FIELDS:")
for n in sorted(Tag._fields):
    if n in ("name", "active", "company_id", "color", "sequence", "display_name"):
        tf = Tag._fields[n]
        print("  FIELD:", n, "TYPE:", tf.type, "REQUIRED:", tf.required)
tags = Tag.search([])
print("TAG_COUNT:", len(tags))
for tag in tags:
    print("TAG:", tag.id, tag.display_name,
          "| ACTIVE:", tag.active if "active" in Tag._fields else "n/a")
print("SCRAP_DESTINATION_DOMAIN:", repr(S._fields["scrap_location_id"].domain))
print("INVENTORY_USAGE_LOCATIONS:")
for loc in Loc.search([("usage", "=", "inventory")]):
    print("LOCATION:", loc.id, loc.complete_name, "ACTIVE:", loc.active)
print("SCRAP_REASON_AUDIT_OK: no database changes")
