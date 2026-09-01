"""Unit-aware engineering calculation registry."""
from dataclasses import dataclass
import math
from quantities import parse_quantity

UNITS = {
    "none": {"": 1.0},
    "length": {"m":1, "mm":1e-3, "µm":1e-6, "mil":.0000254, "cm":1e-2, "km":1e3, "in":.0254, "ft":.3048},
    "area": {"m²":1, "mm²":1e-6, "cm²":1e-4, "in²":.00064516, "ft²":.09290304},
    "moment4": {"m⁴":1, "mm⁴":1e-12, "cm⁴":1e-8, "in⁴":.0254**4},
    "mass": {"kg":1, "g":1e-3, "lbm":.45359237},
    "force": {"N":1, "kN":1e3, "lbf":4.4482216153},
    "pressure": {"Pa":1, "kPa":1e3, "MPa":1e6, "bar":1e5, "psi":6894.757293},
    "time": {"s":1, "ms":1e-3, "min":60, "h":3600},
    "speed": {"m/s":1, "km/h":1/3.6, "ft/s":.3048, "mph":.44704},
    "acceleration": {"m/s²":1, "ft/s²":.3048, "g":9.80665},
    "rotation": {"rad/s":1, "rpm":2*math.pi/60},
    "torque": {"N·m":1, "kN·m":1e3, "lbf·ft":1.3558179483},
    "power": {"W":1, "kW":1e3, "MW":1e6, "hp":745.699872},
    "energy": {"J":1, "kJ":1e3, "MJ":1e6, "Wh":3600, "kWh":3.6e6},
    "voltage": {"V":1, "mV":1e-3, "kV":1e3},
    "current": {"A":1, "mA":1e-3, "µA":1e-6},
    "resistance": {"Ω":1, "kΩ":1e3, "MΩ":1e6},
    "capacitance": {"F":1, "mF":1e-3, "µF":1e-6, "nF":1e-9, "pF":1e-12},
    "inductance": {"H":1, "mH":1e-3, "µH":1e-6},
    "frequency": {"Hz":1, "kHz":1e3, "MHz":1e6},
    "volume_flow": {"m³/s":1, "L/s":1e-3, "L/min":1e-3/60, "ft³/min":.0283168466/60},
    "density": {"kg/m³":1, "g/cm³":1e3, "lbm/ft³":16.0184634},
    "viscosity": {"Pa·s":1, "mPa·s":1e-3, "cP":1e-3},
    "specific_heat": {"J/(kg·K)":1, "kJ/(kg·K)":1e3},
    "conductivity": {"W/(m·K)":1},
    "temp_delta": {"K or °C":1, "°F difference":5/9},
    "spring_rate": {"N/m":1, "N/mm":1e3, "lbf/in":175.126835},
    "series": {"E3":1,"E6":1,"E12":1,"E24":1,"E48":1,"E96":1,"E192":1},
    "capacity": {"Ah":1,"mAh":1e-3},
    "line_load": {"N/m":1,"kN/m":1e3,"lbf/ft":14.5939029},
    "thermal_resistance": {"K/W":1,"°C/W":1},
    "heat_transfer_coefficient": {"W/(m²·K)":1},
    "mass_flow": {"kg/s":1,"g/s":1e-3,"lbm/s":.45359237},
    "temperature_abs": {"K":1,"°C":1},
}
AUTO_UNIT = "Auto (best fit)"
AUTO_UNITS = {
    "length": ("µm","mm","cm","m","km"), "area": ("mm²","cm²","m²"),
    "force": ("N","kN"), "pressure": ("Pa","kPa","MPa","bar"),
    "power": ("W","kW","MW"), "energy": ("J","kJ","MJ"),
    "voltage": ("mV","V","kV"), "current": ("µA","mA","A"),
    "resistance": ("Ω","kΩ","MΩ"), "capacitance": ("pF","nF","µF","mF","F"),
    "inductance": ("µH","mH","H"), "frequency": ("Hz","kHz","MHz"),
    "time": ("ms","s","min","h"), "mass": ("g","kg"),
    "capacity": ("mAh","Ah"), "mass_flow": ("g/s","kg/s"),
}

@dataclass(frozen=True)
class Input:
    key: str
    label: str
    dimension: str = "none"
    default: str = ""
    default_unit: str = ""

@dataclass(frozen=True)
class Calculation:
    discipline: str
    name: str
    formula: str
    inputs: tuple
    output_label: str
    output_dimension: str
    compute: object
    note: str = ""
    actions: tuple = ()
    solvers: object = None

def I(key,label,dimension="none",default="",default_unit=""): return Input(key,label,dimension,default,default_unit)
def C(d,n,f,inputs,out,dim,fn,note="",actions=(),solvers=None): return Calculation(d,n,f,tuple(inputs),out,dim,fn,note,tuple(actions),solvers)

def pcb_width(values, k):
    area_mil2=(values["current"]/(k*values["rise"]**.44))**(1/.725)
    return (area_mil2/(values["thickness"]/.0000254))*.0000254
def pcb_current(values, k):
    area=(values["width"]/.0000254)*(values["thickness"]/.0000254)
    return k*values["rise"]**.44*area**.725
def pcb_rise(values,k):
    area=(values["width"]/.0000254)*(values["thickness"]/.0000254)
    return (values["current"]/(k*area**.725))**(1/.44)
def pcb_thickness(values,k):
    area=(values["current"]/(k*values["rise"]**.44))**(1/.725)
    return (area/(values["width"]/.0000254))*.0000254
AWG_DATA=((30,.86),(28,1.4),(26,2.2),(24,3.5),(22,7),(20,11),(18,16),(16,22),(14,32),(12,41),(10,55),(8,73),(6,101),(4,135),(2,181),(0,245))
def awg_area_m2(gauge): return 0.012668 * 92**((36-gauge)/19.5) * 1e-6
def awg_diameter_mm(gauge): return 0.127 * 92**((36-gauge)/39)
def wire_gauge_chart():
    """Return AWG geometry, copper resistance, and application screen data."""
    return tuple({
        "gauge":gauge,
        "diameter_mm":awg_diameter_mm(gauge),
        "area_mm2":awg_area_m2(gauge)*1e6,
        "ohm_per_km":1.724e-8*1000/awg_area_m2(gauge),
        "screen_current":ampacity,
    } for gauge,ampacity in AWG_DATA)
def recommend_awg(values):
    current,length,voltage,max_drop=values["current"],values["length"],values["voltage"],values["drop"]
    for gauge,ampacity in AWG_DATA:
        resistance=1.724e-8*(2*length)/awg_area_m2(gauge)
        if current<=ampacity and current*resistance<=voltage*max_drop/100: return gauge
    raise ValueError("Required conductor is larger than 0 AWG")
def wire_drop(values,gauge): return values["current"]*1.724e-8*(2*values["length"])/awg_area_m2(gauge)

def network_equivalents(values,reciprocal_series=False):
    if len(values)<2 or any(value==0 for value in values):raise ValueError("Enter at least two nonzero values")
    direct=sum(values);reciprocal=1/sum(1/value for value in values)
    return (reciprocal,direct) if reciprocal_series else (direct,reciprocal)

