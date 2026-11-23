"""READ ONLY: inspect Odoo19 periodic inventory closing implementation metadata.

No call to any closing method, no journal creation, no posting, no writes.
Test database only. Inspect source signatures and selected source snippets
for human code review; do not expose sensitive config values.
"""
import inspect
assert env.cr.dbname == "erp-yussyakmal-mrp-test", "REFUSED: TEST DB ONLY"
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_ODOO19_STOCK_CLOSING_IMPLEMENTATION")
company = env.company.sudo()
print("COMPANY:", company.id, company.name)
print("VAL_MODE:", company.inventory_valuation if "inventory_valuation" in company._fields else "N/A")
print("VAL_PERIOD:", company.inventory_period if "inventory_period" in company._fields else "N/A")
names = (
    "_action_close_stock_valuation",
    "action_close_stock_valuation",
    "_cron_post_stock_valuation",
    "_get_location_valuation_vals",
    "_get_stock_valuation_account_vals",
    "_get_valuation_product_domain",
)
for name in names:
    meth = getattr(type(company), name, None)
    print("=== METHOD:", name, "PRESENT:", bool(meth), "===")
    if not meth:
        continue
    try:
        print("SIGNATURE:", inspect.signature(meth))
    except (TypeError, ValueError) as error:
        print("SIGNATURE_ERROR:", type(error).__name__)
    try:
        origin = inspect.getsourcefile(meth)
        print("SOURCE_FILE:", origin)
        code = inspect.getsource(meth)
        print("SOURCE_LINES:", len(code.splitlines()))
        for n, line in enumerate(code.splitlines()[:170], 1):
            print("  %03d: %s" % (n, line[:230]))
        if len(code.splitlines()) > 170:
            print("  ... TRUNCATED ...")
    except (OSError, TypeError) as error:
        print("SOURCE_UNAVAILABLE:", type(error).__name__)
print("=== STOCK VALUATION REPORT ACTION ===")
Act = env["ir.actions.act_window"].sudo()
for act in Act.search([("res_model", "=", "stock.move")]):
    if "valu" in (act.name or "").lower():
        print("ACTION:", act.id, act.name, "CONTEXT:", str(act.context or "")[:300],
              "DOMAIN:", str(act.domain or "")[:300])
print("=== VALUATION REPORT REGISTERED MODEL ===")
report_name = "stock_account.stock.valuation.report"
if report_name in env.registry.models:
    report = env[report_name]
    print("REPORT_MODEL:", report_name, "TYPE:", report._name,
          "TRANSIENT:", report._transient)
print("NOTE: This script NEVER invokes closing methods or creates GL entries.")
print("READ_ONLY_ODOO19_STOCK_CLOSING_IMPLEMENTATION_OK")
