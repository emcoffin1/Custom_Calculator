import unittest
from components import decade_values,preferred_summary,preferred_value


class ComponentTests(unittest.TestCase):
    def test_e24_contains_standard_values(self):
        self.assertIn(4.7,decade_values("E24"));self.assertIn(9.1,decade_values("E24"))
    def test_preferred_directions(self):
        self.assertEqual(preferred_value(4600,"E24"),4700)
        self.assertEqual(preferred_value(4600,"E24","lower"),4300)
        self.assertEqual(preferred_value(4600,"E24","higher"),4700)
    def test_summary_reports_error(self):
        self.assertAlmostEqual(preferred_summary(4600)["error_percent"],100*(4700/4600-1))
    def test_published_high_density_series(self):
        self.assertEqual((len(decade_values("E48")),len(decade_values("E96")),len(decade_values("E192"))),(48,96,192))
        self.assertEqual(decade_values("E192")[83],2.71)


if __name__=="__main__":unittest.main()