def series_rlc_response(resistance,inductance,capacitance,frequency):
    if frequency<=0 or capacitance<=0:raise ValueError("Frequency and capacitance must be positive")
    omega=2*math.pi*frequency;reactance=omega*inductance-1/(omega*capacitance)
    return {"resistance":resistance,"reactance":reactance,"magnitude":math.hypot(resistance,reactance),"phase_deg":math.degrees(math.atan2(reactance,resistance))}

def rc_filter_response(resistance,capacitance,frequency):
    if min(resistance,capacitance,frequency)<=0:raise ValueError("R, C, and frequency must be positive")
    cutoff=1/(2*math.pi*resistance*capacitance);ratio=frequency/cutoff;low=1/math.sqrt(1+ratio**2);high=ratio/math.sqrt(1+ratio**2)
    return {"cutoff":cutoff,"low_gain":low,"low_phase":-math.degrees(math.atan(ratio)),"high_gain":high,"high_phase":math.degrees(math.atan(1/ratio))}

def nozzle_exit_state(total_pressure,total_temperature,exit_pressure,gamma,gas_constant):
    ratio=total_pressure/exit_pressure
    if ratio<1 or gamma<=1 or min(total_temperature,gas_constant)<=0:raise ValueError("Total pressure must exceed exit pressure and γ must exceed 1")
    mach=math.sqrt(2/(gamma-1)*(ratio**((gamma-1)/gamma)-1));temperature=total_temperature/(1+(gamma-1)*mach**2/2);sound=math.sqrt(gamma*gas_constant*temperature)
    return {"mach":mach,"temperature":temperature,"sound_speed":sound,"velocity":mach*sound}

def standard_atmosphere(altitude):
    if not 0<=altitude<=11000:raise ValueError("This atmosphere model is limited to 0–11 km")
    temperature=288.15-.0065*altitude;pressure=101325*(temperature/288.15)**(9.80665/(.0065*287.05287));density=pressure/(287.05287*temperature)
    return {"temperature":temperature,"pressure":pressure,"density":density,"sound_speed":math.sqrt(1.4*287.05287*temperature)}

def wardogs_solution(mortar_x, mortar_y, target_x, target_y):
    """Return distance and a north-zero clockwise bearing from Mortar to Target."""
    dx=target_x-mortar_x;dy=target_y-mortar_y
    cartesian_angle=math.degrees(math.atan2(dy,dx))
    return {"distance":math.hypot(dx,dy),"angle_deg":(90-cartesian_angle)%360}

