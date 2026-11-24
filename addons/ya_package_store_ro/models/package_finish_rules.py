"""Pure Paket finished-goods demand accounting — no Odoo or stock side effects.

One MO per final Paket SKU per date/slot. Store DO retains distinct qty
by warehouse. Only positive confirmed Paket RO demand may be included.
"""
from collections import defaultdict


class PackageFinishError(ValueError):
    pass


def group_package_finish_demands(rows):
    """Aggregate original frozen Paket RO rows into MO and store DO quantities.

    rows: [{product_id: int, store_id: int, qty: int}].
    A SKU can appear in multiple stores; it MUST have one MO per slot but
    each store receives exactly its own confirmed quantity.
    """
    assembly = defaultdict(int)
    by_store = defaultdict(lambda: defaultdict(int))
    for row in rows:
        product = row["product_id"]
        store = row["store_id"]
        qty = row["qty"]
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value <= 0
            for value in (product, store, qty)
        ):
            raise PackageFinishError("Paket product/store/Qty must be positive integers")
        assembly[product] += qty
        by_store[store][product] += qty
    mo = dict(sorted(assembly.items()))
    dos = {store: dict(sorted(items.items())) for store, items in sorted(by_store.items())}
    assert sum(mo.values()) == sum(
        sum(items.values()) for items in dos.values()
    )
    return {"assembly_mo_qty": mo, "store_do_qty": dos,
            "total_package_qty": sum(mo.values())}
