"""Safe arithmetic expression evaluation."""
import ast
import math
import operator
import re

_BINARY = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
           ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
           ast.Mod: operator.mod, ast.Pow: operator.pow}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_CONSTANTS = {"pi": math.pi, "e": math.e}
_FUNCTIONS = {
    "sqrt": math.sqrt,
    "cbrt": math.cbrt,
    "root": lambda value, degree: value ** (1 / degree),
    "factorial": math.factorial,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "ln": math.log,
    "log": math.log10,
    "log10": math.log10,
    "log2": math.log2,
    "logbase": lambda value, base: math.log(value, base),
    "exp": math.exp,
    "abs": abs,
    "floor": math.floor,
    "ceil": math.ceil,
    "degrees": math.degrees,
    "radians": math.radians,
    "gcd": math.gcd,
}

def evaluate(expression, variables=None):
    # MathLive's ASCII form writes nth roots as root(degree)(value).
    # Convert innermost instances to the evaluator's root(value, degree).
    root_pattern = re.compile(r"root\(([^()]*)\)\(([^()]*)\)")
    while root_pattern.search(expression):
        expression = root_pattern.sub(r"root(\2,\1)", expression)
    expression = re.sub(r"log\s*_([^()\s]+)\(([^()]*)\)", r"logbase(\2,\1)", expression)
    expression = (expression.strip()
                  .replace("ⁿ√", "root")
                  .replace("∛", "cbrt")
                  .replace("√", "sqrt")
                  .replace("π", "pi")
                  .replace("^", "**")
                  .replace("×", "*")
                  .replace("÷", "/")
                  .replace("−", "-"))
    if "□" in expression:
        raise ValueError("Fill in every □ first")
    if not expression:
        return 0
    if len(expression) > 500:
        raise ValueError("Expression is too long")
    return _evaluate_node(ast.parse(expression, mode="eval").body, variables)

def _evaluate_node(node, variables=None):
    variables = variables or {}
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Name) and node.id in _CONSTANTS:
        return _CONSTANTS[node.id]
    if isinstance(node, ast.Name) and node.id in variables:
        return variables[node.id]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in ("integral", "derivative", "summation"):
        name = node.func.id
        if name == "integral" and len(node.args) == 3:
            lower, upper = _evaluate_node(node.args[1], variables), _evaluate_node(node.args[2], variables)
            steps = 1000; width = (upper - lower) / steps
            total = _evaluate_node(node.args[0], {**variables, "x": lower}) + _evaluate_node(node.args[0], {**variables, "x": upper})
            for index in range(1, steps):
                total += (4 if index % 2 else 2) * _evaluate_node(node.args[0], {**variables, "x": lower + index * width})
            return total * width / 3
        if name == "derivative" and len(node.args) == 2:
            point = _evaluate_node(node.args[1], variables); step = 1e-5 * max(1, abs(point))
            high = _evaluate_node(node.args[0], {**variables, "x": point + step})
            low = _evaluate_node(node.args[0], {**variables, "x": point - step})
            return (high - low) / (2 * step)
        if name == "summation" and len(node.args) == 3:
            start, end = int(_evaluate_node(node.args[1], variables)), int(_evaluate_node(node.args[2], variables))
            if abs(end - start) > 100000: raise ValueError("Summation range is too large")
            return sum(_evaluate_node(node.args[0], {**variables, "x": value}) for value in range(start, end + 1))
        raise ValueError(f"Invalid {name} arguments")
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCTIONS:
        if node.keywords or len(node.args) > 2:
            raise ValueError("Invalid function arguments")
        arguments = [_evaluate_node(argument, variables) for argument in node.args]
        if node.func.id in ("factorial", "gcd"):
            if any(not float(argument).is_integer() for argument in arguments):
                raise ValueError(f"{node.func.id} requires whole numbers")
            arguments = [int(argument) for argument in arguments]
        if node.func.id == "factorial" and arguments and arguments[0] > 1000:
            raise ValueError("Factorial input is too large")
        return _FUNCTIONS[node.func.id](*arguments)
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        left, right = _evaluate_node(node.left, variables), _evaluate_node(node.right, variables)
        if isinstance(node.op, ast.Pow) and abs(right) > 1000:
            raise ValueError("Exponent is too large")
        return _BINARY[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_evaluate_node(node.operand, variables))
    raise ValueError("Unsupported expression")

def format_number(value, precision=12):
    if isinstance(value, complex) or not math.isfinite(float(value)):
        raise ValueError("Result is not a finite real number")
    precision = max(1, min(15, int(precision)))
    return str(int(value)) if float(value).is_integer() else f"{value:.{precision}g}"


def format_measurement(value, unit="", precision=6):
    """Format a displayed measurement to useful, unit-appropriate precision."""
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("Result is not a finite real number")
    if number == 0:
        return "0"

    decimal_caps = {
        "mil": 2, "mm": 3, "µm": 2, "cm": 3, "m": 4,
        "in": 4, "ft": 3, "m²": 4, "mm²": 3, "cm²": 3,
        "in²": 4, "ft²": 3, "K": 2, "K or °C": 2,
        "°F difference": 2, "%": 2,
    }
    cap = decimal_caps.get(unit, 6)
    magnitude = math.floor(math.log10(abs(number)))
    precision = max(1, min(15, int(precision)))
    decimals = max(0, min(cap, precision - 1 - magnitude))
    rounded = round(number, decimals)
    if rounded == 0 or abs(number) >= 1e9:
        return f"{number:.{precision}g}"
    return f"{rounded:.{decimals}f}".rstrip("0").rstrip(".")


def format_engineering(value, precision=6):
    """Format a finite number with an exponent divisible by three."""
    number=float(value);precision=max(1,min(15,int(precision)))
    if not math.isfinite(number):raise ValueError("Result is not a finite real number")
    if number==0:return "0"
    exponent=3*math.floor(math.log10(abs(number))/3);mantissa=number/(10**exponent)
    return f"{mantissa:.{precision}g}e{exponent:+d}"
