"""Read-only source preflight for OWNER APPROVED BoM surplus allocation.

Verifies that Planning Max shortages still obey the original RO capacity
controls, while whole kitchen BoM batch rounding surplus is shared prorata
with stores. This only checks source; it does not touch Odoo or substitute
for test DB UAT.
"""
from pathlib import Path
import ast
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1] / "addons" / "ya_store_ro"
required = {
    "models/allocation_rules.py": [
        "def allocate_surplus_prorata(requests, bom_output):",
        "def allocate_capacity_prorata(requests, bom_output, max_capacity):",
        "_, distributed = allocate_surplus_prorata(requests, bom_output)",
        "available = (max_capacity // bom_output) * bom_output",
        "'blocked'", "'prorated'",
        "'shortage': requested - base",
        "assert sum(row['shortage'] for row in result.values()) == total - available",
    ],
    "wizard/packing_preview.py": [
        "from ..models.allocation_rules import allocate_capacity_prorata",
        "allocate_capacity_prorata(",
        "if capacity_status == 'blocked':",
        "elif capacity_status == 'prorated':",
        "'qty_shortage': shortage",
        "'qty_shortage': a['shortage']",
        "'qty_surplus': a['surplus']",
        "total_surplus_distributed += sum(a['surplus'] for a in allocations.values())",
        "'total_surplus_distributed': total_surplus_distributed",
        "if any(a['allocated'] != a['requested'] - a['shortage'] + a['surplus']",
        "'qty_surplus': unallocated",
        "unallocated = produced - allocated_total",
        "if self.prorated_count and not self.accept_shortage:",
    ],
    "models/packing_batch.py": [
        "qty_shortage = fields.Integer(",
        "sum(rows.mapped('qty_shortage')) != line.qty_shortage",
        "allocation.qty_surplus < 0",
        "allocation.qty_requested + allocation.qty_surplus",
        "line.qty_requested + sum(rows.mapped('qty_surplus'))",
        "sum(rows.mapped('qty_allocated')) + line.qty_surplus",
    ],
    "views/packing_preview_views.xml": [
        "name=\"total_shortage\"",
        "name=\"total_surplus_distributed\"",
        "name=\"qty_surplus\"",
        "name=\"qty_allocated\"",
        "name=\"accept_shortage\"",
        "Alokasi Prorata per Toko",
        "Tambahan Surplus BoM",
        "Surplus pembulatan BoM dibagikan otomatis prorata",
    ],
    "views/packing_batch_views.xml": [
        "name=\"qty_shortage\"",
        "name=\"qty_surplus\"",
        "Tambahan Surplus BoM",
        "Jatah Final Toko",
    ],
    "__manifest__.py": [
        "'version': '19.0.8.1.3'",
    ],
}
errors = []
for rel, tokens in required.items():
    file = root / rel
    if not file.exists():
        errors.append("MISSING FILE: " + rel)
        continue
    content = file.read_text(encoding="utf8")
    for token in tokens:
        if token not in content:
            errors.append("MISSING TOKEN: %s :: %s" % (rel, token))
    try:
        if file.suffix == ".py":
            ast.parse(content, filename=str(file))
        elif file.suffix == ".xml":
            ET.parse(file)
    except (SyntaxError, ET.ParseError) as exc:
        errors.append("SOURCE INVALID: %s: %s" % (rel, exc))
    print("SOURCE_CHECK:", rel)
print("ERROR_COUNT:", len(errors))
for error in errors:
    print(error)
if errors:
    raise SystemExit(1)
print("CAPACITY_SURPLUS_PRORATA_SOURCE_OK")
