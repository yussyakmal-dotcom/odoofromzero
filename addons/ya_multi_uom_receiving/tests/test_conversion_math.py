import importlib.util
from pathlib import Path
import unittest

path = Path(__file__).resolve().parents[1] / "conversion_math.py"
spec = importlib.util.spec_from_file_location("ya_receipt_math", path)
math = importlib.util.module_from_spec(spec)
spec.loader.exec_module(math)


class TestReceivingMath(unittest.TestCase):
    def test_kg_and_gram(self):
        self.assertEqual(math.sum_base_quantities([(20, 1000), (500, 1)]), 20500)

    def test_three_units_same_sku(self):
        self.assertEqual(math.sum_base_quantities([(20, 120), (3, 12), (5, 1)]), 2441)

    def test_fraction_rejected(self):
        for qty in (0, -1, 1.5, "NaN", "Infinity", "dua"):
            with self.subTest(qty=qty), self.assertRaises(ValueError):
                math.to_base_quantity(qty, 1000)

    def test_invalid_factor_rejected(self):
        for factor in (0, -1, 1.2, "NaN"):
            with self.subTest(factor=factor), self.assertRaises(ValueError):
                math.to_base_quantity(1, factor)

    def test_preserves_large_integer(self):
        self.assertEqual(math.to_base_quantity(2500, 1000), 2500000)


if __name__ == "__main__":
    unittest.main()
