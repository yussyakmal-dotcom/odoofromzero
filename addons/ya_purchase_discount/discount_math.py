"""Currency-agnostic discount calculation, independently unit-testable.

An amount entered against a line is a discount on the ENTIRE line, not
per purchased unit. Global amount is distributed proportional to gross value.
Odoo's native discount percentage is the only value fed to tax/bill engines.
"""

from decimal import Decimal, InvalidOperation


def decimal_number(value):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("Invalid discount number") from None
    if not number.is_finite() or number < 0:
        raise ValueError("Discount must be non-negative and finite")
    return number


def effective_percent(kind, value, gross, order_gross=None):
    """Return Odoo native line discount percent; ensure discount <= gross.

    For a global amount, every line gets the same percentage of its gross;
    this is equivalent to a proportional allocation across lines.
    """
    amount = decimal_number(value)
    line_gross = decimal_number(gross)
    if kind == "percent":
        if amount > 100:
            raise ValueError("Discount percentage exceeds 100")
        return float(amount)
    if kind != "amount":
        raise ValueError("Unknown discount kind")
    denominator = decimal_number(order_gross if order_gross is not None else line_gross)
    if amount > denominator:
        raise ValueError("Discount amount exceeds gross value")
    if not denominator:
        if amount:
            raise ValueError("Positive discount on a zero-valued order")
        return 0.0
    return float(amount * 100 / denominator)


def validate_exclusive(mode, global_value, line_values):
    if mode not in ("none", "line", "global"):
        raise ValueError("Invalid discount mode")
    global_amount = decimal_number(global_value)
    has_line = any(decimal_number(value) > 0 for value in line_values)
    if mode == "line" and global_amount:
        raise ValueError("Line and global discounts cannot be combined")
    if mode == "global" and has_line:
        raise ValueError("Line and global discounts cannot be combined")
    if mode == "none" and (has_line or global_amount):
        raise ValueError("Choose a discount mode before entering a discount")
