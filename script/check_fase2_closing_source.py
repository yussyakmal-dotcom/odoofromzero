"""Source preflight only: no Odoo, no database, no runtime claims."""
import ast
from pathlib import Path
import xml.etree.ElementTree as ET

root=Path("addons/ya_sale_production_capacity")
for p in root.rglob("*.py"):
    ast.parse(p.read_text(),filename=str(p))
for p in root.rglob("*.xml"):
    ET.parse(p)
assert ast.literal_eval((root/"__manifest__.py").read_text())["version"]=="19.0.1.22.6"
src=(root/"models/closing_lifecycle.py").read_text()
assert 'DEFAULT = {"pp1": "scheduled", "pp2": "manual"}' in src
assert "def button_mark_done" in src and "def _post_inventory" in src
assert "old_closed" in (root/"models/consolidation_cutoff_gate.py").read_text()
queue=(root/"models/consolidation_timer_queue.py").read_text()
view=(root/"views/consolidation_timer_queue_views.xml").read_text()
assert "def action_refresh_queue" in queue
assert "def _refresh_demand_queue" in queue
assert 'if not current_clock(self.env,day,slot)["ro_closed"]' not in queue
assert 'display="always"' in view
assert 'action="action_ya_consolidation_queue_refresh"' in view
action=ET.fromstring(view).find("./record[@id='action_ya_consolidation_queue_refresh']")
assert action is not None
groups=action.find("./field[@name='group_ids']")
assert groups is not None and "ya_store_ro.group_ya_packing_admin" in groups.attrib["eval"]
print("QUEUE_SERVER_ACTION_GROUP_PREFLIGHT_PASS")
assert 'if clock["expired"]:' in queue
assert "search_default_active_queue" in view
assert "Expired - Gagal Produksi" in queue
assert "now.astimezone(WIB).date()" in (root/"models/consolidation_cutoff_gate.py").read_text()
print("QUEUE_EXPIRY_FILTER_SOURCE_PREFLIGHT_PASS")
assert "PP1 legacy sudah release" in queue
assert "self._prepare_slot(self.delivery_date,self.slot)" in queue
assert "state not in ('ready','waiting')" in view
assert '._prepare_slot(day,slot)' in (root/"wizard/consolidation_review_wizard.py").read_text()
print("QUEUE_RELEASE_STATE_SYNC_SOURCE_PREFLIGHT_PASS")
queue_class=next(n for n in ast.parse(queue).body if isinstance(n,ast.ClassDef) and n.name=="ConsolidationTimerQueue")
refresh=next(n for n in queue_class.body if isinstance(n,ast.FunctionDef) and n.name=="action_refresh_queue")
assert not refresh.decorator_list, "Object button must use recordset dispatch, not api.model"
assert [a.arg for a in refresh.args.args]==["self"]
print("QUEUE_REFRESH_RPC_SIGNATURE_PREFLIGHT_PASS")
display=(root/"models/sales_capacity_display.py").read_text()
assert 'headers[i]=="Status" and v in ("Melebihi Max","Ditutup")' in display
assert '"text-danger fw-bold"' in display
print("SO_STATUS_RED_SOURCE_PREFLIGHT_PASS")
assert '"text-success fw-bold" if headers[i]=="Status" and v=="Tanpa tambah produksi"' in display
assert '"text-warning fw-bold" if headers[i]=="Status" and v=="Tambah produksi"' in display
print("SO_STATUS_GREEN_YELLOW_SOURCE_PREFLIGHT_PASS")
mr_view=(root/"views/mo2_material_views.xml").read_text()
assert "MR1 - Rencana Produksi" in mr_view and "MR2 - Rencana Produksi" in mr_view
assert "MR2 - Kebutuhan Bahan" in mr_view
assert "Siapkan MR2" in mr_view and "Terbitkan Material Requirement" in mr_view
assert "MR1" in (root/"models/mo1_material_integration.py").read_text()
assert "Pengurangan RO Paket" in (root/"views/consolidation_review_views.xml").read_text()
print("MR_STAGE_DISPLAY_ORIGIN_SOURCE_PREFLIGHT_PASS")
mr_base=Path("addons/ya_material_requirement")
for p in mr_base.rglob("*.py"):
    ast.parse(p.read_text(),filename=str(p))
