"""Source preflight only: no Odoo, no database, no runtime claims."""
import ast
from pathlib import Path
import xml.etree.ElementTree as ET

root=Path("addons/ya_sale_production_capacity")
for p in root.rglob("*.py"):
    ast.parse(p.read_text(),filename=str(p))
for p in root.rglob("*.xml"):
    ET.parse(p)
assert ast.literal_eval((root/"__manifest__.py").read_text())["version"]=="19.0.1.21.1"
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
print("FASE2_CLOSING_SOURCE_PREFLIGHT_PASS")
print("SOURCE_ONLY_NO_DATABASE_NO_DEPLOY")
