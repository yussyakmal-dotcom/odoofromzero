"""Source preflight only: no Odoo, no database, no runtime claims."""
import ast
from pathlib import Path
import xml.etree.ElementTree as ET

root=Path("addons/ya_sale_production_capacity")
for p in root.rglob("*.py"):
    ast.parse(p.read_text(),filename=str(p))
for p in root.rglob("*.xml"):
    ET.parse(p)
assert ast.literal_eval((root/"__manifest__.py").read_text())["version"]=="19.0.1.21.0"
src=(root/"models/closing_lifecycle.py").read_text()
assert 'DEFAULT = {"pp1": "scheduled", "pp2": "manual"}' in src
assert "def button_mark_done" in src and "def _post_inventory" in src
assert "old_closed" in (root/"models/consolidation_cutoff_gate.py").read_text()
print("FASE2_CLOSING_SOURCE_PREFLIGHT_PASS")
print("SOURCE_ONLY_NO_DATABASE_NO_DEPLOY")
