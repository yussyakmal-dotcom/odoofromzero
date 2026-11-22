"""Static no-DB checks for capacity prorata plus persisted shortage/UI audit."""
from pathlib import Path
import ast
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1] / 'addons' / 'ya_store_ro'
required = {
    'models/allocation_rules.py': [
        'def allocate_capacity_prorata(requests, bom_output, max_capacity):',
        'available = (max_capacity // bom_output) * bom_output',
        "'blocked'",
        "'prorated'",
        "'shortage': requested - base",
        "assert sum(row['shortage'] for row in result.values()) == total - available",
    ],
    'wizard/packing_preview.py': [
        'allocate_capacity_prorata(',
        "if capacity_status == 'blocked':",
        "elif capacity_status == 'prorated':",
        "'qty_shortage': shortage",
        "'qty_shortage': a['shortage']",
        "qty_shortage = fields.Integer(",
        'accept_shortage = fields.Boolean(',
        'if self.prorated_count and not self.accept_shortage:',
        "'qty_shortage': row.qty_shortage",
        "'qty_shortage': allocation.qty_shortage",
        "if any(a['surplus'] for a in allocations.values()):",
        "'total_unallocated': total_unallocated",
    ],
    'models/packing_batch.py': [
        "qty_shortage = fields.Integer(",
        "sum(rows.mapped('qty_shortage')) != line.qty_shortage",
        "allocation.qty_allocated + allocation.qty_shortage !=",
        "allocation.qty_surplus != 0",
        "line.qty_surplus",
    ],
    'views/packing_preview_views.xml': [
        'class="alert alert-warning"',
        'PRORATA KAPASITAS:',
        'name="total_shortage"',
        'name="prorated_count"',
        'name="accept_shortage"',
        'name="qty_shortage"',
        'name="total_unallocated"',
        'Selisih BoM Belum Dialokasikan',
        "decoration-warning=\"capacity_status == 'prorated'\"",
    ],
    'views/packing_batch_views.xml': [
        'name="qty_shortage"',
    ],
    '__manifest__.py': [
        "'version': '19.0.8.1.0'",
    ],
}
errors = []
for path, tokens in required.items():
    file = root / path
    if not file.exists():
        errors.append('MISSING FILE: '+path)
        continue
    content = file.read_text(encoding='utf8')
    for token in tokens:
        if token not in content:
            errors.append('MISSING TOKEN: %s :: %s' % (path, token))
    try:
        if file.suffix == '.py':
            ast.parse(content, filename=str(file))
        elif file.suffix == '.xml':
            ET.parse(file)
    except (SyntaxError, ET.ParseError) as exc:
        errors.append('SOURCE INVALID: %s: %s' % (path, exc))
    print('SOURCE_CHECK:', path)
print('ERROR_COUNT:', len(errors))
for error in errors:
    print(error)
if errors:
    raise SystemExit(1)
print('CAPACITY_PRORATA_SOURCE_OK')
