"""Run BEFORE installation: python3 -m unittest discover -s .../tests -v."""

import importlib.util
from pathlib import Path
import unittest


source = Path(__file__).resolve().parents[1] / "discount_math.py"
spec = importlib.util.spec_from_file_location("ya_discount_math_test", source)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class TestDiscountMath(unittest.TestCase):
    def test_line_percent(self):
        self.assertEqual(mod.effective_percent("percent", 10, 100_000), 10)

    def test_line_rupiah_applies_to_entire_line(self):
        self.assertEqual(mod.effective_percent("amount", 20_000, 200_000), 10)

    def test_global_rupiah_allocated_proportionally(self):
        # 30k discount on total 300k => 10% on each line.
        self.assertEqual(mod.effective_percent("amount", 30_000, 100_000, 300_000), 10)
        self.assertEqual(mod.effective_percent("amount", 30_000, 200_000, 300_000), 10)

    def test_global_percent(self):
        self.assertEqual(mod.effective_percent("percent", 5, 200_000, 300_000), 5)

    def test_exclusive(self):
        mod.validate_exclusive("line", 0, [0, 5000])
        mod.validate_exclusive("global", 10000, [0, 0])
        for mode, global_amount, lines in [
            ("line", 1000, [300]), ("global", 1000, [300]),
            ("none", 0, [1]), ("none", 1, []),
        ]:
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                mod.validate_exclusive(mode, global_amount, lines)

    def test_invalid_numbers(self):
        for val in (-1, "nan", "inf", "invalid"):
            with self.subTest(val=val), self.assertRaises(ValueError):
                mod.effective_percent("amount", val, 100)

    def test_discount_caps(self):
        for kind, amount in [("percent", 101), ("amount", 101)]:
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                mod.effective_percent(kind, amount, 100)

    def test_zero_gross(self):
        self.assertEqual(mod.effective_percent("amount", 0, 0), 0)
        with self.assertRaises(ValueError):
            mod.effective_percent("amount", 1, 0)


if __name__ == "__main__":
    unittest.main()
