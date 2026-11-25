"""Source-only gate for isolated Fase 2 YA Sales Order stage 1. Run as feri."""
import ast
import csv
from pathlib import Path
from xml.etree import ElementTree as ET

root = Path.cwd()
addon = root / "addons/ya_sale_production_capacity"
files = [
    addon / "__init__.py",
    addon / "__manifest__.py",
    addon / "models/__init__.py",
    addon / "models/sale_order.py",
    addon / "views/ya_sale_order_views.xml",
    addon / "wizard/__init__.py",
    addon / "wizard/confirm_wizard.py",
    addon / "wizard/quotation_discount_wizard.py",
    addon / "security/ir.model.access.csv",
]
for path in files:
    assert path.is_file(), "MISSING: %s" % path
for path in files:
    if path.suffix == ".py":
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
ET.parse(addon / "views/ya_sale_order_views.xml")
ET.parse(addon / "views/ya_sale_confirm_wizard_views.xml")
ET.parse(addon / "views/ya_quotation_discount_wizard_views.xml")

source = (addon / "models/sale_order.py").read_text(encoding="utf-8")
xml = (addon / "views/ya_sale_order_views.xml").read_text(encoding="utf-8")
manifest = ast.literal_eval((addon / "__manifest__.py").read_text(encoding="utf-8"))
required_source = [
    "_inherit = 'sale.order'",
    "ya_is_capacity_so = fields.Boolean(",
    "ya_delivery_date = fields.Date(",
    "ya_delivery_date_label = fields.Char(",
    "from odoo.addons.ya_store_ro.models.date_labels import format_ymondd",
    "order.ya_delivery_date_label = format_ymondd(order.ya_delivery_date)",
    "ya_slot = fields.Selection(",
    "default_ya_is_capacity_so",
    "return super().create(vals_list)",
    "return super().write(vals)",
    "def action_confirm(self):",
    "ya_orders = self.filtered('ya_is_capacity_so')",
    "ya.sale.capacity.confirm.wizard",
    "def action_open_discount_wizard(self):",
    "return super().action_open_discount_wizard()",
    "ya.sale.quotation.discount.wizard",
    "return super().action_confirm()",
]
for token in required_source:
    assert token in source, "SOURCE_GUARD_MISSING: %s" % token
required_xml = [
    'ref="sale.view_order_form"',
    "ya_workflow_navigation.menu_ya_before_production",
    "default_ya_is_capacity_so",
    "[('ya_is_capacity_so', '=', True)]",
    'invisible="state in (\'draft\', \'sent\')"',
    '<field name="mode">primary</field>',
    '<xpath expr="//field[@name=\'payment_term_id\']" position="after">',
    'string="YA Tanggal Kirim"',
    'string="YA Slot Kirim"',
    'name="ya_delivery_date_label"',
    'string="Format YYYY-Mon-DD"',
    '<field name="ya_delivery_date_label" string="YA Tanggal Kirim"/>',
    'view_ya_capacity_sale_order_list',
    'action_ya_capacity_sale_orders_form_view',
]
for token in required_xml:
    assert token in xml, "VIEW_GUARD_MISSING: %s" % token
assert "ya_workflow_navigation" in manifest["depends"]
assert "sale_stock" in manifest["depends"]
assert "security/ir.model.access.csv" in manifest["data"]
assert manifest["data"].index("security/ir.model.access.csv") < manifest["data"].index("views/ya_sale_confirm_wizard_views.xml")
with (addon / "security/ir.model.access.csv").open(newline="", encoding="utf-8") as fh:
    acl_rows = list(csv.DictReader(fh))
expected_wizard_models = {
    "model_ya_sale_capacity_confirm_wizard",
    "model_ya_sale_quotation_discount_wizard",
}
assert len(acl_rows) == 2, "ACL_EXPECTED_EXACTLY_TWO_YA_WIZARDS"
assert {row["model_id:id"] for row in acl_rows} == expected_wizard_models, "ACL_WIZARD_MODELS_MISMATCH"
for row in acl_rows:
    assert row["group_id:id"] == "sales_team.group_sale_salesman", "ACL_WRONG_GROUP"
    assert all(row["perm_" + p] == "1" for p in ("read", "write", "create", "unlink")), "ACL_MISSING_WIZARD_RIGHTS"
assert manifest["installable"] is True
assert not any(token in source for token in (
    "env.cr.commit()", "env.cr.execute(", "mrp.production'].create(",
    "stock.quant'].create(", "stock.move'].create(",
)), "UNSAFE_SOURCE_SCOPE"
print("FASE2_YA_SALE_SOURCE_PREFLIGHT_PASS")
wizard = (addon / "wizard/confirm_wizard.py").read_text(encoding="utf-8")
assert "('state', '=', 'published')" in wizard
assert "default_ya_is_capacity_so" in xml
assert "required=\"ya_is_capacity_so\"" not in xml
assert "orders._ya_validate_published_schedule()" not in source
assert "self._ya_validate_published_schedule()" not in source
assert "order.write(" not in wizard
assert "order.state =" not in wizard
assert "raise UserError(" in wizard
assert "order.action_confirm()" not in wizard
assert "super().action_confirm()" not in wizard
assert "views/ya_sale_confirm_wizard_views.xml" in manifest["data"]
discount_wizard = (addon / "wizard/quotation_discount_wizard.py").read_text(encoding="utf-8")
for key in ("one_percent", "one_amount", "all_percent", "global_percent", "global_amount",
            "sale.order.discount", "line.discount", "discount_percentage=value / 100",
            "order.state not in ('draft', 'sent')", "_is_global_discount()"):
    assert key in discount_wizard, "DISCOUNT_WIZARD_MISSING: %s" % key
assert "views/ya_quotation_discount_wizard_views.xml" in manifest["data"]
assert "from . import quotation_discount_wizard" in (addon / "wizard/__init__.py").read_text(encoding="utf-8")
print("SCOPE: YA quotation Draft/Sent without schedule; wizard at confirm; fail-closed")
print("YA_DISCOUNT: one-line Rp/%; all-lines %; global Rp/%; native Sales unaffected")
print("STANDARD_SALES: native action_confirm delegate, no YA rules")
print("INSTALL_STATUS: SOURCE_ONLY_NOT_PROVEN")
