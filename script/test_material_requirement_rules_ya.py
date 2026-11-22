"""Pure-Python no-DB tests: shortage interval and shared CDC capacity arithmetic."""
import importlib.util
from pathlib import Path

source = (Path(__file__).resolve().parents[1] /
          'addons/ya_material_requirement/models/material_rules.py')
spec = importlib.util.spec_from_file_location('ya_material_rules_pure', source)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def test(need, on_hand, reserved, expected):
    result = m.shortage_bounds(need, on_hand, reserved)
    assert result == expected, (need, on_hand, reserved, result, expected)
    print('PASS_KITCHEN:', need, on_hand, reserved, '->', result)


test(100, 0, 0, (0, 0, 100, 100))
test(100, 30, 0, (30, 30, 70, 70))
test(100, 100, 40, (100, 60, 0, 40))
test(100, 200, 50, (200, 150, 0, 0))
test(100, -10, 0, (0, 0, 100, 100))
test(100, 50, 100, (50, 0, 50, 100))


def cdc(rows, free, expected):
    result = m.cdc_shortage_bounds(rows, free)
    assert result == expected, (rows, free, result, expected)
    print('PASS_CDC:', rows, 'CDC free:', free, '->', result)


# Same CDC stock cannot be reused for separate kitchen rows.
cdc([(80, 80), (50, 50)], 100, (30, 30))
cdc([(80, 80), (50, 50)], 0, (130, 130))
cdc([(0, 40), (0, 20)], 30, (0, 30))
cdc([(0, 0), (0, 0)], 0, (0, 0))
print('MATERIAL_REQUIREMENT_RULES_OK')
