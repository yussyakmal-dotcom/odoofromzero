"""Read-only: why YA RO Toko 'Upload RO Baru' list button is missing.

Odoo 19 shell; exact test database only. Checks server-loaded module, action,
menu, list view and group restriction. Does not print user identities.
No writes / upgrade / view modification / commits.
"""
DB = "erp-yussyakmal-mrp-test"
assert env.cr.dbname == DB, "REFUSED: wrong database"

print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_RO_UPLOAD_BUTTON")
Mod = env["ir.module.module"].sudo().search([("name", "=", "ya_store_ro")], limit=1)
print("MODULE:", Mod.state if Mod else "MISSING",
      "| installed_version:", Mod.installed_version if Mod else "(NONE)")

for xid in [
    "ya_store_ro.menu_ya_store_ro",
    "ya_store_ro.action_ya_store_ro",
    "ya_store_ro.view_ya_store_ro_list",
    "ya_store_ro.action_ya_store_ro_import",
]:
    item = env.ref(xid, raise_if_not_found=False)
    print("XMLID:", xid, "| exists:", bool(item),
          "| res_model:", item._name if item else "(NONE)")
    if not item:
        continue
    if item._name == "ir.ui.menu":
        print("  MENU:", item.name, "| active:", item.active,
              "| action:", item.action.display_name if item.action else "(NONE)",
              "| groups:", item.group_ids.mapped("display_name"))
    elif item._name == "ir.actions.act_window":
        print("  ACTION:", item.name, "| model:", item.res_model,
              "| view_mode:", item.view_mode,
              "| preferred_view:", item.view_id.display_name if item.view_id else "(NONE)")
    elif item._name == "ir.ui.view":
        xml = str(item.arch_db or "")
        print("  VIEW:", item.name, "| model:", item.model,
              "| type:", item.type, "| active:", item.active,
              "| priority:", item.priority,
              "| has_upload_button:", "action_open_upload" in xml,
              "| display_always:", 'display="always"' in xml,
              "| manager_group_guard:", "mrp.group_mrp_manager" in xml)
views = env["ir.ui.view"].sudo().search([
    ("model", "=", "ya.store.ro"), ("type", "=", "list"),
])
print("ALL_RO_LIST_VIEWS:", len(views))
for view in views:
    print("  LIST_VIEW:", view.id, "|", view.name,
          "| active:", view.active,
          "| priority:", view.priority,
          "| upload_button:", "action_open_upload" in str(view.arch_db or ""))
# Effective default list architecture with server-side view resolution.
try:
    effective = env["ya.store.ro"].sudo().get_view(view_type="list")
    arch = str(effective.get("arch") or "")
    print("EFFECTIVE_LIST_VIEW_ID:", effective.get("id"))
    print("EFFECTIVE_LIST_HAS_UPLOAD:", "action_open_upload" in arch)
except Exception as exc:
    print("EFFECTIVE_LIST_QUERY_ERROR:", type(exc).__name__, str(exc)[:300])
print("RESULT: Check GUI user's Manufacturing Manager group separately.")
print("READ_ONLY_RO_UPLOAD_AUDIT_OK")
