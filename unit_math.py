"""Small safe evaluator for arithmetic containing explicit engineering units."""
import ast
from dataclasses import dataclass
import re


VECTORS={
    "none":(0,0,0,0),"length":(1,0,0,0),"area":(2,0,0,0),"moment4":(4,0,0,0),
    "mass":(0,1,0,0),"time":(0,0,1,0),"current":(0,0,0,1),
    "speed":(1,0,-1,0),"acceleration":(1,0,-2,0),"frequency":(0,0,-1,0),
    "force":(1,1,-2,0),"pressure":(-1,1,-2,0),"energy":(2,1,-2,0),
    "torque":(2,1,-2,0),"power":(2,1,-3,0),"voltage":(2,1,-3,-1),
    "resistance":(2,1,-3,-2),"capacitance":(-2,-1,4,2),"inductance":(2,1,-2,-2),
    "density":(-3,1,0,0),"volume_flow":(3,0,-1,0),"mass_flow":(0,1,-1,0),
}

@dataclass(frozen=True)
class UnitValue:
    value: float
    vector: tuple
    def _coerce(self,other): return other if isinstance(other,UnitValue) else UnitValue(float(other),VECTORS["none"])
    def __add__(self,other):
        other=self._coerce(other)
        if self.vector!=other.vector:raise ValueError("Addition requires compatible units")
        return UnitValue(self.value+other.value,self.vector)
    __radd__=__add__
    def __sub__(self,other):
        other=self._coerce(other)
        if self.vector!=other.vector:raise ValueError("Subtraction requires compatible units")
        return UnitValue(self.value-other.value,self.vector)
    def __rsub__(self,other):return self._coerce(other).__sub__(self)
    def __mul__(self,other):
        other=self._coerce(other);return UnitValue(self.value*other.value,tuple(a+b for a,b in zip(self.vector,other.vector)))
    __rmul__=__mul__
    def __truediv__(self,other):
        other=self._coerce(other);return UnitValue(self.value/other.value,tuple(a-b for a,b in zip(self.vector,other.vector)))
    def __rtruediv__(self,other):return self._coerce(other).__truediv__(self)
    def __pow__(self,other):
        if isinstance(other,UnitValue):
            if any(other.vector):raise ValueError("Exponent must be unitless")
            other=other.value
        exponent=float(other)
        if not exponent.is_integer():raise ValueError("Unit powers must be integers")
        return UnitValue(self.value**exponent,tuple(int(exponent)*part for part in self.vector))
    def __neg__(self):return UnitValue(-self.value,self.vector)

def _unit_lookup(units):
    lookup={}
    for dimension,choices in units.items():
        if dimension not in VECTORS:continue
        for symbol,factor in choices.items():
            if symbol and symbol not in lookup:lookup[symbol]=(dimension,factor)
    return lookup

def contains_unit(text,units):
    return any(re.search(rf"(?<=\d)\s*{re.escape(symbol)}(?![\wµΩ°])",text) for symbol in _unit_lookup(units))

def evaluate_unit_expression(text,units):
    lookup=_unit_lookup(units);rewritten=str(text).replace("×","*").replace("÷","/")
    symbols=sorted(lookup,key=len,reverse=True)
    pattern=re.compile(r"(?<![\w.])((?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)\s*("+"|".join(map(re.escape,symbols))+r")(?![\wµΩ°])")
    rewritten=pattern.sub(lambda match:f"Q({match.group(1)},'{match.group(2)}')",rewritten)
    if "Q(" not in rewritten:raise ValueError("Include an explicit unit")
    tree=ast.parse(rewritten,mode="eval")
    def visit(node):
        if isinstance(node,ast.Expression):return visit(node.body)
        if isinstance(node,ast.Constant) and isinstance(node.value,(int,float)):return UnitValue(float(node.value),VECTORS["none"])
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):
            value=visit(node.operand);return value if isinstance(node.op,ast.UAdd) else -value
        if isinstance(node,ast.BinOp) and isinstance(node.op,(ast.Add,ast.Sub,ast.Mult,ast.Div,ast.Pow)):
            left,right=visit(node.left),visit(node.right);return {ast.Add:left.__add__,ast.Sub:left.__sub__,ast.Mult:left.__mul__,ast.Div:left.__truediv__,ast.Pow:left.__pow__}[type(node.op)](right)
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=="Q" and len(node.args)==2 and isinstance(node.args[1],ast.Constant):
            number=visit(node.args[0]).value;symbol=node.args[1].value
            if symbol not in lookup:raise ValueError("Unknown unit")
            dimension,factor=lookup[symbol];return UnitValue(number*factor,VECTORS[dimension])
        raise ValueError("Unsupported unit expression")
    result=visit(tree);dimensions=[name for name,vector in VECTORS.items() if vector==result.vector and name not in ("torque",)]
    dimension=dimensions[0] if dimensions else None
    return result,dimension
