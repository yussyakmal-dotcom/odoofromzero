"""Pure rules for controlled Published Planning revision."""

def validate_revision(old, new, batch, *, ro, so, locked, delete=False, referenced=False):
    for value in (old, new, batch, ro, so):
        if type(value) is not int or value < 0:
            raise ValueError("Quantities must be nonnegative whole integers")
    if not batch or new % batch or new > 2147483647:
        raise ValueError("Max must be a valid BoM multiple")
    if locked:
        raise ValueError("PP1 already staged/released: revision blocked")
    if delete:
        if ro or so or referenced:
            raise ValueError("Referenced SKU cannot be deleted")
        return
    if so and (new < old or new < so):
        raise ValueError("SO committed: Max may only increase")
    # Current PP1 ignores zero-Max routes; do not silently lose committed RO.
    if ro and new == 0:
        raise ValueError("Zero Max with committed RO requires PP1 zero-route support")