CALCULATIONS = [
 C("Electrical","Ohm’s law","V = I × R",[I("v","Voltage","voltage"),I("i","Current","current"),I("r","Resistance","resistance")],"Voltage","voltage",lambda v:v["i"]*v["r"],solvers={"v":lambda v:v["i"]*v["r"],"i":lambda v:v["v"]/v["r"],"r":lambda v:v["v"]/v["i"]}),
 C("Electrical","DC power","P = V × I",[I("p","Power","power"),I("v","Voltage","voltage"),I("i","Current","current")],"Power","power",lambda v:v["v"]*v["i"],solvers={"p":lambda v:v["v"]*v["i"],"v":lambda v:v["p"]/v["i"],"i":lambda v:v["p"]/v["v"]}),
 C("Electrical","Voltage divider","Vout = Vin × R2/(R1 + R2)",[I("vout","Output voltage","voltage"),I("vin","Input voltage","voltage"),I("r1","R1","resistance"),I("r2","R2","resistance")],"Output voltage","voltage",lambda v:v["vin"]*v["r2"]/(v["r1"]+v["r2"]),"R1 connects Vin to Vout. R2 connects Vout to ground.",solvers={"vout":lambda v:v["vin"]*v["r2"]/(v["r1"]+v["r2"]),"vin":lambda v:v["vout"]*(v["r1"]+v["r2"])/v["r2"],"r1":lambda v:v["r2"]*(v["vin"]/v["vout"]-1),"r2":lambda v:v["vout"]*v["r1"]/(v["vin"]-v["vout"])}),
 C("Electrical","PCB traces","Shared current, temperature-rise, copper, and optional length inputs",[I("current","Current","current"),I("rise","Temperature rise","temp_delta","10"),I("thickness","Copper thickness","length","0.03479","mm"),I("length","Optional trace length","length")],"Trace results","none",lambda v:0,"External and internal widths use IPC-2221 estimates. If length is entered, copper resistance is also shown for each width."),
 C("Electrical","Wire sizing & voltage drop","AWG from current and round-trip copper voltage drop",[I("current","Current","current"),I("length","One-way length","length"),I("voltage","System voltage","voltage"),I("drop","Maximum voltage drop (%)","none","3")],"Recommended AWG","none",recommend_awg,"Copper conductor at ~20 °C; conservative chassis ampacity screen. Verify insulation, bundling, ambient temperature, duty cycle, and electrical code requirements."),
 C("Electrical","Series / parallel resistance","Series: R = ΣRᵢ   ·   Parallel: R = 1/Σ(1/Rᵢ)",[I("values","Resistances (comma-separated)","resistance")],"Resistance","resistance",lambda v:0,"Enter two or more values separated by commas, semicolons, or new lines. A typed unit may be used on each value."),
 C("Electrical","Series / parallel capacitance","Parallel: C = ΣCᵢ   ·   Series: C = 1/Σ(1/Cᵢ)",[I("values","Capacitances (comma-separated)","capacitance")],"Capacitance","capacitance",lambda v:0,"Ideal capacitors; voltage rating, bias dependence, tolerance, ESR, and dielectric behavior are not combined."),
 C("Electrical","Series / parallel inductance","Series: L = ΣLᵢ   ·   Parallel: L = 1/Σ(1/Lᵢ)",[I("values","Inductances (comma-separated)","inductance")],"Inductance","inductance",lambda v:0,"Assumes uncoupled ideal inductors. Mutual coupling changes the result."),
 C("Electrical","RC time constant","τ = R × C",[I("tau","Time constant","time"),I("r","Resistance","resistance"),I("c","Capacitance","capacitance")],"Time constant","time",lambda v:v["r"]*v["c"],solvers={"tau":lambda v:v["r"]*v["c"],"r":lambda v:v["tau"]/v["c"],"c":lambda v:v["tau"]/v["r"]}),
 C("Electrical","LC resonant frequency","f = 1/(2π√LC)",[I("f","Frequency","frequency"),I("l","Inductance","inductance"),I("c","Capacitance","capacitance")],"Frequency","frequency",lambda v:1/(2*math.pi*math.sqrt(v["l"]*v["c"])),solvers={"f":lambda v:1/(2*math.pi*math.sqrt(v["l"]*v["c"])),"l":lambda v:1/((2*math.pi*v["f"])**2*v["c"]),"c":lambda v:1/((2*math.pi*v["f"])**2*v["l"])}),
 C("Electrical","Preferred resistor value","IEC 60063 preferred E-series values",[I("target","Target resistance","resistance"),I("series","Preferred series","series","1","E24")],"Preferred values","resistance",lambda v:0,"Shows the adjacent and nearest nominal values; availability still depends on the selected component family."),
 C("Electrical","Preferred capacitor value","IEC 60063 preferred E-series values",[I("target","Target capacitance","capacitance"),I("series","Preferred series","series","1","E24")],"Preferred values","capacitance",lambda v:0,"Shows the adjacent and nearest nominal values; availability still depends on dielectric, voltage rating, and package."),
 C("Electrical","LED current resistor","R = (Vs − Vf)/I",[I("supply","Supply voltage","voltage"),I("forward","LED forward voltage","voltage"),I("current","LED current","current")],"Series resistance","resistance",lambda v:(v["supply"]-v["forward"])/v["current"],"Requires Vs > Vf. Check resistor power P = I(Vs−Vf), LED pulse limits, and supply tolerance."),
 C("Electrical","Battery runtime","t = capacity × efficiency / current",[I("capacity","Battery capacity","capacity"),I("current","Average load current","current"),I("efficiency","Usable fraction","none","0.85")],"Estimated runtime","time",lambda v:3600*v["capacity"]*v["efficiency"]/v["current"],"Simple average-current estimate; battery chemistry, discharge rate, temperature, aging, and converter behavior can dominate."),
 C("Electrical","Sine RMS / peak","Vpk = √2 Vrms; Vpp = 2Vpk",[I("rms","RMS voltage","voltage"),I("peak","Peak voltage","voltage"),I("pp","Peak-to-peak voltage","voltage")],"Voltage","voltage",lambda v:v["rms"]*math.sqrt(2),solvers={"rms":lambda v:(v.get("peak",v.get("pp")/2))/math.sqrt(2),"peak":lambda v:v.get("rms",v.get("pp")/(2*math.sqrt(2)))*math.sqrt(2),"pp":lambda v:v.get("peak",v.get("rms")*math.sqrt(2))*2}),
 C("Electrical","Three-phase real power","P = √3 VLL IL PF",[I("voltage","Line-line voltage","voltage"),I("current","Line current","current"),I("pf","Power factor","none","1")],"Real power","power",lambda v:math.sqrt(3)*v["voltage"]*v["current"]*v["pf"],"Balanced three-phase system using RMS line quantities."),
 C("Electrical","Inductive reactance","XL = 2πfL",[I("frequency","Frequency","frequency"),I("inductance","Inductance","inductance")],"Reactance","resistance",lambda v:2*math.pi*v["frequency"]*v["inductance"]),
 C("Electrical","Capacitive reactance","XC = 1/(2πfC)",[I("frequency","Frequency","frequency"),I("capacitance","Capacitance","capacitance")],"Reactance magnitude","resistance",lambda v:1/(2*math.pi*v["frequency"]*v["capacitance"])),
 C("Electrical","RC cutoff frequency","fc = 1/(2πRC)",[I("resistance","Resistance","resistance"),I("capacitance","Capacitance","capacitance")],"Cutoff frequency","frequency",lambda v:1/(2*math.pi*v["resistance"]*v["capacitance"]),"Ideal first-order RC pole."),
 C("Electrical","Power ratio decibels","dB = 10 log10(P2/P1)",[I("p1","Reference power","power"),I("p2","Measured power","power")],"Power ratio","none",lambda v:10*math.log10(v["p2"]/v["p1"])),
 C("Electrical","Resistor dissipation","P = I²R",[I("current","Current","current"),I("resistance","Resistance","resistance")],"Dissipation","power",lambda v:v["current"]**2*v["resistance"],"Select a rated power with appropriate ambient-temperature derating and transient margin."),
 C("Electrical","PCB via resistance","R = ρL/[π((r+t)²−r²)]",[I("length","Board thickness","length","1.6","mm"),I("diameter","Finished hole diameter","length","0.3","mm"),I("plating","Copper plating","length","0.025","mm")],"Via resistance","resistance",lambda v:1.724e-8*v["length"]/(math.pi*((v["diameter"]/2+v["plating"])**2-(v["diameter"]/2)**2)),"DC copper-barrel estimate; fabrication tolerances, temperature, current crowding, and thermal limits are not included."),
 C("Electrical","Differential impedance estimate","Zdiff ≈ 2Z0[1−0.48e^(−0.96s/h)]",[I("z0","Single-ended impedance","resistance","50","Ω"),I("spacing","Edge spacing","length"),I("height","Trace-to-plane height","length")],"Differential impedance","resistance",lambda v:2*v["z0"]*(1-.48*math.exp(-.96*v["spacing"]/v["height"])),"First-order edge-coupled microstrip estimate only; use a field solver for fabrication values."),
 C("Electrical","Linear power derating","Pallow = Prated(Tzero−Ta)/(Tzero−Tfull)",[I("rated","Rated power","power"),I("ambient","Ambient temperature (°C)","none","25"),I("full","Full-rating temperature (°C)","none","70"),I("zero","Zero-power temperature (°C)","none","155")],"Allowed power","power",lambda v:v["rated"]*(v["zero"]-v["ambient"])/(v["zero"]-v["full"]),"Generic linear derating model; use the component manufacturer’s actual curve and limits."),
 C("Electrical","Series RLC impedance","Z = R + j(2πfL−1/(2πfC))",[I("resistance","Resistance","resistance"),I("inductance","Inductance","inductance"),I("capacitance","Capacitance","capacitance"),I("frequency","Frequency","frequency")],"Complex impedance","none",lambda v:0,"Ideal sinusoidal steady-state series RLC network."),
 C("Electrical","RC filter response","HLP = 1/(1+jf/fc)",[I("resistance","Resistance","resistance"),I("capacitance","Capacitance","capacitance"),I("frequency","Evaluation frequency","frequency")],"Filter response","none",lambda v:0,"Shows ideal first-order low-pass and high-pass magnitude and phase."),
 C("Electrical","Amplitude ratio decibels","dB = 20 log10(A2/A1)",[I("a1","Reference amplitude","none"),I("a2","Measured amplitude","none")],"Amplitude ratio","none",lambda v:20*math.log10(abs(v["a2"]/v["a1"]))),
 C("Mechanical","Newton’s second law","F = m × a",[I("f","Force","force"),I("m","Mass","mass"),I("a","Acceleration","acceleration")],"Force","force",lambda v:v["m"]*v["a"],solvers={"f":lambda v:v["m"]*v["a"],"m":lambda v:v["f"]/v["a"],"a":lambda v:v["f"]/v["m"]}),
 C("Mechanical","Rotational power","P = τ × ω",[I("p","Power","power"),I("t","Torque","torque"),I("w","Rotational speed","rotation")],"Power","power",lambda v:v["t"]*v["w"],solvers={"p":lambda v:v["t"]*v["w"],"t":lambda v:v["p"]/v["w"],"w":lambda v:v["p"]/v["t"]}),
 C("Mechanical","Kinetic energy","E = ½mv²",[I("e","Energy","energy"),I("m","Mass","mass"),I("v","Speed","speed")],"Energy","energy",lambda v:.5*v["m"]*v["v"]**2,solvers={"e":lambda v:.5*v["m"]*v["v"]**2,"m":lambda v:2*v["e"]/v["v"]**2,"v":lambda v:math.sqrt(2*v["e"]/v["m"])}),
 C("Mechanical","Hooke’s law","F = k × x",[I("f","Force","force"),I("k","Spring rate","spring_rate"),I("x","Deflection","length")],"Force","force",lambda v:v["k"]*v["x"],solvers={"f":lambda v:v["k"]*v["x"],"k":lambda v:v["f"]/v["x"],"x":lambda v:v["f"]/v["k"]}),
 C("Mechanical","Factor of safety","FoS = strength / stress",[I("fos","Factor of safety"),I("strength","Material strength","pressure"),I("stress","Working stress","pressure")],"Factor of safety","none",lambda v:v["strength"]/v["stress"],solvers={"fos":lambda v:v["strength"]/v["stress"],"strength":lambda v:v["fos"]*v["stress"],"stress":lambda v:v["strength"]/v["fos"]}),
 C("Mechanical","Shaft torsional stress","τmax = 16T/(πd³)",[I("torque","Torque","torque"),I("diameter","Solid shaft diameter","length")],"Maximum shear stress","pressure",lambda v:16*v["torque"]/(math.pi*v["diameter"]**3),"Solid circular shaft under pure elastic torsion."),
 C("Mechanical","Shaft angle of twist","θ = 32TL/(πGd⁴)",[I("torque","Torque","torque"),I("length","Shaft length","length"),I("modulus","Shear modulus","pressure"),I("diameter","Solid shaft diameter","length")],"Twist (radians)","none",lambda v:32*v["torque"]*v["length"]/(math.pi*v["modulus"]*v["diameter"]**4),"Uniform solid circular shaft in the elastic range."),
 C("Mechanical","Hydraulic cylinder force","F = pA",[I("pressure","Gauge pressure","pressure"),I("area","Effective piston area","area")],"Cylinder force","force",lambda v:v["pressure"]*v["area"],"Ideal static force; subtract friction and account for rod-side annular area when applicable."),
 C("Mechanical","Gear ratio","ratio = driven teeth / driver teeth",[I("driver","Driver teeth","none"),I("driven","Driven teeth","none")],"Speed reduction ratio","none",lambda v:v["driven"]/v["driver"],"Ideal external spur-gear ratio; ignores losses and direction."),
 C("Mechanical","Belt speed","v = ωD/2",[I("speed","Pulley speed","rotation"),I("diameter","Pitch diameter","length")],"Belt speed","speed",lambda v:v["speed"]*v["diameter"]/2,"Uses pitch diameter and neglects slip."),
 C("Mechanical","Spring stored energy","E = ½kx²",[I("rate","Spring rate","spring_rate"),I("deflection","Deflection","length")],"Stored energy","energy",lambda v:.5*v["rate"]*v["deflection"]**2,"Ideal linear spring within its rated travel."),
 C("Mechanical","Bearing L10 life","L10 = (C/P)^p × 10⁶ rev",[I("capacity","Dynamic capacity","force"),I("load","Equivalent bearing load","force"),I("exponent","Life exponent (3 ball, 3.333 roller)","none","3")],"L10 life (revolutions)","none",lambda v:(v["capacity"]/v["load"])**v["exponent"]*1e6,"Basic rating life only; reliability adjustment, lubrication, contamination, speed, and mounting require manufacturer methods."),
 C("Mechanical","Bolt tightening torque","T = KFd",[I("factor","Nut factor K","none","0.2"),I("preload","Target preload","force"),I("diameter","Nominal diameter","length")],"Tightening torque","torque",lambda v:v["factor"]*v["preload"]*v["diameter"],"Highly approximate; friction dominates torque-preload scatter. Use validated joint-specific procedures for critical joints."),
 C("Mechanical","Bolt tensile stress","σ = F/At",[I("preload","Bolt tensile load","force"),I("area","Tensile stress area","area")],"Bolt tensile stress","pressure",lambda v:v["preload"]/v["area"],"Use the thread-standard tensile stress area, not nominal shank area, for threaded-section stress."),
 C("Mechanical","Gear tangential tooth force","Ft = 2T/dp",[I("torque","Transmitted torque","torque"),I("diameter","Pitch diameter","length")],"Tangential tooth force","force",lambda v:2*v["torque"]/v["diameter"],"Ideal pitch-circle force only; radial/axial components and dynamic factors require gear geometry and rating methods."),
 C("Mechanical","Belt tension difference","T1−T2 = P/v",[I("power","Transmitted power","power"),I("speed","Belt speed","speed")],"Tension difference","force",lambda v:v["power"]/v["speed"],"Does not determine individual tight/slack tensions or traction capacity."),
 C("Structural","Axial stress","σ = F/A",[I("stress","Stress","pressure"),I("f","Axial force","force"),I("a","Area","area")],"Stress","pressure",lambda v:v["f"]/v["a"],solvers={"stress":lambda v:v["f"]/v["a"],"f":lambda v:v["stress"]*v["a"],"a":lambda v:v["f"]/v["stress"]}),
 C("Structural","Axial strain","ε = ΔL/L",[I("strain","Strain"),I("dl","Change in length","length"),I("l","Original length","length")],"Strain","none",lambda v:v["dl"]/v["l"],solvers={"strain":lambda v:v["dl"]/v["l"],"dl":lambda v:v["strain"]*v["l"],"l":lambda v:v["dl"]/v["strain"]}),
 C("Structural","Euler buckling load","Pcr = π²EI/(KL)²",[I("e","Elastic modulus","pressure"),I("i","Second moment of area","moment4"),I("k","Effective-length factor","none","1"),I("l","Unsupported length","length")],"Critical load","force",lambda v:math.pi**2*v["e"]*v["i"]/(v["k"]*v["l"])**2,"Ideal straight column with pinned-equivalent effective length."),
 C("Structural","Bending stress","σ = Mc/I",[I("moment","Bending moment","torque"),I("c","Neutral-axis distance","length"),I("i","Second moment of area","moment4")],"Extreme-fiber stress","pressure",lambda v:v["moment"]*v["c"]/v["i"],"Linear-elastic, prismatic member under simple bending."),
 C("Structural","Rectangle section inertia","I = bh³/12",[I("width","Section width","length"),I("height","Section height","length")],"Second moment of area","moment4",lambda v:v["width"]*v["height"]**3/12),
 C("Structural","Tube section inertia","I = π(Do⁴−Di⁴)/64",[I("outer","Outer diameter","length"),I("inner","Inner diameter","length")],"Second moment of area","moment4",lambda v:math.pi*(v["outer"]**4-v["inner"]**4)/64,"Requires outer diameter greater than inner diameter."),
 C("Structural","Cantilever point-load deflection","δ = FL³/(3EI)",[I("force","End force","force"),I("length","Beam length","length"),I("modulus","Elastic modulus","pressure"),I("inertia","Second moment of area","moment4")],"End deflection","length",lambda v:v["force"]*v["length"]**3/(3*v["modulus"]*v["inertia"]),"Small-deflection Euler–Bernoulli beam with an end point load."),
 C("Structural","Simply supported UDL deflection","δmax = 5wL⁴/(384EI)",[I("load","Uniform line load","line_load"),I("length","Span","length"),I("modulus","Elastic modulus","pressure"),I("inertia","Second moment of area","moment4")],"Maximum deflection","length",lambda v:5*v["load"]*v["length"]**4/(384*v["modulus"]*v["inertia"]),"Small-deflection Euler–Bernoulli beam with uniform load over the full simple span."),
 C("Structural","Combined axial and bending stress","σ = F/A + Mc/I",[I("force","Axial force","force"),I("area","Area","area"),I("moment","Bending moment","torque"),I("c","Neutral-axis distance","length"),I("inertia","Second moment of area","moment4")],"Combined normal stress","pressure",lambda v:v["force"]/v["area"]+v["moment"]*v["c"]/v["inertia"],"Reports the same-sign extreme fiber; evaluate the opposite fiber separately when needed."),
 C("Structural","Plane-stress von Mises","σv = √(σx²−σxσy+σy²+3τxy²)",[I("sx","Normal stress σx","pressure"),I("sy","Normal stress σy","pressure"),I("tau","Shear stress τxy","pressure")],"Von Mises stress","pressure",lambda v:math.sqrt(v["sx"]**2-v["sx"]*v["sy"]+v["sy"]**2+3*v["tau"]**2),"Plane-stress distortion-energy equivalent; compare against an appropriate material limit."),
 C("Structural","Simply supported point reaction","RA = P(L−a)/L",[I("load","Point load","force"),I("span","Support span","length"),I("position","Load distance from left","length")],"Left support reaction","force",lambda v:v["load"]*(v["span"]-v["position"])/v["span"],"Single vertical point load between simple supports; right reaction is P−RA."),
 C("Structural","I-section strong-axis inertia","Ix = [BH³−(B−tw)(H−2tf)³]/12",[I("width","Flange width B","length"),I("height","Overall height H","length"),I("web","Web thickness tw","length"),I("flange","Flange thickness tf","length")],"Second moment of area","moment4",lambda v:(v["width"]*v["height"]**3-(v["width"]-v["web"])*(v["height"]-2*v["flange"])**3)/12,"Ideal doubly symmetric sharp-corner I-section."),
 C("Structural","Maximum principal stress","σ1 = (σx+σy)/2 + √[((σx−σy)/2)²+τxy²]",[I("sx","Normal stress σx","pressure"),I("sy","Normal stress σy","pressure"),I("tau","Shear stress τxy","pressure")],"Maximum principal stress","pressure",lambda v:(v["sx"]+v["sy"])/2+math.sqrt(((v["sx"]-v["sy"])/2)**2+v["tau"]**2),"Plane-stress transformation."),
 C("Fluids","Hydrostatic pressure","p = ρgh",[I("p","Pressure","pressure"),I("rho","Fluid density","density","1000"),I("g","Gravity","acceleration","9.80665"),I("h","Fluid depth","length")],"Pressure","pressure",lambda v:v["rho"]*v["g"]*v["h"],solvers={"p":lambda v:v["rho"]*v["g"]*v["h"],"rho":lambda v:v["p"]/(v["g"]*v["h"]),"g":lambda v:v["p"]/(v["rho"]*v["h"]),"h":lambda v:v["p"]/(v["rho"]*v["g"])}),
 C("Fluids","Volume flow","Q = A × v",[I("q","Volume flow","volume_flow"),I("a","Flow area","area"),I("v","Average velocity","speed")],"Volume flow","volume_flow",lambda v:v["a"]*v["v"],solvers={"q":lambda v:v["a"]*v["v"],"a":lambda v:v["q"]/v["v"],"v":lambda v:v["q"]/v["a"]}),
 C("Fluids","Reynolds number","Re = ρvD/μ",[I("rho","Density","density","1000"),I("v","Velocity","speed"),I("d","Hydraulic diameter","length"),I("mu","Dynamic viscosity","viscosity","1","mPa·s")],"Reynolds number","none",lambda v:v["rho"]*v["v"]*v["d"]/v["mu"]),
 C("Fluids","Bernoulli pressure change","p2−p1 = ½ρ(v1²−v2²)+ρg(z1−z2)",[I("rho","Fluid density","density","998"),I("v1","Upstream velocity","speed"),I("v2","Downstream velocity","speed"),I("z1","Upstream elevation","length"),I("z2","Downstream elevation","length")],"Pressure change","pressure",lambda v:.5*v["rho"]*(v["v1"]**2-v["v2"]**2)+v["rho"]*9.80665*(v["z1"]-v["z2"]),"Steady incompressible flow with no pump, turbine, or head loss between stations."),
 C("Fluids","Darcy–Weisbach pressure drop","Δp = f(L/D)ρv²/2",[I("factor","Darcy friction factor","none","0.02"),I("length","Pipe length","length"),I("diameter","Inside diameter","length"),I("density","Fluid density","density","998"),I("velocity","Mean velocity","speed")],"Pressure drop","pressure",lambda v:v["factor"]*(v["length"]/v["diameter"])*v["density"]*v["velocity"]**2/2,"Straight-pipe major loss only. Determine Darcy friction factor from Reynolds number and relative roughness."),
 C("Fluids","Pump hydraulic power","Pshaft = ρgQH/η",[I("density","Fluid density","density","998"),I("flow","Volume flow","volume_flow"),I("head","Head","length"),I("efficiency","Pump efficiency","none","0.7")],"Required shaft power","power",lambda v:v["density"]*9.80665*v["flow"]*v["head"]/v["efficiency"],"Steady incompressible estimate; efficiency must be taken at the operating point."),
 C("Fluids","Orifice flow","Q = CdA√(2Δp/ρ)",[I("coefficient","Discharge coefficient","none","0.62"),I("area","Orifice area","area"),I("pressure","Pressure differential","pressure"),I("density","Fluid density","density","998")],"Volume flow","volume_flow",lambda v:v["coefficient"]*v["area"]*math.sqrt(2*v["pressure"]/v["density"]),"Incompressible sharp-edged approximation; coefficient and cavitation limits require application data."),
 C("Fluids","Hydraulic power","P = ΔpQ",[I("pressure","Pressure differential","pressure"),I("flow","Volume flow","volume_flow")],"Hydraulic power","power",lambda v:v["pressure"]*v["flow"]),
 C("Fluids","Haaland friction factor","1/√f = −1.8log10[((ε/D)/3.7)^1.11+6.9/Re]",[I("reynolds","Reynolds number","none"),I("roughness","Absolute roughness","length"),I("diameter","Pipe diameter","length")],"Darcy friction factor","none",lambda v:(-1.8*math.log10(((v["roughness"]/v["diameter"])/3.7)**1.11+6.9/v["reynolds"]))**-2,"Turbulent-flow approximation; use f = 64/Re for fully developed laminar flow."),
 C("Fluids","Cv / Kv conversion","Cv ≈ 1.156 Kv",[I("cv","Flow coefficient Cv","none"),I("kv","Flow coefficient Kv","none")],"Flow coefficient","none",lambda v:1.156*v["kv"],solvers={"cv":lambda v:1.156*v["kv"],"kv":lambda v:v["cv"]/1.156}),
 C("Fluids","Choked gas mass flow","ṁ = CdApt√(γ/RTt)[2/(γ+1)]^((γ+1)/(2(γ−1)))",[I("coefficient","Discharge coefficient","none","1"),I("area","Throat area","area"),I("pressure","Total pressure","pressure"),I("temperature","Total temperature","temperature_abs"),I("gamma","Specific-heat ratio","none","1.4"),I("gas_constant","Gas constant (J/kg·K)","none","287.05")],"Choked mass flow","mass_flow",lambda v:v["coefficient"]*v["area"]*v["pressure"]*math.sqrt(v["gamma"]/(v["gas_constant"]*v["temperature"]))*(2/(v["gamma"]+1))**((v["gamma"]+1)/(2*(v["gamma"]-1))),"Perfect-gas, one-dimensional, choked, adiabatic flow."),
 C("Thermal","Sensible heat","Q = mcΔT",[I("q","Heat energy","energy"),I("m","Mass","mass"),I("c","Specific heat","specific_heat"),I("dt","Temperature change","temp_delta")],"Heat energy","energy",lambda v:v["m"]*v["c"]*v["dt"],solvers={"q":lambda v:v["m"]*v["c"]*v["dt"],"m":lambda v:v["q"]/(v["c"]*v["dt"]),"c":lambda v:v["q"]/(v["m"]*v["dt"]),"dt":lambda v:v["q"]/(v["m"]*v["c"])}),
 C("Thermal","Conduction heat rate","Q̇ = kAΔT/L",[I("q","Heat rate","power"),I("k","Thermal conductivity","conductivity"),I("a","Area","area"),I("dt","Temperature difference","temp_delta"),I("l","Thickness","length")],"Heat rate","power",lambda v:v["k"]*v["a"]*v["dt"]/v["l"],"Steady one-dimensional conduction.",solvers={"q":lambda v:v["k"]*v["a"]*v["dt"]/v["l"],"k":lambda v:v["q"]*v["l"]/(v["a"]*v["dt"]),"a":lambda v:v["q"]*v["l"]/(v["k"]*v["dt"]),"dt":lambda v:v["q"]*v["l"]/(v["k"]*v["a"]),"l":lambda v:v["k"]*v["a"]*v["dt"]/v["q"]}),
 C("Thermal","Linear thermal expansion","ΔL = αLΔT",[I("dl","Length change","length"),I("alpha","Expansion coefficient (1/K)","none"),I("l","Original length","length"),I("dt","Temperature change","temp_delta")],"Length change","length",lambda v:v["alpha"]*v["l"]*v["dt"],solvers={"dl":lambda v:v["alpha"]*v["l"]*v["dt"],"alpha":lambda v:v["dl"]/(v["l"]*v["dt"]),"l":lambda v:v["dl"]/(v["alpha"]*v["dt"]),"dt":lambda v:v["dl"]/(v["alpha"]*v["l"])}),
 C("Thermal","Convection heat rate","Q̇ = hAΔT",[I("h","Convection coefficient","heat_transfer_coefficient"),I("area","Surface area","area"),I("dt","Surface-fluid temperature difference","temp_delta")],"Heat rate","power",lambda v:v["h"]*v["area"]*v["dt"],"Lumped coefficient estimate; h depends strongly on geometry and flow."),
 C("Thermal","Radiation heat rate","Q̇ = εσA(Ts⁴−Tsur⁴)",[I("emissivity","Emissivity","none","0.9"),I("area","Radiating area","area"),I("surface","Surface temperature","temperature_abs"),I("surroundings","Surroundings temperature","temperature_abs")],"Net radiative heat rate","power",lambda v:v["emissivity"]*5.670374419e-8*v["area"]*(v["surface"]**4-v["surroundings"]**4),"Diffuse gray surface exchanging with large isothermal surroundings; temperatures are absolute internally."),
 C("Thermal","Conduction thermal resistance","Rθ = L/(kA)",[I("length","Layer thickness","length"),I("conductivity","Thermal conductivity","conductivity"),I("area","Heat-flow area","area")],"Thermal resistance","thermal_resistance",lambda v:v["length"]/(v["conductivity"]*v["area"]),"One-dimensional steady conduction through a uniform layer."),
 C("Thermal","Heatsink requirement","Rsa = (Tjmax−Ta)/P − Rjc − Rcs",[I("junction","Maximum junction temperature","temperature_abs"),I("ambient","Ambient temperature","temperature_abs"),I("power","Dissipated power","power"),I("rjc","Junction-case resistance","thermal_resistance"),I("rcs","Case-sink resistance","thermal_resistance","0")],"Maximum sink-ambient resistance","thermal_resistance",lambda v:(v["junction"]-v["ambient"])/v["power"]-v["rjc"]-v["rcs"],"Steady-state thermal-resistance network; use transient impedance for pulsed loads."),
 C("Thermal","Junction temperature","Tj = Ta + P(Rjc+Rcs+Rsa)",[I("ambient","Ambient temperature","temperature_abs"),I("power","Dissipated power","power"),I("rjc","Junction-case resistance","thermal_resistance"),I("rcs","Case-sink resistance","thermal_resistance","0"),I("rsa","Sink-ambient resistance","thermal_resistance")],"Junction temperature","temperature_abs",lambda v:v["ambient"]+v["power"]*(v["rjc"]+v["rcs"]+v["rsa"]),"Steady-state lumped thermal network."),
 C("Thermal","Enclosure temperature rise","ΔT = Q/(UA)",[I("heat","Internal heat load","power"),I("coefficient","Overall heat-transfer coefficient","heat_transfer_coefficient"),I("area","Effective enclosure area","area")],"Temperature rise","temp_delta",lambda v:v["heat"]/(v["coefficient"]*v["area"]),"Simplified steady-state lumped model; solar load, internal gradients, openings, and radiation may dominate."),
 C("Thermal","Series / parallel thermal resistance","Series: Rθ = ΣRθᵢ   ·   Parallel: Rθ = 1/Σ(1/Rθᵢ)",[I("values","Thermal resistances (comma-separated)","thermal_resistance")],"Thermal resistance","thermal_resistance",lambda v:0,"Lumped steady-state paths; parallel elements must connect the same two temperature nodes."),
 C("General","Linear interpolation","y = y₁+(x−x₁)(y₂−y₁)/(x₂−x₁)",[I("x","x"),I("x1","x₁"),I("y1","y₁"),I("x2","x₂"),I("y2","y₂")],"Interpolated value","none",lambda v:v["y1"]+(v["x"]-v["x1"])*(v["y2"]-v["y1"])/(v["x2"]-v["x1"])),
 C("General","Vector magnitude","|v| = √(x²+y²+z²)",[I("x","x component"),I("y","y component"),I("z","z component","none","0")],"Magnitude","none",lambda v:math.sqrt(v["x"]**2+v["y"]**2+v["z"]**2)),
 C("General","Circle area","A = πr²",[I("a","Area","area"),I("r","Radius","length")],"Area","area",lambda v:math.pi*v["r"]**2,solvers={"a":lambda v:math.pi*v["r"]**2,"r":lambda v:math.sqrt(v["a"]/math.pi)}),
 C("General","WarDogs","d = √((xₜ−xₘ)²+(yₜ−yₘ)²); bearing = 90° − atan2(yₜ−yₘ, xₜ−xₘ)",[I("mortar_x","Mortar X"),I("mortar_y","Mortar Y"),I("target_x","Target X"),I("target_y","Target Y")],"Distance and bearing","none",lambda v:wardogs_solution(v["mortar_x"],v["mortar_y"],v["target_x"],v["target_y"])["distance"],"Compass bearing is measured clockwise from North and normalized to 0–360°."),
 C("Propulsion","Isentropic flow","Ideal-gas static/total and area relations",[I("mach","Mach number","none","2"),I("gamma","Specific-heat ratio γ","none","1.4"),I("temperature","Total temperature Tₜ (K)","none","300"),I("pressure","Total pressure","pressure","1","bar"),I("gas_constant","Gas constant R (J/kg·K)","none","287.05")],"Flow properties","none",lambda v:0,"Calorically perfect gas, steady adiabatic reversible flow; equations follow NASA Glenn isentropic relations."),
 C("Propulsion","Rocket thrust","F = ṁVe + (Pe−Pa)Ae",[I("mass_flow","Propellant mass flow","mass_flow"),I("velocity","Exit velocity","speed"),I("exit_pressure","Exit pressure","pressure"),I("ambient_pressure","Ambient pressure","pressure","101.325","kPa"),I("exit_area","Exit area","area")],"Thrust","force",lambda v:v["mass_flow"]*v["velocity"]+(v["exit_pressure"]-v["ambient_pressure"])*v["exit_area"],"Steady one-dimensional gross momentum and pressure thrust."),
 C("Propulsion","Specific impulse","Isp = F/(ṁg₀)",[I("thrust","Thrust","force"),I("mass_flow","Propellant mass flow","mass_flow")],"Specific impulse","time",lambda v:v["thrust"]/(v["mass_flow"]*9.80665)),
 C("Propulsion","Effective exhaust velocity","c = Isp g₀",[I("isp","Specific impulse","time")],"Effective exhaust velocity","speed",lambda v:v["isp"]*9.80665),
 C("Propulsion","Propellant mass flow","ṁ = F/(Isp g₀)",[I("thrust","Thrust","force"),I("isp","Specific impulse","time")],"Mass flow","mass_flow",lambda v:v["thrust"]/(v["isp"]*9.80665)),
 C("Propulsion","Mixture ratio","O/F = oxidizer flow / fuel flow",[I("oxidizer","Oxidizer mass flow","mass_flow"),I("fuel","Fuel mass flow","mass_flow")],"Oxidizer/fuel ratio","none",lambda v:v["oxidizer"]/v["fuel"]),
 C("Propulsion","Nozzle exit state","Isentropic expansion from chamber total conditions",[I("total_pressure","Chamber total pressure","pressure"),I("total_temperature","Chamber total temperature","temperature_abs"),I("exit_pressure","Exit static pressure","pressure"),I("gamma","Specific-heat ratio","none","1.2"),I("gas_constant","Gas constant (J/kg·K)","none","355")],"Exit state","none",lambda v:0,"Ideal calorically perfect, one-dimensional isentropic expansion."),
 C("Propulsion","Standard atmosphere","Troposphere ISA approximation",[I("altitude","Geopotential altitude","length")],"Atmosphere properties","none",lambda v:0,"1976-style sea-level constants with a −6.5 K/km lapse rate; this compact model is limited to 0–11 km."),
]

