"""Pure-Python, no DB: test YA Production Planning BoM batch rounding.
Run as Feri: python3 script/test_planning_capacity_batch_pure_ya.py
No Odoo import, service, database, or files changed.
"""
from pathlib import Path
import runpy

path = Path(__file__).resolve().parents[1] / "addons" / "ya_production_planning" / "models" / "capacity_rules.py"
round_max = runpy.run_path(str(path))["closest_batch_multiple"]
cases = [
    (50, 24, 48), (70, 24, 72), (100, 24, 96),
    (120, 24, 120), (36, 24, 24), (0, 24, 0),
    (5, 1, 5), (1, 24, 0), (23, 24, 24),
]
for value, batch, expected in cases:
    actual = round_max(value, batch)
    assert actual == expected, (value, batch, actual, expected)
    print("BATCH_CASE_OK:", value, "BoM:", batch, "Adjusted:", actual)
for bad in [(-1, 24), (10, 0), (10, -2), (10, 2.5), (10.4, 2)]:
    try:
        round_max(*bad)
    except ValueError:
        print("BATCH_INVALID_REJECT_OK:", bad)
    else:
        raise AssertionError("Must reject invalid input %s" % (bad,))
print("PLANNING_CAPACITY_BATCH_PURE_OK")
