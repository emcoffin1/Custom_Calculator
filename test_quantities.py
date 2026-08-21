import unittest
from engineering import UNITS
from quantities import parse_any_quantity, parse_quantity


class QuantityTests(unittest.TestCase):
    def test_selected_unit_is_used_when_omitted(self):
        self.assertAlmostEqual(parse_quantity("12.5", "length", "mm", UNITS).base_value, .0125)

    def test_attached_prefixed_unit(self):
        parsed=parse_quantity("4.7kΩ", "resistance", "Ω", UNITS)
        self.assertEqual(parsed.unit,"kΩ");self.assertEqual(parsed.base_value,4700)

    def test_fractional_inches(self):
        self.assertAlmostEqual(parse_quantity("3/8 in", "length", "mm", UNITS).base_value,.009525)

    def test_micro_alias(self):
        self.assertAlmostEqual(parse_quantity("250 uA", "current", "A", UNITS).base_value,.00025)

    def test_dimension_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ValueError,"not valid for length"):parse_quantity("12 V","length","mm",UNITS)

    def test_percent_tolerance(self):
        parsed=parse_quantity("10 kΩ ±5%","resistance","Ω",UNITS)
        self.assertEqual(parsed.base_value,10000);self.assertEqual(parsed.minimum,9500);self.assertEqual(parsed.maximum,10500)

    def test_absolute_tolerance(self):
        parsed=parse_quantity("12 V +/- 0.2 V","voltage","V",UNITS)
        self.assertAlmostEqual(parsed.minimum,11.8);self.assertAlmostEqual(parsed.maximum,12.2)
    def test_dimensioned_variable(self):
        dimension,stored=parse_any_quantity("24 V",UNITS)
        variables={"Vin":{"base_value":stored.base_value,"dimension":dimension}}
        self.assertEqual(parse_quantity("Vin","voltage","mV",UNITS,variables).base_value,24)
        with self.assertRaisesRegex(ValueError,"not length"):parse_quantity("Vin","length","mm",UNITS,variables)
    def test_absolute_celsius(self):
        parsed=parse_quantity("25 °C","temperature_abs","K",UNITS)
        self.assertAlmostEqual(parsed.base_value,298.15)


if __name__ == "__main__":unittest.main()
