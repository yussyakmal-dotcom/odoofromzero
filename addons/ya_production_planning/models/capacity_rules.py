"""Production batch multiple rules used by both XLSX and Draft edits.

All quantities are expressed in the BoM finished-product UoM.
BoM output quantity must be a positive whole number for integer Max.
Exactly halfway between two multiples chooses the lower multiple.
"""
from decimal import Decimal, InvalidOperation


def closest_batch_multiple(requested, bom_quantity):
    try:
        desired = Decimal(str(requested))
        batch = Decimal(str(bom_quantity))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Invalid quantity or BoM output quantity") from exc
    if not desired.is_finite() or not batch.is_finite():
        raise ValueError("Quantities must be finite")
    if desired < 0 or desired != desired.to_integral_value():
        raise ValueError("Max must be a nonnegative whole number")
    if batch <= 0 or batch != batch.to_integral_value():
        raise ValueError("BoM output must be a positive whole number")
    lower_batches = desired // batch
    lower = lower_batches * batch
    upper = lower + batch
    result = lower if desired - lower <= upper - desired else upper
    if result > 2147483647:
        raise ValueError("Adjusted Max exceeds Odoo integer field limit")
    return int(result)