assert ast.literal_eval((mr_base/"__manifest__.py").read_text())["version"]=="19.0.6.1.1"
direct=(mr_base/"models/material_requirement_direct_transfer.py").read_text()
assert "return line.required_qty" in direct
assert direct.count("self._mr_native_demand_qty(line)")==3
policy=(root/"models/mr_stage_policy.py").read_text()
assert "UNIQUE(batch_id,stage)" in policy and "pg_advisory_xact_lock" in policy
assert "decision.facts" in (root/"models/mo2_finished_goods_wave.py").read_text()
assert "ya_full_width_source" in (root/"views/mr_picking_report.xml").read_text()
print("MR_STAGE_MODE_ISSUE_SOURCE_PREFLIGHT_PASS")
register=(root/"models/mr_stage_register.py").read_text()
assert "_auto = False" in register and "UNION ALL" in register
assert "ya_sale_mo2_release_line" in register and "EXISTS" in register
assert 'self.batch_id._ya_mr_open_stage(self.stage)' in register
assert "action_ya_mr_stage_menu" in (root/"views/mr_stage_register_views.xml").read_text()
print("MR_STAGE_REGISTER_SOURCE_PREFLIGHT_PASS")
register_view=(root/"views/mr_stage_register_views.xml").read_text()
assert 'string="Tgl Kirim"' in register_view
assert 'Tanggal Kirim (YYYY-Mon-DD)' not in register_view
assert 'widget="radio" readonly="0"' in mr_view
assert 'return wiz._reopen()' in policy
print("MR_METHOD_SELECTOR_SOURCE_PREFLIGHT_PASS")
mr2=(root/"models/mo2_material_wave.py").read_text()
assert "def _ya_check_grouped_mr2(self, require_picked=True)" in mr2
assert "self._ya_check_grouped_mr2(require_picked=False)" in mr2
assert "if any(self.move_ids.mapped(\"picked\")):" in mr2
assert "m._get_picked_quantity()" in mr2
cls=next(n for n in ast.parse(mr2).body if isinstance(n,ast.ClassDef) and n.name=="StockPickingMo2Material")
done=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=="_action_done")
assert "self._ya_check_grouped_mr2()" in ast.unparse(done)
print("MR2_NATIVE_VALIDATE_PICKED_PREFLIGHT_PASS")
mo_nav=(root/"models/mo_production_navigation.py").read_text()
assert '("ya_packing_batch_line_id", "!=", False)' in mo_nav
assert '("id", "in", lines.mapped("mo_id").ids)' in mo_nav
assert 'if self.env.cr.dbname != DB:' in mo_nav
assert "ya_workflow_navigation.menu_ya_mo_production" in (root/"views/mo_production_navigation_views.xml").read_text()
print("MO_PRODUCTION_MENU_MO1_MO2_PREFLIGHT_PASS")
fg_display=(root/"models/finished_packing_display.py").read_text()
fg_view=(root/"views/finished_packing_display_views.xml").read_text()
assert "mos=mo1|mo2" in fg_display and "ya_fg_total_kitchen_count" in fg_display
assert "move_finished_ids" in fg_display and "ya_mo2_fg_picking_ids" in fg_display
assert "action_open_packing_queue" not in fg_view and "action_open_packing_preproduction" not in fg_view
assert "action_ya_fg_move_to_packing" in fg_view and "action_ya_final_packing_review" in fg_view
assert "def action_ya_fg_move_to_packing" not in fg_display
assert "ya_finished_packing_transfer.ya_fg_packing_batch_action" in fg_display
print("FG_MO1_MO2_DISPLAY_SOURCE_PREFLIGHT_PASS")
print("FASE2_CLOSING_SOURCE_PREFLIGHT_PASS")
print("SOURCE_ONLY_NO_DATABASE_NO_DEPLOY")
