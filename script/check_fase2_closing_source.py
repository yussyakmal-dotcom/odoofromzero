"""Source preflight only: no Odoo, no database, no runtime claims."""
import ast
from pathlib import Path
import xml.etree.ElementTree as ET

root=Path("addons/ya_sale_production_capacity")
for p in root.rglob("*.py"):
    ast.parse(p.read_text(),filename=str(p))
for p in root.rglob("*.xml"):
    ET.parse(p)
assert ast.literal_eval((root/"__manifest__.py").read_text())["version"]=="19.0.1.21.7"
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
print("FASE2_CLOSING_SOURCE_PREFLIGHT_PASS")
print("SOURCE_ONLY_NO_DATABASE_NO_DEPLOY")
