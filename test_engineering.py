import math
import unittest
from engineering import best_unit, calculations_for, from_base, network_equivalents, nozzle_exit_state, pcb_width, presets_for, rc_filter_response, recommend_awg, series_rlc_response, standard_atmosphere, to_base, warnings_for, wire_drop, wire_gauge_chart

class EngineeringTests(unittest.TestCase):
    def test_automatic_si_unit_scaling(self):
        self.assertEqual(best_unit(.0047,"current"),"mA")
        self.assertEqual(best_unit(4700,"resistance"),"kΩ")
    def test_presets_are_exposed_as_editable_values(self):
        calc=self.calculation("Electrical","PCB traces")
        self.assertEqual(presets_for(calc)["2 oz copper"]["thickness"],("0.06958","mm"))
    def test_factor_of_safety_warning(self):
        calc=self.calculation("Mechanical","Factor of safety")
        self.assertTrue(warnings_for(calc,{"strength":100,"stress":125},.8))
    def test_expanded_registry_covers_every_discipline(self):
        minimums={"Electrical":20,"Mechanical":10,"Structural":10,"Fluids":8,"Thermal":8,"Propulsion":6}
        for discipline,minimum in minimums.items():self.assertGreaterEqual(len(calculations_for(discipline)),minimum)
    def test_three_phase_power(self):
        calc=self.calculation("Electrical","Three-phase real power")
        self.assertAlmostEqual(calc.compute({"voltage":480,"current":10,"pf":.9}),math.sqrt(3)*4800*.9)
    def test_shaft_torsional_stress(self):
        calc=self.calculation("Mechanical","Shaft torsional stress")
        self.assertAlmostEqual(calc.compute({"torque":100,"diameter":.02}),16*100/(math.pi*.02**3))
    def test_cantilever_deflection(self):
        calc=self.calculation("Structural","Cantilever point-load deflection")
        self.assertAlmostEqual(calc.compute({"force":100,"length":1,"modulus":200e9,"inertia":1e-6}),100/(3*200e9*1e-6))
    def test_darcy_pressure_drop(self):
        calc=self.calculation("Fluids","Darcy–Weisbach pressure drop")
        self.assertAlmostEqual(calc.compute({"factor":.02,"length":10,"diameter":.1,"density":1000,"velocity":2}),4000)
    def test_radiation_uses_absolute_temperature(self):
        calc=self.calculation("Thermal","Radiation heat rate")
        self.assertGreater(calc.compute({"emissivity":.9,"area":1,"surface":373.15,"surroundings":293.15}),0)
    def test_rocket_thrust_includes_pressure_term(self):
        calc=self.calculation("Propulsion","Rocket thrust")
        self.assertEqual(calc.compute({"mass_flow":2,"velocity":2000,"exit_pressure":200000,"ambient_pressure":100000,"exit_area":.01}),5000)
    def test_multi_component_network_rules(self):
        series,parallel=network_equivalents([10,20]);self.assertEqual(series,30);self.assertAlmostEqual(parallel,20/3)
        series,parallel=network_equivalents([10,20],True);self.assertAlmostEqual(series,20/3);self.assertEqual(parallel,30)
    def test_rlc_response_at_resonance(self):
        response=series_rlc_response(10,.01,1e-6,1/(2*math.pi*math.sqrt(.01e-6)))
        self.assertAlmostEqual(response["reactance"],0,places=8);self.assertAlmostEqual(response["magnitude"],10)
    def test_rc_filter_at_cutoff(self):
        response=rc_filter_response(1000,1e-6,1/(2*math.pi*.001))
        self.assertAlmostEqual(response["low_gain"],1/math.sqrt(2))
    def test_nozzle_exit_and_atmosphere(self):
        state=nozzle_exit_state(500000,1000,100000,1.4,287)
        self.assertGreater(state["mach"],1);self.assertGreater(state["velocity"],0)
        sea=standard_atmosphere(0);self.assertAlmostEqual(sea["pressure"],101325);self.assertAlmostEqual(sea["temperature"],288.15)
    def calculation(self, discipline, name):
        return next(item for item in calculations_for(discipline) if item.name == name)
    def test_ohms_law_with_milliamps_and_kilohms(self):
        calc=self.calculation("Electrical","Ohm’s law")
        self.assertEqual(calc.compute({"i":to_base(2,"current","mA"),"r":to_base(5,"resistance","kΩ")}),10)
        self.assertEqual(calc.solvers["r"]({"v":10,"i":.002}),5000)
    def test_voltage_divider_solves_any_missing_value(self):
        calc=self.calculation("Electrical","Voltage divider")
        self.assertEqual(calc.solvers["vout"]({"vin":12,"r1":1000,"r2":1000}),6)
        self.assertEqual(calc.solvers["r1"]({"vin":12,"vout":6,"r2":1000}),1000)
    def test_internal_trace_requires_more_width(self):
        values={"current":1,"rise":10,"thickness":34.79e-6}
        self.assertAlmostEqual(pcb_width(values,.048)/25.4e-6,11.8976267,places=5)
        self.assertGreater(pcb_width(values,.024),pcb_width(values,.048))
    def test_wire_gauge_includes_voltage_drop(self):
        values={"current":10,"length":3,"voltage":12,"drop":3}
        gauge=recommend_awg(values)
        self.assertEqual(gauge,12)
        self.assertLessEqual(wire_drop(values,gauge),.36)
    def test_wire_gauge_chart_uses_copper_geometry(self):
        rows=wire_gauge_chart();row_12=next(row for row in rows if row["gauge"]==12)
        self.assertAlmostEqual(row_12["area_mm2"],3.31,places=1)
        self.assertAlmostEqual(row_12["ohm_per_km"],5.21,places=1)
        self.assertEqual([row["gauge"] for row in rows],sorted((row["gauge"] for row in rows),reverse=True))
    def test_combined_resistance_series_formula(self):
        calc=self.calculation("Electrical","Series / parallel resistance")
        self.assertIn("ΣR",calc.formula)
    def test_rotational_power(self):
        calc=self.calculation("Mechanical","Rotational power")
        watts=calc.compute({"t":10,"w":to_base(60,"rotation","rpm")})
        self.assertAlmostEqual(watts,20*math.pi,places=8)
    def test_axial_stress_output_conversion(self):
        calc=self.calculation("Structural","Axial stress")
        pascals=calc.compute({"f":to_base(10,"force","kN"),"a":to_base(100,"area","mm²")})
        self.assertAlmostEqual(from_base(pascals,"pressure","MPa"),100)
    def test_hydrostatic_pressure(self):
        calc=self.calculation("Fluids","Hydrostatic pressure")
        self.assertAlmostEqual(calc.compute({"rho":1000,"g":9.80665,"h":10}),98066.5)
    def test_sensible_heat(self):
        calc=self.calculation("Thermal","Sensible heat")
        self.assertEqual(calc.compute({"m":2,"c":4184,"dt":10}),83680)

if __name__ == "__main__": unittest.main()
