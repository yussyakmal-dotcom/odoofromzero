"""No-DB static preflight for the MO -> kitchen stock -> CDC material audit.

Run locally as Feri: python3 script/check_mo_material_cdc_source_readonly_ya.py
"""
import ast
from pathlib import Path

path = Path(__file__).with_name('audit_mo_material_cdc_readonly_ya.py')
text = path.read_text(encoding='utf-8')
tree = ast.parse(text, filename=str(path))
errors = []
required = (
    "EXPECTED_DB = 'erp-yussyakmal-mrp-test'",
    "TARGET_DELIVERY_DATE = '2026-11-27'",
    "TARGET_SLOT = 'S1'",
    "env.cr.dbname != EXPECTED_DB",
    "mo.move_raw_ids",
    "move.product_uom._compute_quantity(",
    "move.product_id.uom_id",
    "quant.quantity",
    "quant.reserved_quantity",
    "'location_id', 'child_of'",
    "CDC_NOT_UNAMBIGUOUS",
    "AUDIT_READ_ONLY_OK",
    "env.cr.rollback()",
)
for item in required:
    if item not in text:
        errors.append('MISSING: '+item)

# Strict static policy: no ORM stock/purchase/manufacturing writes.
for node in ast.walk(tree):
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr in ('create', 'write', 'unlink', 'action_confirm',
                              'action_assign', 'button_validate',
                              '_action_done', 'action_done', 'commit'):
            errors.append('FORBIDDEN ORM MUTATION: %s at line %s'
                          % (node.func.attr, node.lineno))
    if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
        # Keep audit dependencies to Python standard library; model env is from Odoo shell.
        mods = [x.name for x in node.names] if isinstance(node, ast.Import) else [node.module]
        if any(m != 'collections' for m in mods):
            errors.append('UNNECESSARY IMPORT: '+repr(mods))
print('CHECKED:', path.as_posix())
print('ERROR_COUNT:', len(errors))
for e in errors:
    print(e)
if errors:
    raise SystemExit(1)
print('MO_MATERIAL_CDC_SOURCE_OK')
