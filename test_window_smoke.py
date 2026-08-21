"""Opt-in GTK callback smoke tests: CALCULATOR_RUN_GTK_TESTS=1."""
import os
import unittest

@unittest.skipUnless(os.environ.get("CALCULATOR_RUN_GTK_TESTS")=="1","GTK smoke tests are opt-in")
class WindowSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import app
        cls.app=app;app.STATE_FILE="/tmp/conversions-calculator-gtk-test.json"
        try:os.unlink(app.STATE_FILE)
        except FileNotFoundError:pass
        cls.window=app.CalculatorWindow();cls.window.show_all()

    def pick(self,combo,text):
        values=[combo.get_model()[i][0] for i in range(len(combo.get_model()))];combo.set_active(values.index(text))

    def test_live_and_button_callbacks(self):
        w=self.window;self.pick(w.engineering_discipline,"Electrical");self.pick(w.engineering_calculation,"Ohm’s law")
        w.engineering_fields["v"][0].set_text("");w.engineering_fields["i"][0].set_text("2");w.engineering_fields["r"][0].set_text("5")
        self.assertEqual(w.engineering_result.get_text(),"Voltage: 10 V")
        self.pick(w.engineering_calculation,"LED current resistor")
        w.engineering_fields["supply"][0].set_text("12");w.engineering_fields["forward"][0].set_text("2");w.engineering_fields["current"][0].set_text("0.02")
        w.engineering_actions.get_children()[0].clicked();self.assertIn("500 Ω",w.engineering_result.get_text())
        self.pick(w.engineering_output_unit,"kΩ");self.assertIn("0.5 kΩ",w.engineering_result.get_text())

    def test_favorites_group(self):
        w=self.window;self.pick(w.engineering_discipline,"Electrical");self.pick(w.engineering_calculation,"Ohm’s law")
        if not w.engineering_favorite_button.get_active():w.engineering_favorite_button.clicked()
        self.pick(w.engineering_discipline,"Favorites")
        self.assertIn("Ohm’s law",[w.engineering_calculation.get_model()[i][0] for i in range(len(w.engineering_calculation.get_model()))])

    def test_unit_math_and_wire_chart(self):
        w=self.window;w.basic_expression.set_text("12 V / 220 Ω");w.calculate_math(w.basic_expression,w.basic_result)
        self.assertEqual(w.basic_result.get_text(),"54.5455 mA")
        self.pick(w.engineering_calculation,"Wire sizing & voltage drop")
        chart=next(button for button in w.engineering_actions.get_children() if button.get_label()=="AWG chart");chart.clicked()
        self.assertTrue(hasattr(w,"_wire_chart_popover"))

if __name__=="__main__":unittest.main()
