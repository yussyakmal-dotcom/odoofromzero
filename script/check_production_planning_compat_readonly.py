"""Read-only compatibility preflight for YA Production Planning on Odoo 19.
Run with Odoo shell on erp-yussyakmal-mrp-test only.
Does not install addons, create records, write, unlink, or commit.
"""
import importlib.util
from collections import Counter

EXPECTED_DB = "erp-yussyakmal-mrp-test"
if env.cr.dbname != EXPECTED_DB:
    raise RuntimeError("STOP: unexpected database %s" % env.cr.dbname)

print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_PRODUCTION_PLANNING_COMPAT")

for package in ("openpyxl",):
    spec = importlib.util.find_spec(package)
    if spec is None:
        print("PYTHON_DEPENDENCY_MISSING:", package)
    else:
        module = __import__(package)
        print("PYTHON_DEPENDENCY:", package, getattr(module, "__version__", "unknown"))

required_fields = {
    "mrp.workcenter": ("code", "name", "active"),
    "product.product": ("default_code", "name", "active", "uom_id"),
    "uom.uom": ("name", "active"),
    "ir.ui.menu": ("name", "parent_id"),
}
for model_name, fields in required_fields.items():
    if model_name not in env:
        print("MODEL_MISSING:", model_name)
        continue
    model = env[model_name]
    print("MODEL_FIELDS:", model_name, {
        name: (model._fields[name].type if name in model._fields else "MISSING")
        for name in fields
    })

centers = env["mrp.workcenter"].with_context(active_test=False).search_read(
    [], ["code", "name", "active"], order="code, id"
)
print("WORKCENTERS_ALL:", [
    (row["code"], row["name"], row["active"]) for row in centers
])
counts = Counter(row["code"] for row in centers if row["active"])
expected = ("ASN", "CKL", "CKS", "GRG", "JP", "LG", "PST", "ROTI", "SL", "TART")
print("EXPECTED_KITCHEN_CODES:", list(expected))
print("ACTIVE_CODE_MATCH_COUNTS:", [(code, counts[code]) for code in expected])
print("PRODUCT_MASTER_COUNT:", env["product.product"].with_context(active_test=False).search_count([]))
print("UOM_MASTER_COUNT:", env["uom.uom"].with_context(active_test=False).search_count([]))
print("MENU_PARENT_MRP:", bool(env.ref("mrp.menu_mrp_root", raise_if_not_found=False)))
print("PLANNING_ADDON_STATUS:", env["ir.module.module"].search_read(
    [("name", "=", "ya_production_planning")], ["name", "state"]
))
print("READ_ONLY_PRODUCTION_PLANNING_COMPAT_CHECK_OK")
