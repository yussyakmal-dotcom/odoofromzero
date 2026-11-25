"""Source-only deterministic regression tests. Run as feri; no Odoo or DB."""
import importlib.util
from pathlib import Path

path = Path.cwd() / "addons/ya_sale_production_capacity/models/confirm_capacity_math.py"
spec = importlib.util.spec_from_file_location("ya_so_confirm_math", str(path))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
check = mod.check_so_capacity
expand = mod.expand_so_package_requirements


def rejects(fn, *args, **kwargs):
    try:
        fn(*args, **kwargs)
    except mod.CapacityDecisionError:
        return
    raise AssertionError("EXPECTED_CAPACITY_REJECTION: %s" % (fn.__name__,))


# BoM batch 24, Sales 49 -> 72 (not 48).
result = check(49, 0, 72, 24)
assert result["so_required_batch_output"] == 72
assert result["incremental_mo2_output_needed"] == 72

# RO-driven MO1 production may be reused by SO. No double-count RO+SO.
result = check(30, 0, 72, 24, mo1_output=72)
assert result["incremental_mo2_output_needed"] == 0

# Prior SO 24 + new 25 -> batch total 72. MO1=48, add MO2=24 only.
result = check(25, 24, 72, 24, mo1_output=48)
assert result["confirmed_so_qty_after"] == 49
assert result["incremental_mo2_output_needed"] == 24

# Already released output 48+24 meets 49 combined SO.
result = check(25, 24, 72, 24, mo1_output=48, mo2_output=24)
assert result["incremental_mo2_output_needed"] == 0

# SO has priority over RO, but cannot exceed Published Planning Max.
rejects(check, 49, 24, 72, 24)
rejects(check, 25, 24, 48, 24)
rejects(check, 10, 0, 72, 24, mo1_output=72, mo2_output=24)
rejects(check, 10, 0, 70, 24)
rejects(check, 10, 0, 72, 24, slot_open=False)
rejects(check, -1, 0, 72, 24)
rejects(check, 2.5, 0, 72, 24)

# Paket final SKU 900 composed of two kitchen SKUs, plus PCK stock.
p = expand(
    {101: 3}, {900: 6},
    {900: {101: 2, 102: 1, 201: 0.5}},
    {101: "KITCHEN", 102: "KITCHEN", 201: "PCK"},
)
assert p["kitchen_requirements"] == {101: 15, 102: 6}
assert p["pck_stock_requirements"] == {201: 3.0}
rejects(expand, {}, {900: 2}, {900: {101: 1}}, {})
rejects(expand, {}, {900: 1}, {900: {101: 0.5}}, {101: "KITCHEN"})
rejects(expand, {}, {900: 1}, {}, {})

print("FASE2_YA_SO_CONFIRM_CAPACITY_PURE_PASS")
print("CASES: SO batch round-up, MO1 reuse, MO2 increment, combined SO max,")
print("       locked schedule, invalid batch, cross-kitchen Paket/PCK expansion")
print("SCOPE: SOURCE_ONLY; no reservation, Odoo SO confirm, MO, RO, stock, or accounting")
