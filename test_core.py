import unittest
from calculator import evaluate, format_engineering, format_measurement, format_number
from conversions import convert, parse_conversion_input

class CalculatorTests(unittest.TestCase):
    def test_precedence(self): self.assertEqual(evaluate("2 + 3 * (4 - 1)"), 11)
    def test_power_alias(self): self.assertEqual(evaluate("2^8"), 256)
    def test_rejects_code(self):
        with self.assertRaises(ValueError): evaluate("__import__('os')")
    def test_format(self): self.assertEqual(format_number(5.0), "5")
    def test_measurement_precision_by_unit(self):
        self.assertEqual(format_measurement(0.30219931418, "mm"), "0.302")
        self.assertEqual(format_measurement(11.8976267, "mil"), "11.9")
        self.assertEqual(format_measurement(3.14159265, "V"), "3.14159")
    def test_engineering_notation(self):
        self.assertEqual(format_engineering(.0047,3),"4.7e-3")
    def test_square_root(self): self.assertEqual(evaluate("sqrt(144)"), 12)
    def test_visual_square_root(self): self.assertEqual(evaluate("√(144)"), 12)
    def test_nth_root(self): self.assertEqual(evaluate("root(81, 4)"), 3)
    def test_visual_nth_root(self): self.assertEqual(evaluate("ⁿ√(81, 4)"), 3)
    def test_mathlive_nth_root(self): self.assertEqual(evaluate("root(4)(81)"), 3)
    def test_integral(self): self.assertAlmostEqual(evaluate("integral(x^2, 0, 3)"), 9, places=7)
    def test_derivative(self): self.assertAlmostEqual(evaluate("derivative(x^3, 2)"), 12, places=5)
    def test_summation(self): self.assertEqual(evaluate("summation(x^2, 1, 3)"), 14)
    def test_factorial(self): self.assertEqual(evaluate("factorial(6)"), 720)
    def test_logarithms(self): self.assertEqual(evaluate("log(1000) + ln(e)"), 4)
    def test_mathlive_log_base(self): self.assertEqual(evaluate("log _2(8)"), 3)
    def test_trigonometry(self): self.assertAlmostEqual(evaluate("sin(pi / 2)"), 1)
    def test_named_variables(self): self.assertEqual(evaluate("Vin / 2", {"Vin":24}), 12)
    def test_rejects_unknown_function(self):
        with self.assertRaises(ValueError): evaluate("open('/tmp/nope')")
    def test_rejects_empty_visual_box(self):
        with self.assertRaisesRegex(ValueError, "Fill in every"):
            evaluate("√(□)")

class ConversionTests(unittest.TestCase):
    def test_pico_to_micro(self): self.assertAlmostEqual(convert(1_000_000, "Length", "Picometer (pm)", "Micrometer (µm)"), 1)
    def test_metric_to_us(self): self.assertAlmostEqual(convert(1, "Length", "Meter (m)", "Foot (ft)"), 3.280839895, places=8)
    def test_us_to_us(self): self.assertAlmostEqual(convert(3, "Length", "Foot (ft)", "Yard (yd)"), 1)
    def test_temperature(self): self.assertAlmostEqual(convert(212, "Temperature", "Fahrenheit (°F)", "Celsius (°C)"), 100)
    def test_typed_source_unit(self):
        self.assertAlmostEqual(convert("12 in","Length","Meter (m)","Foot (ft)"),1)
        value,source,explicit=parse_conversion_input("3/8 in","Length","Millimeter (mm)")
        self.assertEqual((value,source,explicit),(.375,"Inch (in)",True))

if __name__ == "__main__": unittest.main()
