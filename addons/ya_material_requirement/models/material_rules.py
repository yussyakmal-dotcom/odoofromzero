"""Pure diagnostic arithmetic for test-mode ingredient shortage estimation.

This logic deliberately returns a range because stock.quant.reserved_quantity
may already include reservation of raw moves from these same MOs.
Do not use either bound to create/validate stock transfer automatically.
"""


def shortage_bounds(requirement, on_hand, reserved):
    """Return (physical, free, min_missing, max_missing), in product base UoM."""
    if requirement < 0 or reserved < 0:
        raise ValueError('Requirement and reservation cannot be negative.')
    physical = max(float(on_hand), 0.0)
    free = max(physical - float(reserved), 0.0)
    minimum = max(float(requirement) - physical, 0.0)
    maximum = max(float(requirement) - free, 0.0)
    return physical, free, minimum, maximum


def cdc_shortage_bounds(kitchen_shortages, cdc_free):
    """CDC stock is shared: total shortages across kitchens BEFORE subtracting once."""
    if cdc_free < 0:
        raise ValueError('CDC free stock must not be negative.')
    min_total = sum(float(row[0]) for row in kitchen_shortages)
    max_total = sum(float(row[1]) for row in kitchen_shortages)
    if min_total < 0 or max_total < min_total:
        raise ValueError('Invalid kitchen shortage intervals.')
    return (max(min_total - cdc_free, 0.0),
            max(max_total - cdc_free, 0.0))
