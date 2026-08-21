"""Unit definitions and conversion helpers."""
from collections import OrderedDict
from fractions import Fraction
import re

CATEGORIES = OrderedDict({
    "Length": OrderedDict([("Picometer (pm)", 1e-12), ("Nanometer (nm)", 1e-9), ("Micrometer (µm)", 1e-6), ("Millimeter (mm)", 1e-3), ("Centimeter (cm)", 1e-2), ("Meter (m)", 1.0), ("Kilometer (km)", 1e3), ("Inch (in)", .0254), ("Foot (ft)", .3048), ("Yard (yd)", .9144), ("Mile (mi)", 1609.344)]),
    "Mass": OrderedDict([("Microgram (µg)", 1e-9), ("Milligram (mg)", 1e-6), ("Gram (g)", 1e-3), ("Kilogram (kg)", 1.0), ("Metric tonne (t)", 1e3), ("Ounce (oz)", .028349523125), ("Pound (lb)", .45359237), ("US ton", 907.18474)]),
    "Volume": OrderedDict([("Milliliter (mL)", 1e-6), ("Liter (L)", 1e-3), ("Cubic meter (m³)", 1.0), ("US teaspoon", 4.92892159375e-6), ("US tablespoon", 1.478676478125e-5), ("US fluid ounce", 2.95735295625e-5), ("US cup", .0002365882365), ("US pint", .000473176473), ("US quart", .000946352946), ("US gallon", .003785411784)]),
    "Area": OrderedDict([("Square millimeter (mm²)", 1e-6), ("Square centimeter (cm²)", 1e-4), ("Square meter (m²)", 1.0), ("Hectare (ha)", 1e4), ("Square kilometer (km²)", 1e6), ("Square inch (in²)", .00064516), ("Square foot (ft²)", .09290304), ("Acre", 4046.8564224), ("Square mile (mi²)", 2589988.110336)]),
    "Speed": OrderedDict([("Meter/second (m/s)", 1.0), ("Kilometer/hour (km/h)", 1/3.6), ("Foot/second (ft/s)", .3048), ("Mile/hour (mph)", .44704), ("Knot (kn)", .514444444444)]),
    "Time": OrderedDict([("Microsecond (µs)", 1e-6), ("Millisecond (ms)", 1e-3), ("Second (s)", 1.0), ("Minute (min)", 60.0), ("Hour (h)", 3600.0), ("Day", 86400.0), ("Week", 604800.0)]),
    "Digital storage": OrderedDict([("Byte (B)", 1.0), ("Kilobyte (kB)", 1e3), ("Megabyte (MB)", 1e6), ("Gigabyte (GB)", 1e9), ("Terabyte (TB)", 1e12), ("Kibibyte (KiB)", 1024.0), ("Mebibyte (MiB)", 1024.0**2), ("Gibibyte (GiB)", 1024.0**3), ("Tebibyte (TiB)", 1024.0**4)]),
    "Pressure": OrderedDict([("Pascal (Pa)", 1.0), ("Kilopascal (kPa)", 1e3), ("Megapascal (MPa)", 1e6), ("Bar", 1e5), ("Atmosphere (atm)", 101325.0), ("Pounds/sq inch (psi)", 6894.757293168)]),
    "Temperature": OrderedDict([("Celsius (°C)", None), ("Fahrenheit (°F)", None), ("Kelvin (K)", None)]),
})

_QUANTITY=re.compile(r"^\s*([+-]?(?:\d+\s*/\s*\d+|(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?))\s*(.*?)\s*$")

def parse_conversion_input(text,category,selected_source):
    match=_QUANTITY.match(str(text))
    if not match:raise ValueError("Enter a valid number")
    number,suffix=match.groups();value=float(Fraction(*(int(part.strip()) for part in number.split("/",1)))) if "/" in number else float(number)
    if not suffix:return value,selected_source,False
    normalized=suffix.strip().replace("μ","µ").casefold();matches=[]
    for name in CATEGORIES[category]:
        symbol_match=re.search(r"\(([^()]*)\)\s*$",name);symbols=[name.casefold()]
        if symbol_match:symbols.append(symbol_match.group(1).replace("μ","µ").casefold())
        if normalized in symbols:matches.append(name)
    if len(matches)!=1:raise ValueError(f"Unknown or ambiguous {category.lower()} unit '{suffix}'")
    return value,matches[0],True

def convert(value, category, source, target):
    value,source,_explicit=parse_conversion_input(value,category,source)
    if category == "Temperature":
        celsius = {"Celsius (°C)": lambda x:x, "Fahrenheit (°F)": lambda x:(x-32)*5/9, "Kelvin (K)": lambda x:x-273.15}[source](value)
        return {"Celsius (°C)": lambda x:x, "Fahrenheit (°F)": lambda x:x*9/5+32, "Kelvin (K)": lambda x:x+273.15}[target](celsius)
    units = CATEGORIES[category]
    return value * units[source] / units[target]
