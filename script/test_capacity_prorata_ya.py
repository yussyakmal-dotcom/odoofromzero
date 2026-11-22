"""Pure Python no-DB regression tests: preview prorates store SHORTAGES, never future surplus.

Run from repository root: python3 script/test_capacity_prorata_ya.py
"""
import importlib.util
from pathlib import Path

source = (Path(__file__).resolve().parents[1] / 'addons' / 'ya_store_ro'
          / 'models' / 'allocation_rules.py')
spec = importlib.util.spec_from_file_location('ya_capacity_prorata_pure', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
calculate = module.allocate_capacity_prorata


def test(requests, bom, max_qty, expected_mo, expected_status, shortage, gap):
    planned_mo, rows, status = calculate(requests, bom, max_qty)
    total = sum(requests.values())
    allocated = sum(row['allocated'] for row in rows.values())
    assert planned_mo == expected_mo, (planned_mo, expected_mo)
    assert status == expected_status, (status, expected_status)
    assert total - allocated == shortage
    assert planned_mo - allocated == gap
    assert sum(row['requested'] for row in rows.values()) == total
    assert sum(row['shortage'] for row in rows.values()) == shortage
    assert all(
        row['surplus'] == 0 and
        row['requested'] == row['allocated'] + row['shortage'] and
        0 <= row['allocated'] <= row['requested']
        for row in rows.values()
    ), rows
    if status == 'ok':
        assert rows == {sid: {'requested': qty, 'surplus': 0,
                              'shortage': 0, 'allocated': qty}
                        for sid, qty in requests.items()}
    elif status == 'prorated':
        assert planned_mo <= max_qty and planned_mo % bom == 0
        assert shortage > 0 and gap == 0
    else:
        assert status == 'blocked' and planned_mo == 0
    assert calculate(dict(reversed(list(requests.items()))), bom, max_qty)[1] == rows
    print('PASS:', requests, 'BoM:', bom, 'Max:', max_qty,
          'MO plan:', planned_mo, 'store qty:', allocated,
          'shortage:', shortage, 'unallocated BoM gap:', gap,
          'status:', status)


# Demand > Max: proportionally REDUCE each store's original Qty.
test({1: 90, 2: 60, 3: 30}, 110, 110, 110, 'prorated', 70, 0)
test({1: 74, 2: 74}, 100, 100, 100, 'prorated', 48, 0)
# Demand fits: store Qty unchanged, any future batch rounding is UNALLOCATED.
test({1: 10, 2: 10}, 46, 500, 46, 'ok', 0, 26)
test({1: 20, 2: 26}, 46, 100, 46, 'ok', 0, 0)
# BoM prevents even one batch inside Max: no false solution.
test({1: 10, 2: 10}, 46, 30, 0, 'blocked', 20, 0)
test({1: 20, 2: 27}, 46, 50, 46, 'prorated', 1, 0)
# Unequal and zero demands, stable Hamilton tie-breaking.
test({10: 0, 4: 5, 8: 5}, 4, 8, 8, 'prorated', 2, 0)
test({1: 0, 2: 0}, 10, 0, 0, 'ok', 0, 0)
print('CAPACITY_PRORATA_TEST_OK')
