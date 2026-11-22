"""No Odoo DB access: unit tests for whole-BoM capacity and per-store rationing."""
import importlib.util
from pathlib import Path

source = (Path(__file__).resolve().parents[1] / 'addons' / 'ya_store_ro'
          / 'models' / 'allocation_rules.py')
spec = importlib.util.spec_from_file_location('ya_capacity_prorata_pure', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
calculate = module.allocate_capacity_prorata


def test(requests, bom, max_qty, expected_produced, expected_status,
         expected_shortage):
    produced, rows, status = calculate(requests, bom, max_qty)
    requested = sum(requests.values())
    assert produced == expected_produced, (produced, expected_produced)
    assert status == expected_status, (status, expected_status)
    assert sum(row['allocated'] for row in rows.values()) == produced
    assert sum(row['requested'] for row in rows.values()) == requested
    assert sum(row['shortage'] for row in rows.values()) == expected_shortage
    assert all(row['allocated'] >= 0 and row['shortage'] >= 0
               and row['surplus'] >= 0 for row in rows.values())
    for key, row in rows.items():
        assert row['allocated'] + row['shortage'] == row['requested'] + row['surplus']
    if status == 'prorated':
        assert all(row['allocated'] <= row['requested'] for row in rows.values())
    if status == 'blocked':
        assert produced == 0
    print('PASS:', requests, 'BoM=', bom, 'Max=', max_qty,
          'produced=', produced, 'shortage=', expected_shortage,
          'status=', status)


test({1: 90, 2: 60, 3: 30}, 110, 110, 110, 'prorated', 70)
test({1: 74, 2: 74}, 100, 100, 100, 'prorated', 48)
test({1: 10, 2: 10}, 46, 500, 46, 'ok', 0)
test({1: 10, 2: 10}, 46, 30, 0, 'blocked', 20)
test({1: 20, 2: 27}, 46, 50, 46, 'prorated', 1)
test({10: 0, 4: 5, 8: 5}, 4, 8, 8, 'prorated', 2)
test({1: 0, 2: 0}, 10, 0, 0, 'ok', 0)
print('CAPACITY_PRORATA_TEST_OK')
