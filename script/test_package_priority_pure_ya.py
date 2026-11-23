"""Pure safety specification for package-first consolidation. NO Odoo DB use.

This is NOT integrated into YA RO yet; it formalizes owner-approved math.
"""
from collections import defaultdict


def plan_package_first(direct, packages, bom, available=None):
    """Return kitchen gross demand, protected package needs and direct allocation.

    direct: {SKU: direct store RO total}; packages: {Paket SKU: RO Qty};
    bom: {Paket SKU: {component SKU: qty per package}}. All ints.
    available optional actual FG {SKU: quantity}, used to demonstrate priority.
    Procurement types (consignment/packaging) should be filtered by integration
    before passing this function; package assembly still requires all BoM items.
    """
    for mapping in (direct, packages):
        assert all(isinstance(v, int) and not isinstance(v, bool) and v >= 0
                   for v in mapping.values())
    protected = defaultdict(int)
    for package, n in packages.items():
        assert package in bom, ("NO_BOM", package)
        for component, ratio in bom[package].items():
            assert isinstance(ratio, int) and ratio >= 0, ("INVALID_RATIO", component)
            protected[component] += n * ratio
    gross = {sku: direct.get(sku, 0) + protected.get(sku, 0)
             for sku in direct.keys() | protected.keys()}
    result = {"kitchen_gross": gross, "protected_components": dict(protected),
              "direct_ro_demand": dict(direct), "package_ro_demand": dict(packages)}
    if available is not None:
        # Demonstrate a source stock priority, NOT determine how many entire
        # packages can actually be assembled (all-components constraint).
        result["protected_from_stock"] = {
            sku: min(qty, available.get(sku, 0))
            for sku, qty in protected.items()
        }
        result["direct_from_remaining"] = {
            sku: min(qty, max(0, available.get(sku, 0) - protected.get(sku, 0)))
            for sku, qty in direct.items()
        }
    return result


example = plan_package_first({"Y": 10, "Z": 10}, {"X": 5},
                             {"X": {"Y": 1, "Z": 1}})
assert example["kitchen_gross"] == {"Y": 15, "Z": 15}
assert example["protected_components"] == {"Y": 5, "Z": 5}
assert example["direct_ro_demand"] == {"Y": 10, "Z": 10}
example_shortage = plan_package_first(
    {"Y": 10, "Z": 10}, {"X": 5}, {"X": {"Y": 1, "Z": 1}},
    {"Y": 12, "Z": 15},
)
assert example_shortage["protected_from_stock"] == {"Y": 5, "Z": 5}
assert example_shortage["direct_from_remaining"] == {"Y": 7, "Z": 10}
assert plan_package_first({"Y": 10}, {}, {})["kitchen_gross"] == {"Y": 10}
multiple = plan_package_first({"Y": 2}, {"X": 3, "W": 2},
                              {"X": {"Y": 2}, "W": {"Y": 1, "Z": 3}})
assert multiple["kitchen_gross"] == {"Y": 10, "Z": 6}
assert multiple["protected_components"] == {"Y": 8, "Z": 6}
print("PACKAGE_PRIORITY_PURE_RULES_PASS")
print("NOTE: source-only math, no package MO, allocation ORM or stock validated.")
