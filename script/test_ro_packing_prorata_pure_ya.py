"""Pure RO-only Packing consolidation tests. No Odoo import / database access."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

source = Path(__file__).resolve().parents[1] / 'addons/ya_store_ro/models/allocation_rules.py'
spec = spec_from_file_location('ya_ro_allocation_rules', source)
mod = module_from_spec(spec)
spec.loader.exec_module(mod)

cases = [
    ({1: 13, 2: 27, 3: 9}, 24, 72, {1: 19, 2: 40, 3: 13}),
    ({3: 1, 1: 1, 2: 1}, 8, 8, {1: 3, 2: 3, 3: 2}),
    ({1: 0, 2: 7}, 6, 12, {1: 0, 2: 12}),
    ({1: 13, 2: 27, 3: 32}, 24, 72, {1: 13, 2: 27, 3: 32}),
    ({1: 0, 2: 0}, 24, 0, {1: 0, 2: 0}),
    ({2: 1}, 24, 24, {2: 24}),
]
for requests, bom, expected_produced, expected_alloc in cases:
    produced, allocations = mod.allocate_surplus_prorata(requests, bom)
    assert produced == expected_produced, (requests, produced, expected_produced)
    actual = {k: v['allocated'] for k, v in allocations.items()}
    assert actual == expected_alloc, (requests, actual, expected_alloc)
    assert all(v['allocated'] >= v['requested'] for v in allocations.values())
    assert sum(v['surplus'] for v in allocations.values()) == produced - sum(requests.values())
    print('PRORATA_OK:', requests, 'BoM', bom, 'Produced', produced, 'Allocation', actual)

for requests, bom in [({1: -1}, 24), ({1: 4}, 0), ({0: 1}, 24), ({1: 1.5}, 24)]:
    try:
        mod.allocate_surplus_prorata(requests, bom)
    except ValueError:
        print('INVALID_REJECT_OK:', requests, bom)
    else:
        raise AssertionError('Expected ValueError: %s %s' % (requests, bom))
print('RO_PACKING_PRORATA_PURE_OK')
