"""Pure integer calculations for receipt units; no Odoo dependency."""
from decimal import Decimal, InvalidOperation


def to_base_quantity(quantity, factor):
    try:
        q = Decimal(str(quantity))
        f = Decimal(str(factor))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError("Quantity and factor must be valid integers") from exc
    if not q.is_finite() or not f.is_finite():
        raise ValueError("Quantity and factor must be finite")
    if q <= 0 or q != q.to_integral_value():
        raise ValueError("Receipt quantity must be a positive integer")
    if f <= 0 or f != f.to_integral_value():
        raise ValueError("Conversion factor must be a positive integer")
    return int(q) * int(f)


def sum_base_quantities(lines):
    """lines: iterable of (quantity, factor). Multiple units per SKU allowed."""
    return sum(to_base_quantity(q, f) for q, f in lines)
