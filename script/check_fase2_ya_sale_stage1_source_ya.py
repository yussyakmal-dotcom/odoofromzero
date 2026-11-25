"""Source-only gate for YA Sales Fase2 atomic Confirm v19.0.1.1.0. Run as feri."""
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
    addon / "models/confirm_capacity_math.py",
    addon / "models/confirm_readiness.py",
    addon / "models/capacity_reservation.py",
    addon / "models/capacity_booking.py",
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
    "def _ya_native_confirm_without_early_delivery(",
    "skip_procurement=True",
]
for token in required_source:
    assert token in source, "SOURCE_GUARD_MISSING: %s" % token
required_xml = [
    'ref="sale.view_order_form"',
    "ya_workflow_navigation.menu_ya_before_production",
    "default_ya_is_capacity_so",
    "[('ya_is_capacity_so', '=', True)]",
    'readonly="state not in (\'draft\', \'sent\')"',
    'invisible="not ya_delivery_date"',
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
# Quotation may save without any YA schedule. These fields become mandatory
# only in the confirmation wizard, not in Draft/Sent form views.
view_tree = ET.parse(addon / "views/ya_sale_order_views.xml")
for field_name in ("ya_delivery_date", "ya_slot"):
    form_fields = view_tree.findall(".//xpath/field[@name='%s']" % field_name)
    assert len(form_fields) == 1, "QUOTATION_FIELD_MISSING_OR_DUPLICATE: %s" % field_name
    node = form_fields[0]
    assert node.attrib.get("readonly") == "state not in ('draft', 'sent')", "QUOTATION_NOT_EDITABLE: %s" % field_name
    assert node.attrib.get("required") not in ("1", "True", "true"), "QUOTATION_SCHEDULE_MUST_BE_OPTIONAL"
assert manifest["version"] == "19.0.1.1.0", "UNEXPECTED_ADDON_VERSION"
assert "ya_workflow_navigation" in manifest["depends"]
assert "sale_stock" in manifest["depends"]
assert "security/ir.model.access.csv" in manifest["data"]
assert manifest["data"].index("security/ir.model.access.csv") < manifest["data"].index("views/ya_sale_confirm_wizard_views.xml")
with (addon / "security/ir.model.access.csv").open(newline="", encoding="utf-8") as fh:
    acl_rows = list(csv.DictReader(fh))
expected_wizard_models = {
    "model_ya_sale_capacity_confirm_wizard",
    "model_ya_sale_quotation_discount_wizard",
    "model_ya_sale_capacity_reservation",
}
assert len(acl_rows) == 3, "ACL_EXPECTED_TWO_WIZARDS_PLUS_ONE_RESERVATION"
assert {row["model_id:id"] for row in acl_rows} == expected_wizard_models, "ACL_WIZARD_MODELS_MISMATCH"
for row in acl_rows:
    if row["model_id:id"] == "model_ya_sale_capacity_reservation":
        assert row["group_id:id"] == "ya_store_ro.group_ya_packing_admin", "ACL_RESERVATION_GROUP"
        assert [row["perm_" + p] for p in ("read", "write", "create", "unlink")] == ["1", "0", "0", "0"], "ACL_RESERVATION_MUST_BE_READ_ONLY"
    else:
        assert row["group_id:id"] == "sales_team.group_sale_salesman", "ACL_WRONG_GROUP"
        assert all(row["perm_" + p] == "1" for p in ("read", "write", "create", "unlink")), "ACL_MISSING_WIZARD_RIGHTS"
assert manifest["installable"] is True
assert not any(token in source for token in (
    "env.cr.commit()", "env.cr.execute(", "mrp.production'].create(",
    "stock.quant'].create(", "stock.move'].create(",
)), "UNSAFE_SOURCE_SCOPE"
print("FASE2_YA_SALE_SOURCE_PREFLIGHT_PASS")
wizard = (addon / "wizard/confirm_wizard.py").read_text(encoding="utf-8")
readiness = (addon / "models/confirm_readiness.py").read_text(encoding="utf-8")
assert "from . import confirm_readiness" in (addon / "models/__init__.py").read_text(encoding="utf-8")
assert "_ya_confirm_with_protected_capacity" in wizard
for token in ("def _ya_prepare_capacity_confirm_readonly(", "_is_global_discount()",
              "All / Produk Jadi / Paket", "Published Planning",
              "expand_so_package_requirements", "check_so_capacity",
              "PCK", "line.product_uom_id"):
    assert token in readiness, "CONFIRM_READINESS_MISSING: %s" % token
assert not any(token in readiness for token in (
    ".create(", ".write(", "env.cr.commit(", "env.cr.execute(",
    "action_confirm(",
)), "CONFIRM_READINESS_MUST_REMAIN_READONLY"
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
print("SCOPE: YA date/slot OPTIONAL on Draft/Sent; Confirm protected capacity CLONE-ONLY")
print("YA_DISCOUNT: one-line Rp/%; all-lines %; global Rp/%; native Sales unaffected")
print("STANDARD_SALES: native action_confirm delegate, no YA rules")
print("CONFIRM_READINESS: published SKU route, native global discount exclusions, Paket components; read-only")
booking = (addon / "models/capacity_booking.py").read_text(encoding="utf-8")
ledger = (addon / "models/capacity_reservation.py").read_text(encoding="utf-8")
assert "from . import capacity_booking" in (addon / "models/__init__.py").read_text(encoding="utf-8")
assert "from . import capacity_reservation" in (addon / "models/__init__.py").read_text(encoding="utf-8")
for token in ("lock_ro_slot(self.env.cr, delivery_date, slot)",
              "FOR UPDATE", "confirmed_orders", "check_so_capacity(",
              "mo1_qty", "incremental_mo2_output_needed",
              "def _ya_write_locked_capacity_reservations(",
              "_ya_prepare_locked_booking("):
    assert token in booking, "RESERVATION_ATOMIC_SOURCE_MISSING: %s" % token
for token in ("_name = \"ya.sale.capacity.reservation\"",
              "UNIQUE(order_id, planning_line_id)",
              "CHECK(qty_required > 0)", "def unlink(self):",
              "ya_sale_confirm_slot_locked"):
    assert token in ledger, "RESERVATION_LEDGER_GUARD_MISSING: %s" % token
assert "def _ya_confirm_with_protected_capacity(self, delivery_date, slot):" in booking
assert "self._ya_native_confirm_without_early_delivery()" in booking
assert "self._ya_write_locked_capacity_reservations(booking)" in booking
assert "return order._ya_confirm_with_protected_capacity(" in wizard
assert 'erp-yussyakmal-mrp-test-RO_SO' in source
assert 'CLONE_DB = "erp-yussyakmal-mrp-test-RO_SO"' in booking
assert "lock_ro_slot(self.env.cr, delivery_date, slot)" in booking
assert "self.env.cr.commit()" not in booking
print("CAPACITY_LEDGER: atomic YA Confirm wired in clone; production/dispatch not yet wired")
assert "def _ya_native_confirm_without_early_delivery(" in source
assert "skip_procurement=True" in source
assert "_ya_native_confirm_without_early_delivery" not in wizard
assert "('sale', 'done')" in source
assert "def action_cancel(self):" in source
assert "class SaleOrderLine(models.Model):" in source
wizard_view = (addon / "views/ya_sale_confirm_wizard_views.xml").read_text(encoding="utf-8")
assert 'Confirm Sales Order — Reservasi Kapasitas' in wizard_view
assert 'Confirm Belum Aktif' not in wizard_view
print("YA_NATIVE_DELIVERY: skip_procurement and zero-stock-move postcheck; YA SO mutations locked")
print("INSTALL_STATUS: SOURCE_ONLY_NOT_PROVEN; CLONE ROLLBACK TEST REQUIRED")
