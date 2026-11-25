"""Pure source rules for an MO2 finished-goods handoff (no Odoo writes).

Values are finished PRODUCT BASE UoM whole units. The native ORM layer must
convert Odoo UoMs before calling this function. Production plan is a ceiling,
not evidence of finished stock. Checked physical/free kitchen stock is the
final transfer limit. Source only until integrated native Odoo rollback PASS.
"""
import math


class Mo2FinishedGoodsError(ValueError):
    pass


def _units(value, name, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise Mo2FinishedGoodsError("%s must be numeric base UoM" % name)
    if not math.isfinite(value):
        raise Mo2FinishedGoodsError("%s must be finite" % name)
    integer = round(value)
    if abs(value - integer) > 1e-7:
        raise Mo2FinishedGoodsError("%s must be whole finished units" % name)
    if integer < 0 or (positive and integer == 0):
        raise Mo2FinishedGoodsError("%s cannot be negative or zero" % name)
    return int(integer)


def plan_mo2_finished_goods_handoff(
        planned_mo2_qty, finished_move_quantities,
        exact_kitchen_stock, exact_kitchen_reserved):
    """Assess one native MO2 with matching DONE finished moves.

    No MO1 is considered in this calculation. An actual finished stock move
    alone cannot prove that its output remains in the kitchen location.
    """
    plan = _units(planned_mo2_qty, "MO2 released Qty", positive=True)
    if not isinstance(finished_move_quantities, (list, tuple)):
        raise Mo2FinishedGoodsError("Finished move quantities need a list")
    done_qty = sum(
        _units(item, "Native Done finished move Qty")
        for item in finished_move_quantities
    )
    physical = _units(exact_kitchen_stock, "Kitchen stock")
    reserved = _units(exact_kitchen_reserved, "Kitchen reserved stock")
    if done_qty == 0:
        raise Mo2FinishedGoodsError("MO2 has no actual Done finished output")
    if done_qty > plan:
        raise Mo2FinishedGoodsError("Actual MO2 output exceeds released Qty")
    if reserved > physical:
        raise Mo2FinishedGoodsError("Kitchen reserved exceeds physical stock")
    if done_qty > physical:
        raise Mo2FinishedGoodsError("Kitchen physical stock insufficient")
    free = physical - reserved
    if done_qty > free:
        raise Mo2FinishedGoodsError("Kitchen free stock insufficient")
    return {
        "planned_mo2_qty": plan,
        "actual_mo2_done_qty": done_qty,
        "physical_source_qty": physical,
        "source_reserved_qty": reserved,
        "free_source_qty_before_handoff": free,
        "transfer_qty": done_qty,
        "free_source_qty_after_handoff": free - done_qty,
    }
