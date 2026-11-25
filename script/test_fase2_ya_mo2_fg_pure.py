"""Standalone pure tests: MO2 DONE output -> kitchen stock -> PCK Qty.

No Odoo environment, PostgreSQL, stock moves or manifest upgrades.
"""
import importlib.util
from pathlib import Path

path = Path(
    "addons/ya_sale_production_capacity/models/mo2_finished_goods_rules.py"
)
spec = importlib.util.spec_from_file_location("mo2_finished_goods_rules_ya", path)
rules = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rules)
calc = rules.plan_mo2_finished_goods_handoff
Reject = rules.Mo2FinishedGoodsError


def rejects(kwargs, explanation):
    try:
        calc(**kwargs)
    except Reject:
        return
    raise AssertionError("EXPECTED_REJECT: " + explanation)


def request(plan, moves, physical, reserved=0):
    return {
        "planned_mo2_qty": plan,
        "finished_move_quantities": moves,
        "exact_kitchen_stock": physical,
        "exact_kitchen_reserved": reserved,
    }


full = calc(**request(24, [24], 30, 2))
assert full["transfer_qty"] == 24
assert full["free_source_qty_after_handoff"] == 4
print("MO2_DONE_FINISHED_OUTPUT_TRANSFER_PASS")

partial = calc(**request(24, [10, 2], 30))
assert partial["transfer_qty"] == 12
assert partial["planned_mo2_qty"] == 24
print("MO2_PARTIAL_ACTUAL_OUTPUT_NOT_PLANNED_QTY_PASS")

rejects(request(24, [25], 100), "MO2 actual over released capacity")
rejects(request(24, [24], 20), "physical stock insufficient")
rejects(request(180, [180], 30), "historical 180 DONE, only 30 source stock")
rejects(request(24, [24], 30, 10), "free after reservation is insufficient")
rejects(request(24, [24], 20, 21), "inconsistent reserved greater than stock")
rejects(request(24, [], 30), "no real finished move")
rejects(request(24, [0], 30), "zero production")
rejects(request(24, [1.5], 30), "fractional finished Qty")
rejects(request(24, [float("nan")], 30), "NaN")
rejects(request(24, [float("inf")], 30), "Inf")
rejects(request(24, [True], 30), "boolean Qty")
rejects(request(0, [1], 30), "no released MO2")
print("MO2_PHYSICAL_FREE_STOCK_AND_CAPACITY_GUARDS_PASS")

print("FASE2_YA_MO2_FG_PURE_PASS")
print("SCOPE: SOURCE_PURE_ONLY; NO NATIVE FG PICKING, STOCK OR DO")