# Compact, editable presets. Values stay as user-facing text/unit pairs so the
# UI applies them exactly like manually entered data.
PRESETS = {
    ("Electrical","PCB traces"): {
        "1 oz copper": {"rise":("10","K or °C"),"thickness":("0.03479","mm")},
        "2 oz copper": {"rise":("10","K or °C"),"thickness":("0.06958","mm")},
        "0.5 oz copper": {"rise":("10","K or °C"),"thickness":("0.0174","mm")},
    },
    ("Structural","Euler buckling load"): {
        "Structural steel": {"e":("200000","MPa")},
        "Aluminum 6061": {"e":("68900","MPa")},
    },
    ("Fluids","Hydrostatic pressure"): {
        "Fresh water": {"rho":("998","kg/m³"),"g":("9.80665","m/s²")},
        "Seawater": {"rho":("1025","kg/m³"),"g":("9.80665","m/s²")},
        "Air": {"rho":("1.225","kg/m³"),"g":("9.80665","m/s²")},
    },
    ("Thermal","Sensible heat"): {
        "Water": {"c":("4.186","kJ/(kg·K)")},
        "Aluminum": {"c":("0.897","kJ/(kg·K)")},
        "Steel": {"c":("0.49","kJ/(kg·K)")},
    },
    ("Thermal","Conduction heat rate"): {
        "Copper": {"k":("400","W/(m·K)")},
        "Aluminum": {"k":("205","W/(m·K)")},
        "Steel": {"k":("50","W/(m·K)")},
    },
    ("Propulsion","Isentropic flow"): {
        "Air": {"gamma":("1.4",""),"gas_constant":("287.05","")},
        "Helium": {"gamma":("1.667",""),"gas_constant":("2077.1","")},
    },
}

