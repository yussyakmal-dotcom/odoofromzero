"""Source-only gate for isolated Fase 2 YA Sales Order stage 1. Run as feri."""
import ast
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
]
for path in files:
    assert path.is_file(), "MISSING: %s" % path
for path in files:
    if path.suffix == ".py":
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
ET.parse(addon / "views/ya_sale_order_views.xml")

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
    "('state', '=', 'published')",
    "orders._ya_validate_published_schedule()",
    "self._ya_validate_published_schedule()",
    "def action_confirm(self):",
    "if any(self.mapped('ya_is_capacity_so')):",
    "return super().action_confirm()",
]
for token in required_source:
    assert token in source, "SOURCE_GUARD_MISSING: %s" % token
required_xml = [
    'ref="sale.view_order_form"',
    "ya_workflow_navigation.menu_ya_before_production",
    "default_ya_is_capacity_so",
    "[('ya_is_capacity_so', '=', True)]",
    'required="ya_is_capacity_so"',
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
assert manifest["installable"] is True
assert not any(token in source for token in (
    "env.cr.commit()", "env.cr.execute(", "mrp.production'].create(",
    "stock.quant'].create(", "stock.move'].create(",
)), "UNSAFE_SOURCE_SCOPE"
print("FASE2_YA_SALE_SOURCE_PREFLIGHT_PASS")
print("SCOPE: new YA SO records require Published date+slot; confirm fail-closed")
print("STANDARD_SALES: native action_confirm delegate, no YA rules")
print("INSTALL_STATUS: SOURCE_ONLY_NOT_PROVEN")
