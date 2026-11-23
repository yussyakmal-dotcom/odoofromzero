"""Pure regression checks; run python3 script/test_kitchen_buffer_rules_ya.py."""
from pathlib import Path
import importlib.util

p = Path(__file__).resolve().parents[1] / "addons/ya_material_requirement/models/kitchen_buffer_rules.py"
spec = importlib.util.spec_from_file_location("kitchen_buffer_rules", p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
calc = mod.buffer_replenishment

def check(expected, **kwargs):
    got = calc(**kwargs)["replenishment_qty"]
    assert abs(got - expected) < 0.000001, (kwargs, got, expected)

# Existing kitchen stock is reused across production; buffers remain overnight.
check(0, open_mo_demand=225, kitchen_on_hand=450,
      incoming_committed=0, buffer_target=100)
# Reserved by these MOs is part of demand, not subtracted from on-hand twice.
check(100, open_mo_demand=500, kitchen_on_hand=400,
      incoming_committed=0, buffer_target=0)
# Outstanding confirmed incoming means no second issue of the same Qty.
check(200, open_mo_demand=500, kitchen_on_hand=0,
      incoming_committed=300, buffer_target=0)
# Buffer still replenished despite fully covered production.
check(150, open_mo_demand=500, kitchen_on_hand=400,
      incoming_committed=300, buffer_target=350)
# Entire kitchen's open MOs, not only currently selected batch.
check(400, open_mo_demand=700, kitchen_on_hand=500,
      incoming_committed=0, buffer_target=200)
# Extra commitments are counted only if independently verified.
check(100, open_mo_demand=100, kitchen_on_hand=300,
      incoming_committed=0, buffer_target=200, other_commitments=100)
for bad in (-1, float("nan"), float("inf")):
    try:
        calc(bad, 0, 0, 0)
        raise AssertionError("Expected ValueError")
    except ValueError:
        pass
print("KITCHEN_BUFFER_RULES_OK")