def presets_for(calculation):
    return PRESETS.get((calculation.discipline,calculation.name),{})

def warnings_for(calculation,values,answer):
    """Return concise model/range warnings; never claims standards compliance."""
    warnings=[]
    if calculation.name=="Factor of safety" and answer<1:warnings.append("Factor of safety is below 1; applied stress exceeds the entered strength.")
    if calculation.name=="Reynolds number":
        if answer<2300:warnings.append("Flow is in the commonly approximated laminar range.")
        elif answer<4000:warnings.append("Flow is in the transitional range; regime-dependent results are uncertain.")
    if calculation.name=="PCB traces" and values.get("rise",10)<10:warnings.append("IPC-2221 trace estimates are poorly constrained for temperature rises below 10 °C.")
    if calculation.name=="Heatsink requirement" and answer<0:warnings.append("The entered junction-to-case/interface resistances already exceed the thermal-resistance budget.")
    if calculation.name=="Linear power derating" and answer>values.get("rated",answer):warnings.append("Ambient is below the full-rating temperature; do not exceed the entered nameplate rating.")
    return warnings

def validate_inputs(calculation,values):
    name=calculation.name
    positive={
        "Voltage divider":("r1","r2"),"Wire sizing & voltage drop":("current","length","voltage","drop"),
        "PCB traces":("current","rise","thickness"),"LC resonant frequency":("f","l","c"),
        "RC time constant":("tau","r","c"),"RC cutoff frequency":("resistance","capacitance"),
        "Inductive reactance":("frequency","inductance"),"Capacitive reactance":("frequency","capacitance"),
        "Power ratio decibels":("p1","p2"),"Amplitude ratio decibels":("a1","a2"),
        "Bearing L10 life":("capacity","load","exponent"),"Euler buckling load":("e","i","k","l"),
    }
    for key in positive.get(name,()):
        if key in values and values[key]<=0:raise ValueError(f"{key.replace('_',' ').title()} must be positive")
    if name=="Wire sizing & voltage drop" and values.get("drop",1)>100:raise ValueError("Maximum voltage drop must not exceed 100%")
    if name=="Voltage divider" and "vin" in values and "vout" in values and not 0<values["vout"]<values["vin"]:raise ValueError("Output voltage must be between zero and input voltage")
    if name=="Linear interpolation" and values["x2"]==values["x1"]:raise ValueError("x₁ and x₂ must be different")
    if name=="LED current resistor" and values["supply"]<=values["forward"]:raise ValueError("Supply voltage must exceed LED forward voltage")
    for key in ("efficiency","pf","emissivity","coefficient"):
        if key in values and name in ("Battery runtime","Three-phase real power","Pump hydraulic power","Radiation heat rate","Orifice flow","Choked gas mass flow"):
            if not 0<values[key]<=1:raise ValueError(f"{key.replace('_',' ').title()} must be greater than 0 and no more than 1")
    if name=="Tube section inertia" and values["outer"]<=values["inner"]:raise ValueError("Outer diameter must exceed inner diameter")
    if name=="Linear power derating" and values["zero"]<=values["full"]:raise ValueError("Zero-power temperature must exceed full-rating temperature")
    if name=="Haaland friction factor" and values["reynolds"]<=0:raise ValueError("Reynolds number must be positive")
    if name=="Simply supported point reaction" and not 0<=values["position"]<=values["span"]:raise ValueError("Load position must lie between the supports")
    if name=="I-section strong-axis inertia" and (values["web"]>=values["width"] or 2*values["flange"]>=values["height"]):raise ValueError("Web/flange dimensions must fit inside the overall section")

