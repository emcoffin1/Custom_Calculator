"""Safe parsing of engineering quantities entered as numbers plus units."""
from dataclasses import dataclass
from fractions import Fraction
import re


_NUMBER = re.compile(r"^\s*([+-]?(?:\d+\s*/\s*\d+|(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?))\s*(.*?)\s*$")
_ALIASES = {
    "μ": "µ", "uA": "µA", "uF": "µF", "uH": "µH", "um": "µm",
    "ohm": "Ω", "ohms": "Ω", "kohm": "kΩ", "Mohm": "MΩ",
    "inch": "in", "inches": "in", '"': "in", "feet": "ft", "foot": "ft",
}


@dataclass(frozen=True)
class ParsedQuantity:
    value: float
    unit: str
    base_value: float
    explicit_unit: bool
    minimum: float
    maximum: float


def parse_quantity(text, dimension, selected_unit, units, variables=None):
    """Parse a dimension-constrained quantity without evaluating expressions."""
    raw=str(text);variable=(variables or {}).get(raw.strip())
    if isinstance(variable,dict) and "base_value" in variable:
        if variable.get("dimension")!=dimension:raise ValueError(f"Variable '{raw.strip()}' is {variable.get('dimension')}, not {dimension}")
        base=float(variable["base_value"]);shown=base/units[dimension][selected_unit]
        return ParsedQuantity(shown,selected_unit,base,False,base,base)
    parts=re.split(r"\s*(?:±|\+/-)\s*",raw,maxsplit=1);nominal_text=parts[0]
    match = _NUMBER.match(nominal_text)
    if not match:
        raise ValueError("Enter a number, optionally followed by a unit")
    number_text, typed_unit = match.groups()
    if "/" in number_text:
        numerator, denominator = (part.strip() for part in number_text.split("/", 1))
        value = float(Fraction(int(numerator), int(denominator)))
    else:
        value = float(number_text)
    typed_unit = typed_unit.strip().replace("μ", "µ")
    typed_unit = _ALIASES.get(typed_unit, typed_unit)
    unit = typed_unit or selected_unit
    choices = units.get(dimension, {})
    if unit not in choices:
        raise ValueError(f"Unit '{typed_unit}' is not valid for {dimension.replace('_', ' ')}")
    base_value=value*choices[unit]
    if dimension=="temperature_abs" and unit=="°C":base_value+=273.15
    minimum=maximum=base_value
    if len(parts)==2:
        tolerance_text=parts[1].strip()
        if tolerance_text.endswith("%"):
            percent=float(tolerance_text[:-1].strip())
            if percent<0:raise ValueError("Tolerance must not be negative")
            delta=abs(base_value)*percent/100
        else:
            tolerance=parse_quantity(tolerance_text,dimension,unit,units,variables)
            delta=abs(tolerance.value*choices[tolerance.unit]) if dimension=="temperature_abs" else abs(tolerance.base_value)
        minimum,maximum=base_value-delta,base_value+delta
    return ParsedQuantity(value, unit, base_value, bool(typed_unit), minimum, maximum)


def parse_any_quantity(text,units):
    """Parse an explicitly-unit-bearing value when its dimension is unknown."""
    matches=[]
    for dimension,choices in units.items():
        if dimension in ("none","series"):continue
        for selected in choices:
            try:
                parsed=parse_quantity(text,dimension,selected,units)
            except ValueError:
                continue
            if parsed.explicit_unit:matches.append((dimension,parsed))
            break
    unique={(dimension,parsed.unit):(dimension,parsed) for dimension,parsed in matches}
    if len(unique)!=1:raise ValueError("Include one unambiguous unit symbol")
    return next(iter(unique.values()))
