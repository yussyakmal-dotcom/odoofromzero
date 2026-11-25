"""Source gate for YA Sales v19.0.1.1.3 MO2/CDC/FG staged source, no GUI activation."""
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
    addon / "models/mo2_priority_rules.py",
    addon / "models/mo2_release.py",
    addon / "models/mo2_material_wave.py",
    addon / "models/mo2_finished_goods_rules.py",
    addon / "models/mo2_finished_goods_wave.py",
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
assert manifest["version"] == "19.0.1.1.3", "UNEXPECTED_ADDON_VERSION"
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
    "model_ya_sale_mo2_finalization",
    "model_ya_sale_mo2_release_line",
}
assert len(acl_rows) == 5, "ACL_EXPECTED_TWO_WIZARDS_PLUS_THREE_READ_ONLY_MODELS"
assert {row["model_id:id"] for row in acl_rows} == expected_wizard_models, "ACL_WIZARD_MODELS_MISMATCH"
for row in acl_rows:
    if row["model_id:id"] in {
        "model_ya_sale_capacity_reservation",
        "model_ya_sale_mo2_finalization",
        "model_ya_sale_mo2_release_line",
    }:
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
mo2 = (addon / "models/mo2_release.py").read_text(encoding="utf-8")
mo2_init = (addon / "models/__init__.py").read_text(encoding="utf-8")
for token in ("class YaSaleMo2Finalization(", "class YaSaleMo2ReleaseLine(",
              "class YaPackingBatchMo2Release(", "UNIQUE(batch_id)",
              "UNIQUE(planning_line_id)", "UNIQUE(mo_id)",
              "def _ya_prepare_mo2_final_release(self):",
              "def _ya_release_final_mo2(self):",
              "lock_ro_slot(self.env.cr, self.delivery_date, self.slot)",
              "calculate_mo2_release(", 'self.env["mrp.production"].create({',
              'S2/S3 has not been approved',
              "ya_store_delivery_ids", "ya_fg_transfer_ids",
              "ya_package_assembly_mo_ids", "qty_ro_package",
              "qty_ro_direct", "ya_packing_batch_line_id"):
    assert token in mo2, "MO2_NATIVE_SOURCE_GUARD_MISSING: %s" % token
assert "from . import mo2_release" in mo2_init
assert "ya_packing_batch_line_id" in mo2
assert "env.cr.commit()" not in mo2
assert '"ya_packing_batch_line_id":' not in mo2, "MO2_MUST_NOT_LINK_TO_MO1_UNIQUE_FIELD"
assert "_ya_release_final_mo2" not in wizard, "NO_EARLY_MO2_RELEASE_BY_SALES_CONFIRM"
assert "def action_release_mo2(" not in mo2, "NO_GUI_MO2_BUTTON_UNTIL_QA"
cdc = (addon / "models/mo2_material_wave.py").read_text(encoding="utf-8")
for token in ('_inherit = "stock.picking"',
              "UNIQUE(ya_mo2_material_release_line_id)",
              "def _ya_create_mo2_cdc_transfer(self):",
              "lock_ro_slot(self.env.cr, batch.delivery_date, batch.slot)",
              "mo.move_raw_ids", "product_uom_qty",
              '"origin": origin', "stock.group_stock_manager",
              "erp-yussyakmal-mrp-test-RO_SO"):
    assert token in cdc, "MO2_CDC_SOURCE_GUARD_MISSING: %s" % token
assert "from . import mo2_material_wave" in mo2_init
assert not any(x in cdc for x in (
    "env.cr.commit()", ".button_validate(", "stock.quant'].create(",
    '"ya_mr_batch_id":', '"ya_mr_kitchen_id":',
    '"ya_fg_batch_id":', '"ya_fg_kitchen_id":',
)), "MO2_CDC_MUST_NOT_AUTO_VALIDATE_OR_REUSE_FASE1_LINKS"
print("MO2_CDC_MATERIAL: separate native picking per MO2; no stock validate,"
      " no reuse of Fase1 batch/kitchen link")
fg_rules = (addon / "models/mo2_finished_goods_rules.py").read_text(encoding="utf-8")
fg = (addon / "models/mo2_finished_goods_wave.py").read_text(encoding="utf-8")
for token in (
    "def plan_mo2_finished_goods_handoff(",
    "exact_kitchen_stock", "exact_kitchen_reserved",
    "Actual MO2 output exceeds released Qty",
    "Kitchen free stock insufficient",
):
    assert token in fg_rules, "MO2_FG_PURE_SOURCE_MISSING: %s" % token
for token in (
    'ya_mo2_fg_release_line_id = fields.Many2one(',
    "UNIQUE(ya_mo2_fg_release_line_id)",
    "def _ya_create_mo2_fg_transfer(self):",
    "lock_ro_slot(self.env.cr, batch.delivery_date, batch.slot)",
    'mo.state != "done"', "mo.move_finished_ids.filtered(",
    'move.state == "done"', "plan_mo2_finished_goods_handoff(",
    'product.tracking != "none"', "ya_mo2_material_picking_ids",
    'materials.state != "done"', "ya_store_delivery_ids",
    'batch.ya_package_assembly_mo_ids', "self.env.cr.execute(",
    "ya_finished_packing_transfer.exclude_sku_codes",
    '"origin": origin',
):
    assert token in fg, "MO2_FG_NATIVE_SOURCE_MISSING: %s" % token
assert "from . import mo2_finished_goods_wave" in mo2_init
assert not any(x in fg for x in (
    "env.cr.commit()", ".button_validate(", ".action_confirm(",
    '"ya_fg_batch_id":', '"ya_fg_kitchen_id":',
    '"ya_store_batch_id":', '"ya_mr_batch_id":',
)), "MO2_FG_MUST_NOT_POST_OR_OVERWRITE_PHASE1"
assert "def action_mo2_fg_" not in fg
print("MO2_FG_SOURCE: separate unique native draft picking per DONE MO2;"
      " exact kitchen free stock; no confirm/validate/DO; original MO1 unchanged")

print("MO2_NATIVE: separate one-time date-slot finalization and mrp.production "
      "source staged; MO1 and Fase1 unchanged")
print("INSTALL_STATUS: SOURCE_ONLY_NOT_PROVEN; CLONE_NATIVE_MO2_ROLLBACK_REQUIRED")