DISCIPLINES = list(dict.fromkeys(c.discipline for c in CALCULATIONS))
def calculations_for(discipline): return [c for c in CALCULATIONS if c.discipline == discipline]
def to_base(value, dimension, unit, variables=None): return parse_quantity(value, dimension, unit, UNITS, variables).base_value
def from_base(value, dimension, unit):
    shown=value / UNITS[dimension][unit]
    return shown-273.15 if dimension=="temperature_abs" and unit=="°C" else shown
def best_unit(value,dimension):
    candidates=AUTO_UNITS.get(dimension,tuple(UNITS.get(dimension,{})))
    if not candidates:return ""
    nonzero=abs(float(value))
    if nonzero==0:return candidates[0]
    suitable=[unit for unit in candidates if 1<=nonzero/UNITS[dimension][unit]<1000]
    if suitable:return suitable[0]
    return min(candidates,key=lambda unit:abs(math.log10(nonzero/UNITS[dimension][unit])))

# User-facing summaries shown by the Engineering tab's compact info panel.
# Keep these concise; longer limitations and assumptions belong in Calculation.note.
DESCRIPTIONS = {
    ("Electrical", "Ohm’s law"): "Relates voltage, current, and resistance in a resistive electrical path.",
    ("Electrical", "DC power"): "Relates electrical power to DC voltage and current.",
    ("Electrical", "Voltage divider"): "Finds the unloaded output of two series resistors connected across a voltage source.",
    ("Electrical", "PCB traces"): "Estimates external and internal copper widths for a chosen current and temperature rise.",
    ("Electrical", "Wire sizing & voltage drop"): "Screens copper wire gauge using current capacity and round-trip resistive voltage drop.",
    ("Electrical", "Series / parallel resistance"): "Combines two or more resistors using both series and parallel connections.",
    ("Electrical", "RC time constant"): "Describes the characteristic charging or discharging time of a resistor-capacitor network.",
    ("Electrical", "LC resonant frequency"): "Finds the ideal natural frequency of an inductor-capacitor network.",
    ("Mechanical", "Newton’s second law"): "Relates net force, mass, and linear acceleration.",
    ("Mechanical", "Rotational power"): "Relates shaft torque, angular velocity, and mechanical power.",
    ("Mechanical", "Kinetic energy"): "Calculates the translational energy associated with mass and speed.",
    ("Mechanical", "Hooke’s law"): "Models an ideal linear spring within its elastic range.",
    ("Mechanical", "Factor of safety"): "Compares material capacity with the applied working stress.",
    ("Structural", "Axial stress"): "Calculates average normal stress from concentric axial force and area.",
    ("Structural", "Axial strain"): "Measures axial deformation relative to original length.",
    ("Structural", "Euler buckling load"): "Estimates ideal elastic buckling of a slender column.",
    ("Fluids", "Hydrostatic pressure"): "Calculates pressure created by a stationary fluid column.",
    ("Fluids", "Volume flow"): "Relates average flow velocity, cross-sectional area, and volumetric flow rate.",
    ("Fluids", "Reynolds number"): "Compares inertial and viscous effects to characterize a flow regime.",
    ("Thermal", "Sensible heat"): "Calculates energy required for a temperature change without phase change.",
    ("Thermal", "Conduction heat rate"): "Models steady one-dimensional heat conduction through a uniform layer.",
    ("Thermal", "Linear thermal expansion"): "Estimates dimensional change caused by a uniform temperature change.",
    ("General", "Linear interpolation"): "Estimates a value between two known points on a straight line.",
    ("General", "Vector magnitude"): "Calculates Euclidean magnitude from orthogonal vector components.",
    ("General", "Circle area"): "Relates a circle’s radius to its enclosed area.",
    ("Propulsion", "Isentropic flow"): "Relates static and total properties for ideal compressible flow without losses or heat transfer.",
}

def description_for(calculation):
    description=DESCRIPTIONS.get((calculation.discipline,calculation.name))
    if description:return description
    if calculation.note:return calculation.note.split(".",1)[0].strip()+"."
    return f"Calculates {calculation.output_label.lower()} from the displayed engineering relationship."

REFERENCES = {
    ("Electrical","PCB traces"): "IPC-2221 trace-current approximation (estimate)",
    ("Electrical","Preferred resistor value"): "IEC 60063:2015 preferred number series",
    ("Electrical","Preferred capacitor value"): "IEC 60063:2015 preferred number series",
    ("Propulsion","Isentropic flow"): "NASA Glenn compressible-flow relations",
    ("Propulsion","Nozzle exit state"): "NASA Glenn isentropic-flow relations",
    ("Propulsion","Standard atmosphere"): "U.S. Standard Atmosphere 1976 troposphere model",
    ("Fluids","Choked gas mass flow"): "Ideal-gas isentropic nozzle relation",
    ("Thermal","Radiation heat rate"): "CODATA Stefan–Boltzmann constant",
}

def reference_for(calculation):return REFERENCES.get((calculation.discipline,calculation.name),"")
