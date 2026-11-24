"""Source-only regression: Packing allocates round-up BoM surplus PRORATA.

When published capacity fits, shops get their original RO plus their share of
all finished output rounding surplus. When capacity is below rounded gross
demand, shops receive prorated shortage, no surplus, and MO remains whole BoM.
Original store RO Qty never changes.
Run: python3 script/test_capacity_prorata_ya.py
"""
import importlib.util
from pathlib import Path

source = Path(__file__).resolve().parents[1] / "addons/ya_store_ro/models/allocation_rules.py"
spec = importlib.util.spec_from_file_location("ya_capacity_prorata_pure", source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
calculate = module.allocate_capacity_prorata


def verify(requests, bom, capacity, expected_mo, expected_status,
           expected_shortage, expected_surplus, expected_allocated=None):
    mo_qty, rows, status = calculate(requests, bom, capacity)
    original = sum(requests.values())
    final = sum(row["allocated"] for row in rows.values())
    shortage = sum(row["shortage"] for row in rows.values())
    surplus = sum(row["surplus"] for row in rows.values())
    assert (mo_qty, status) == (expected_mo, expected_status), (requests, rows, status)
    assert (shortage, surplus) == (expected_shortage, expected_surplus), (requests, rows)
    assert all(row["requested"] == requests[store] for store, row in rows.items())
    assert all(
        row["allocated"] == row["requested"] - row["shortage"] + row["surplus"]
        for row in rows.values()
    ), rows
    assert all(
        row["surplus"] >= 0 and row["shortage"] >= 0 and
        not (row["shortage"] and row["surplus"]) for row in rows.values()
    ), rows
    assert final == mo_qty and original + surplus - shortage == mo_qty, (requests, rows)
    assert mo_qty <= capacity and mo_qty % bom == 0
    if expected_allocated is not None:
        assert {store: row["allocated"] for store, row in rows.items()} == expected_allocated, rows
    assert calculate(dict(reversed(list(requests.items()))), bom, capacity)[1] == rows
    print("PASS:", requests, "BoM", bom, "Max", capacity,
          "MO", mo_qty, "Surplus distributed", surplus,
          "Shortage", shortage, "Store Final", final, "Status", status)


# BO M output 10; orders 4 and 6; rounded output10, no excess.
verify({1: 4, 2: 6}, 10, 10, 10, "ok", 0, 0, {1: 4, 2: 6})
# Owner rule: 15 pcs demand / BoM output 10 => 2 full BoMs = 20pcs;
# distribute all extra 5pcs to shops by largest remainder (requests 6:9).
verify({1: 6, 2: 9}, 10, 20, 20, "ok", 0, 5, {1: 8, 2: 12})
# Unequal stores and lots of extra BoM output.
verify({1: 13, 2: 27, 3: 9}, 24, 72, 72, "ok", 0, 23, {1: 19, 2: 40, 3: 13})
# One ordering shop owns the entire batch rounding surplus; zero RO shop gets zero.
verify({1: 0, 2: 7}, 6, 12, 12, "ok", 0, 5, {1: 0, 2: 12})
verify({3: 1, 1: 1, 2: 1}, 8, 8, 8, "ok", 0, 5, {1: 3, 2: 3, 3: 2})
# Original RO total already exactly a BoM multiple, no surplus.
verify({1: 20, 2: 26}, 46, 100, 46, "ok", 0, 0)
# Explicit capacity shortage: do not distribute surplus; prorata reduce RO.
verify({1: 90, 2: 60, 3: 30}, 110, 110, 110, "prorated", 70, 0)
verify({1: 74, 2: 74}, 100, 100, 100, "prorated", 48, 0)
verify({1: 20, 2: 27}, 46, 50, 46, "prorated", 1, 0)
verify({10: 0, 4: 5, 8: 5}, 4, 8, 8, "prorated", 2, 0)
# Cannot manufacture even one full BoM batch, zero MO, all shops shortage.
verify({1: 10, 2: 10}, 46, 30, 0, "blocked", 20, 0)
# Zero demand must not invent an MO or a store allocation.
verify({1: 0, 2: 0}, 10, 0, 0, "ok", 0, 0)

for requests, batch, maximum in (
    ({1: -1}, 10, 20), ({1: 3}, 0, 20), ({0: 2}, 10, 20),
    ({1: 3.5}, 10, 20), ({1: 3}, 10, -1),
):
    try:
        calculate(requests, batch, maximum)
        raise AssertionError("Expected invalid input: %s" % requests)
    except ValueError:
        pass

print("CAPACITY_SURPLUS_PRORATA_REGRESSION_PASS")
print("SOURCE_ONLY: No Odoo MO, batch, stock or allocation records changed.")
