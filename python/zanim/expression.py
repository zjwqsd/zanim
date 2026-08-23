from __future__ import annotations

from dataclasses import dataclass
from math import cos, exp, log, sin
from numbers import Real
from typing import Any


@dataclass(frozen=True, slots=True)
class ScalarExpr:
    """Small portable scalar-expression tree shared by Python/Web Scene IR.

    It is intentionally *not* a Python AST wrapper. Only this explicit numeric
    subset is portable; arbitrary Python callbacks remain runtime code and use
    sampled IR fallback when exported.
    """

    op: str
    args: tuple[Any, ...] = ()

    @staticmethod
    def constant(value: Real) -> "ScalarExpr":
        if isinstance(value, bool) or not isinstance(value, Real):
            raise TypeError("ScalarExpr constant must be a real number")
        return ScalarExpr("const", (float(value),))

    @staticmethod
    def variable(name: str) -> "ScalarExpr":
        if name not in ("x", "time"):
            raise ValueError("portable scalar variable must be 'x' or 'time'")
        return ScalarExpr("var", (name,))

    def evaluate(self, *, x: float = 0.0, time: float = 0.0) -> float:
        op = self.op
        if op == "const":
            return float(self.args[0])
        if op == "var":
            return float(x if self.args[0] == "x" else time)
        if op == "neg":
            return -_expr(self.args[0]).evaluate(x=x, time=time)
        a = _expr(self.args[0]).evaluate(x=x, time=time)
        if op == "sin":
            return sin(a)
        if op == "cos":
            return cos(a)
        if op == "exp":
            return exp(a)
        if op == "log":
            return log(a)
        if op == "abs":
            return abs(a)
        b = _expr(self.args[1]).evaluate(x=x, time=time)
        if op == "add":
            return a + b
        if op == "sub":
            return a - b
        if op == "mul":
            return a * b
        if op == "div":
            return a / b
        if op == "pow":
            return a**b
        raise ValueError(f"unsupported ScalarExpr op: {op}")

    def to_data(self):
        if self.op in ("const", "var"):
            return [self.op, self.args[0]]
        return [self.op, *(_expr(arg).to_data() for arg in self.args)]

    @staticmethod
    def from_data(value) -> "ScalarExpr":
        if not isinstance(value, list) or not value:
            raise ValueError("invalid portable scalar expression")
        op = str(value[0])
        if op == "const":
            if len(value) != 2:
                raise ValueError("const expression requires one value")
            return ScalarExpr.constant(float(value[1]))
        if op == "var":
            if len(value) != 2:
                raise ValueError("var expression requires one name")
            return ScalarExpr.variable(str(value[1]))
        unary = {"neg", "sin", "cos", "exp", "log", "abs"}
        binary = {"add", "sub", "mul", "div", "pow"}
        if op in unary and len(value) == 2:
            return ScalarExpr(op, (ScalarExpr.from_data(value[1]),))
        if op in binary and len(value) == 3:
            return ScalarExpr(op, (ScalarExpr.from_data(value[1]), ScalarExpr.from_data(value[2])))
        raise ValueError(f"invalid portable scalar expression op: {op}")

    def _binary(self, op: str, other) -> "ScalarExpr":
        return ScalarExpr(op, (self, _expr(other)))

    def __add__(self, other):
        return self._binary("add", other)

    def __radd__(self, other):
        return _expr(other)._binary("add", self)

    def __sub__(self, other):
        return self._binary("sub", other)

    def __rsub__(self, other):
        return _expr(other)._binary("sub", self)

    def __mul__(self, other):
        return self._binary("mul", other)

    def __rmul__(self, other):
        return _expr(other)._binary("mul", self)

    def __truediv__(self, other):
        return self._binary("div", other)

    def __rtruediv__(self, other):
        return _expr(other)._binary("div", self)

    def __pow__(self, other):
        return self._binary("pow", other)

    def __rpow__(self, other):
        return _expr(other)._binary("pow", self)

    def __neg__(self):
        return ScalarExpr("neg", (self,))

    def sin(self) -> "ScalarExpr":
        return ScalarExpr("sin", (self,))

    def cos(self) -> "ScalarExpr":
        return ScalarExpr("cos", (self,))

    def exp(self) -> "ScalarExpr":
        return ScalarExpr("exp", (self,))

    def log(self) -> "ScalarExpr":
        return ScalarExpr("log", (self,))

    def abs(self) -> "ScalarExpr":
        return ScalarExpr("abs", (self,))


def _expr(value) -> ScalarExpr:
    if isinstance(value, ScalarExpr):
        return value
    if isinstance(value, Real) and not isinstance(value, bool):
        return ScalarExpr.constant(value)
    raise TypeError(f"expected ScalarExpr or real number, got {type(value).__name__}")


X = ScalarExpr.variable("x")
TIME = ScalarExpr.variable("time")
