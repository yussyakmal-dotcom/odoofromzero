"""Pure, importable CDC physical picking rules (no Odoo dependency).

Actual quantity may exceed the originally printed MO requirement when the
surplus is explicitly declared as Special Transfer to the SAME kitchen.
The supplement never changes MO demand.
"""


def special_extra(requested_qty, picked_qty):
    return max(0.0, float(picked_qty) - float(requested_qty))


def special_issue(requested_qty, picked_qty, flagged, reason, tolerance=0.0):
    """Return a symbolic error code, or None when the exception is valid."""
    requested = float(requested_qty)
    picked = float(picked_qty)
    if requested < 0 or picked < 0:
        return 'negative_quantity'
    is_extra = picked > requested + float(tolerance)
    if is_extra and not flagged:
        return 'missing_special_flag'
    if is_extra and not (reason or '').strip():
        return 'missing_special_reason'
    if flagged and not is_extra:
        return 'flag_without_extra'
    return None


def shared_shortage(actual_quantities, cdc_free_qty, tolerance=0.0):
    """Check CDC pool ONCE after totaling actual picks across kitchens."""
    return max(0.0, sum(float(q) for q in actual_quantities) -
               float(cdc_free_qty) - float(tolerance))
