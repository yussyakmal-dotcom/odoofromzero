"""READ ONLY: inventory valuation report / periodic closing availability in Odoo19.

Only inspect registry metadata and existing accounting journals/closing entries.
NO writes, NO action execution, NO computations that change inventory.
"""
assert env.cr.dbname == "erp-yussyakmal-mrp-test", "REFUSED: test DB only"
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_ODOO19_VALUATION_CLOSING_ACCESS")
company = env.company.sudo()
print("COMPANY:", company.id, company.name)
for f in ("inventory_valuation", "inventory_period", "cost_method",
          "account_stock_valuation_id", "anglo_saxon_accounting"):
    if f in company._fields:
        val = company[f]
        if company._fields[f].type == "many2one":
            val = val.display_name if val else "-"
        print("COMPANY_SETTING:", f, val)
print("=== RELATED INSTALLED MODULES ===")
modules = env["ir.module.module"].sudo().search([
    ("name", "in", ["stock_account", "mrp_account", "account",
                   "account_financial_report", "stock", "stock_account_valuation_report",
                   "stock_inventory_valuation_report", "account_inventory_valuation"])
])
for mod in modules:
    print("MODULE:", mod.name, mod.state)
print("=== VALUATION AND CLOSING MENUS ===")
Menu = env["ir.ui.menu"].sudo()
menus = Menu.search(["|", "|",
    ("name", "ilike", "valuation"),
    ("name", "ilike", "inventory"),
    ("name", "ilike", "closing")], order="id")
# complete_name is computed/non-stored in Odoo 19; sort in Python only.
menus = menus.sorted(key=lambda m: (m.complete_name or "", m.id))
print("MENU_CANDIDATES:", len(menus))
for menu in menus[:100]:
    menu_groups = (menu["groups_id"] if "groups_id" in menu._fields else
                   menu["group_ids"] if "group_ids" in menu._fields else [])
    print("MENU:", menu.id, repr(menu.complete_name),
          "ACTION:", menu.action,
          "GROUPS:", [g.display_name for g in menu_groups],
          "ACTIVE:", menu.active if "active" in menu._fields else "N/A")
print("=== REPORT ACTION METADATA ===")
Act = env["ir.actions.act_window"].sudo()
actions = Act.search(["|", "|",
    ("name", "ilike", "valuation"),
    ("name", "ilike", "inventory"),
    ("res_model", "ilike", "valuation")])
print("ACTION_CANDIDATES:", len(actions))
for action in actions[:100]:
    print("ACTION:", action.id, repr(action.name),
          "MODEL:", action.res_model,
          "VIEWS:", action.view_mode,
          "CONTEXT:", str(action.context or "")[:280])
print("=== MODELS FOR CLOSING OR VALUATION ===")
matches = sorted(
    name for name in env.registry.models
    if ("valuation" in name or "inventory.close" in name or
        "inventory.period" in name or "stock.accounting" in name)
)
print("MODEL_MATCH_COUNT:", len(matches))
for name in matches[:100]:
    m = env[name]
    print("MODEL:", name, "DESCRIPTION:", m._description)
    selected = [k for k in m._fields if
                any(x in k for x in ("value", "amount", "period",
                                     "closing", "date", "account"))]
    print("  RELEVANT_FIELDS:", selected[:50])
print("=== STOCK VALUATION CALCULATION METHODS (DISCOVERY ONLY) ===")
for name in ("stock.move", "product.product", "product.category", "account.move",
             "res.company"):
    model = env[name]
    interesting = sorted(
        x for x in dir(type(model))
        if any(y in x for y in ("valuation", "inventory_close",
                                "inventory_valuation", "stock_valuation")))
    print("METHODS:", name, interesting[:50])
print("=== JOURNALS AND POSTED BALANCE CONTEXT ===")
Journal = env["account.journal"].sudo()
for j in Journal.search([("company_id", "=", company.id)]):
    if any(t in (j.name or "").lower() for t in
           ("inventory", "valuation", "stock", "closing")):
        print("JOURNAL:", j.id, j.name, j.code, j.type)
print("NOTE: menus/models indicate feature availability, not correctness")
print("NOTE: user access and date-cutoff accounting reconciliation require follow-up")
print("READ_ONLY_ODOO19_VALUATION_CLOSING_ACCESS_OK")
