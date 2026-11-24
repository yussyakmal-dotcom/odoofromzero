"""READ ONLY gate before installing OCA stock_no_negative 19.0 on TEST.

Does not install/upgrade Odoo modules, create records, or mutate stock.
Run on dedicated erp-yussyakmal-mrp-test via Odoo shell before -i.
The custom addon source must already be placed in a configured addons_path.
All existing negative internal/transit storable quants must be resolved.
"""
import ast
from pathlib import Path
from odoo.tools import config, float_compare

EXPECTED_DB = "erp-yussyakmal-mrp-test"
assert env.cr.dbname == EXPECTED_DB, "REFUSED: TEST DATABASE ONLY"
print("DATABASE:", env.cr.dbname)
print("MODE: READ_ONLY_OCA_NEGATIVE_GUARD_INSTALL_GATE")

Warehouse = env["stock.warehouse"].sudo()
Product = env["product.product"].sudo()
Quant = env["stock.quant"].sudo()
Module = env["ir.module.module"].sudo()

sul = Warehouse.search([("code", "=", "SUL")], limit=2)
assert len(sul) == 1 and sul.lot_stock_id.complete_name == "SUL/Stock", (
    "REFUSED: Expected exactly one SUL/Stock warehouse")
for code in ("10662", "11436"):
    products = Product.search([("default_code", "=", code)], limit=2)
    assert len(products) == 1, "REFUSED: SKU missing/duplicate "+code
    p = products[0]
    assert p.is_storable, "REFUSED: tracked stock product changed "+code
    quants = Quant.search([
        ("product_id", "=", p.id),
        ("location_id", "=", sul.lot_stock_id.id),
        ("company_id", "=", sul.company_id.id),
    ])
    total = sum(quants.mapped("quantity"))
    assert float_compare(
        total, 0.0, precision_rounding=p.uom_id.rounding
    ) == 0, "REFUSED: SUL/Stock not zero following owner-approved opname: "+code
    print("PREVIOUS_TEST_NEGATIVE_SKU_NOW_ZERO:", code,
          "stock:", total, "uom:", p.uom_id.name)

negative = Quant.search([
    ("quantity", "<", -0.000001),
    ("location_id.usage", "in", ["internal", "transit"]),
    ("product_id.is_storable", "=", True),
], limit=10)
print("PRESENT_NEGATIVE_INTERNAL_TRANSIT_QUANT_SAMPLE_COUNT:", len(negative))
for q in negative:
    print("NEGATIVE_BLOCKER:", q.product_id.default_code,
          q.quantity, q.product_id.uom_id.name,
          q.location_id.complete_name)
assert not negative, (
    "REFUSED: negative storable stock remains; don't install guard yet")

paths = config["addons_path"]
if isinstance(paths, (list, tuple)):
    addon_dirs = [Path(str(p)) for p in paths if str(p)]
else:
    addon_dirs = [Path(p.strip()) for p in str(paths).split(",") if p.strip()]
print("CONFIGURED_ADDON_DIRECTORY_COUNT:", len(addon_dirs))
print("CONFIGURED_ADDON_DIRECTORIES:", [str(p) for p in addon_dirs])
found = []
for base in addon_dirs:
    manifest = base / "stock_no_negative" / "__manifest__.py"
    if manifest.is_file():
        found.append(manifest)
assert len(found) == 1, (
    "REFUSED: Expected exactly one OCA addon in configured path; found %s" %
    [str(p) for p in found])
manifest = found[0]
module_dir = manifest.parent
values = ast.literal_eval(manifest.read_text(encoding="utf8"))
assert values.get("name") == "Stock Disallow Negative", (
    "REFUSED: mismatched addon display name")
assert values.get("version") == "19.0.1.0.1", (
    "REFUSED: unexpected OCA addon version")
assert values.get("depends") == ["stock"], (
    "REFUSED: unexpected extra OCA addon dependency")
assert values.get("installable") is True, (
    "REFUSED: addon not installable")
for relative in ("__init__.py", "models/__init__.py",
                 "models/stock_quant.py", "models/product.py",
                 "models/stock_location.py",
                 "views/product_product_views.xml",
                 "views/stock_location_views.xml"):
    assert (module_dir / relative).is_file(), (
        "REFUSED: missing addon file "+relative)
check_code = (module_dir / "models/stock_quant.py").read_text(
    encoding="utf8")
assert "def check_negative_qty" in check_code and (
    'quant.location_id.usage in ["internal", "transit"]' in check_code), (
    "REFUSED: expected OCA negative-stock constraint source not found")
print("OCA_MANIFEST_SOURCE:", str(manifest))
print("OCA_MODULE_VERSION:", values["version"])
print("OCA_LICENSE:", values["license"])

modules = Module.search([("name", "=", "stock_no_negative")], limit=2)
assert len(modules) <= 1, "REFUSED: multiple registered module records"
if modules:
    print("OCA_REGISTRY_STATE:", modules.state)
    assert modules.state in ("uninstalled", "uninstallable"), (
        "STOP: module already installed or in transitional state")
else:
    print("OCA_REGISTRY_STATE: NOT_DISCOVERED_BEFORE_APPS_UPDATE")

print("OCA_STOCK_NO_NEGATIVE_TEST_INSTALL_READINESS_PASS")
print("NO_DB_WRITES_NO_INSTALL_NO_RESTART")
