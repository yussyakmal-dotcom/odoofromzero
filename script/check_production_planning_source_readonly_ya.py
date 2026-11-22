"""Static, read-only source preflight for YA Production Planning.
Run from ~/odoofromzero, before deploying or installing the addon.
No Odoo database access, no Python bytecode writes, no mutations.
"""
import ast
import pathlib
import re
import sys
import xml.etree.ElementTree as ET

root = pathlib.Path.cwd() / "addons" / "ya_production_planning"
required = [
    "__init__.py", "__manifest__.py", "models/__init__.py",
    "models/planning.py", "models/capacity_rules.py", "wizard/__init__.py", "wizard/planning_import.py",
    "security/ir.model.access.csv", "views/planning_views.xml",
    "views/import_wizard_views.xml",
]
print("MODE: SOURCE_READ_ONLY_PREFLIGHT")
print("ADDON_DIR:", root)
errors = []
for relative in required:
    path = root / relative
    if not path.is_file():
        errors.append("MISSING: " + relative)
        continue
    source = path.read_text(encoding="utf-8")
    if relative.endswith(".py"):
        try:
            compile(source, str(path), "exec")
        except SyntaxError as exc:
            errors.append("PYTHON_ERROR: %s: %s" % (relative, exc))
    elif relative.endswith(".xml"):
        try:
            ET.fromstring(source)
        except ET.ParseError as exc:
            errors.append("XML_ERROR: %s: %s" % (relative, exc))
    print("FOUND:", relative, len(source.encode("utf-8")), "bytes")

manifest_path = root / "__manifest__.py"
if manifest_path.is_file():
    try:
        manifest = ast.literal_eval(manifest_path.read_text(encoding="utf-8"))
        print("MANIFEST_VERSION:", manifest.get("version"))
        print("MANIFEST_DEPENDS:", manifest.get("depends"))
        print("MANIFEST_FILES:", manifest.get("data"))
        for item in manifest.get("data", []):
            if not (root / item).is_file():
                errors.append("MANIFEST_DATA_MISSING: " + item)
    except Exception as exc:
        errors.append("MANIFEST_ERROR: " + repr(exc))

wizard = root / "wizard" / "planning_import.py"
if wizard.is_file():
    source = wizard.read_text(encoding="utf-8")
    if "PRODUCT_RE = re.compile(r'^\\[([^\\[\\]]+)\\]\\s+(.+)$')" not in source:
        errors.append("REFERENCE_REGEX_NOT_EXPECTED")
    if "MAX_BYTES = 10 * 1024 * 1024" not in source:
        errors.append("FILE_LIMIT_MISSING")

print("ERROR_COUNT:", len(errors))
for err in errors:
    print("ERROR:", err)
if errors:
    sys.exit(1)
print("SOURCE_PREFLIGHT_OK")
