import unittest
from engineering import UNITS
from unit_math import evaluate_unit_expression

class UnitMathTests(unittest.TestCase):
    def test_compatible_addition(self):
        value,dimension=evaluate_unit_expression("3 ft + 200 mm",UNITS)
        self.assertEqual(dimension,"length");self.assertAlmostEqual(value.value,1.1144)
    def test_ohms_law_dimensions(self):
        value,dimension=evaluate_unit_expression("12 V / 220 Ω",UNITS)
        self.assertEqual(dimension,"current");self.assertAlmostEqual(value.value,12/220)
    def test_power_dimensions(self):
        value,dimension=evaluate_unit_expression("5 A * 14 V",UNITS)
        self.assertEqual(dimension,"power");self.assertEqual(value.value,70)
    def test_incompatible_addition_rejected(self):
        with self.assertRaisesRegex(ValueError,"compatible"):evaluate_unit_expression("1 m + 2 s",UNITS)

if __name__=="__main__":unittest.main()
