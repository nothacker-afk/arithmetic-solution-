"""Safe arithmetic expression evaluator with step-by-step breakdown.

NEVER uses eval() or exec(). Uses Python's `ast` module with a strict
whitelist of node types, operators, and functions.
"""
from __future__ import annotations
import ast
import math
import operator
import re as _re
from typing import Any, Callable, Dict, List, Optional

from .physics_constants import CONSTANTS, UNITS


_BIN_OPS: Dict[type, Callable] = {
    ast.Add:      operator.add,
    ast.Sub:      operator.sub,
    ast.Mult:     operator.mul,
    ast.Div:      operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod:      operator.mod,
    ast.Pow:      operator.pow,
}

_UNARY_OPS: Dict[type, Callable] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

_OP_SYMBOLS = {
    operator.add: "+", operator.sub: "-", operator.mul: "×",
    operator.truediv: "÷", operator.floordiv: "//", operator.mod: "mod",
    operator.pow: "^",
}

_FUNCTIONS: Dict[str, Callable] = {
    "sqrt": math.sqrt, "cbrt": lambda x: math.copysign(abs(x) ** (1/3), x),
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "asin": math.asin, "acos": math.acos, "atan": math.atan,
    "sinh": math.sinh, "cosh": math.cosh, "tanh": math.tanh,
    "log": math.log, "log10": math.log10, "log2": math.log2,
    "ln": math.log, "exp": math.exp,
    "abs": abs, "floor": math.floor, "ceil": math.ceil,
    "round": round, "pow": pow,
    "min": min, "max": max,
    "deg": math.degrees, "rad": math.radians,
    "fact": math.factorial,
}


class CalcError(ValueError):
    pass


def _fmt(v: Any) -> str:
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        if v == int(v) and abs(v) < 1e15:
            return str(int(v))
        if v == 0:
            return "0"
        if abs(v) >= 1e15 or abs(v) < 1e-4:
            return f"{v:.6e}"
        return f"{v:.10g}"
    return str(v)


class _Evaluator(ast.NodeVisitor):
    def __init__(self, variables: Dict[str, float]):
        self.vars = variables
        self.steps: List[dict] = []

    def visit_Constant(self, node):
        if isinstance(node.value, (int, float)):
            return node.value
        raise CalcError(f"Unsupported literal: {node.value!r}")

    def visit_Name(self, node):
        if node.id in self.vars:
            return self.vars[node.id]
        raise CalcError(f"Unknown symbol: '{node.id}'")

    def visit_UnaryOp(self, node):
        op = _UNARY_OPS.get(type(node.op))
        if op is None:
            raise CalcError("Unsupported unary operator")
        operand = self.visit(node.operand)
        result = op(operand)
        sym = "-" if isinstance(node.op, ast.USub) else "+"
        self.steps.append({
            "kind": "unary", "op": sym,
            "expr": f"{sym}{_fmt(operand)}",
            "result": result, "result_str": _fmt(result),
        })
        return result

    def visit_BinOp(self, node):
        op = _BIN_OPS.get(type(node.op))
        if op is None:
            raise CalcError("Unsupported operator")
        left = self.visit(node.left)
        right = self.visit(node.right)
        sym = _OP_SYMBOLS.get(op, "?")
        try:
            result = op(left, right)
        except ZeroDivisionError:
            raise CalcError("Division by zero")
        except Exception as e:
            raise CalcError(f"Operation failed: {e}")
        self.steps.append({
            "kind": "binary", "op": sym,
            "expr": f"{_fmt(left)} {sym} {_fmt(right)}",
            "left": left, "right": right,
            "result": result, "result_str": _fmt(result),
        })
        return result

    def visit_Call(self, node):
        if not isinstance(node.func, ast.Name):
            raise CalcError("Only simple function calls are allowed")
        name = node.func.id
        fn = _FUNCTIONS.get(name)
        if fn is None:
            raise CalcError(f"Unknown function: '{name}'")
        args = [self.visit(a) for a in node.args]
        try:
            result = fn(*args)
        except ZeroDivisionError:
            raise CalcError("Division by zero")
        except ValueError as e:
            raise CalcError(f"{name}() error: {e}")
        except Exception as e:
            raise CalcError(f"{name}() failed: {e}")
        args_str = ", ".join(_fmt(a) for a in args)
        self.steps.append({
            "kind": "function", "op": name,
            "expr": f"{name}({args_str})",
            "result": result, "result_str": _fmt(result),
        })
        return result

    def generic_visit(self, node):
        raise CalcError(f"Disallowed syntax: {type(node).__name__}")


_UNIT_RE = _re.compile(
    r"(?<![\w.])(-?\d+(?:\.\d+)?(?:e[+-]?\d+)?)\s*([a-zA-Z]+)\b",
    _re.IGNORECASE,
)


def _convert_units(expr: str):
    """Replace '5 km' with '(5 * 1000)'. Handle constant/unit conflicts."""
    steps = []

    def repl(m):
        num_str, unit = m.group(1), m.group(2)
        unit_lower = unit.lower()

        if unit_lower in _FUNCTIONS or unit in _FUNCTIONS:
            return m.group(0)

        # Constant → explicit multiplication
        if unit in CONSTANTS:
            return f"({num_str} * {unit})"

        factor = UNITS.get(unit) or UNITS.get(unit_lower)
        if factor is None or factor is True:
            return m.group(0)

        try:
            value = float(num_str)
        except ValueError:
            return m.group(0)

        si_value = value * factor
        steps.append({
            "kind": "unit",
            "expr": f"{num_str} {unit}",
            "result": si_value,
            "result_str": f"{_fmt(si_value)} (SI)",
            "note": f"1 {unit} = {_fmt(factor)} SI",
        })
        return f"({num_str} * {factor})"

    new_expr = _UNIT_RE.sub(repl, expr)
    return new_expr, steps


# =====================================================================
# Implicit multiplication normalizer
# =====================================================================
def _normalize_implicit_multiplication(expr: str) -> str:
    """Insert explicit '*' for common implicit-multiplication forms.

    Handles:
        2x       → 2*x
        2(x+1)   → 2*(x+1)
        (x+1)2   → (x+1)*2
        (x+1)(y) → (x+1)*(y)
        x(y+1)   → x*(y+1)     (unless x is a known function name)

    Does NOT touch:
        sin(x), log10(x), sqrt(y)  — function calls
        log10                      — identifier with trailing digits
    """
    # 1. Number followed by identifier: "2x" → "2*x"
    #    Negative lookbehind prevents matching inside identifiers like "log10x"
    expr = _re.sub(
        r"(?<![a-zA-Z_0-9])(\d+(?:\.\d+)?)\s*([a-zA-Z_])",
        r"\1*\2",
        expr,
    )

    # 2. Number followed by open paren: "2(x" → "2*(x"
    expr = _re.sub(r"(\d)\s*\(", r"\1*(", expr)

    # 3. Close paren followed by identifier/digit/paren: ")x" → ")*x"
    expr = _re.sub(r"\)\s*([a-zA-Z_0-9(])", r")*\1", expr)

    # 4. Identifier followed by open paren (not a function call)
    def _maybe_mul(m):
        ident = m.group(1)
        if ident in _FUNCTIONS:
            return m.group(0)  # keep sin(x), log10(x), etc.
        return f"{ident}*("

    expr = _re.sub(r"([a-zA-Z_][a-zA-Z_0-9]*)\s*\(", _maybe_mul, expr)

    return expr


def evaluate(expression: str, extra_vars: Optional[Dict[str, float]] = None) -> dict:
    """Evaluate an expression and return a dict with steps."""
    if not expression or not expression.strip():
        raise CalcError("Empty expression")

    original = expression.strip()
    expr = original
    expr = expr.replace("^", "**")
    expr = expr.replace("×", "*").replace("÷", "/")
    expr = expr.replace("−", "-")
    expr = _re.sub(r"\bmod\b", "%", expr, flags=_re.IGNORECASE)
    expr = _re.sub(r"√", "sqrt", expr)

    expr = _normalize_implicit_multiplication(expr)
    expr, unit_steps = _convert_units(expr)

    variables = dict(CONSTANTS)
    if extra_vars:
        variables.update(extra_vars)

    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise CalcError(f"Syntax error: {e.msg}")

    ev = _Evaluator(variables)
    try:
        result = ev.visit(tree.body)
    except CalcError:
        raise
    except Exception as e:
        raise CalcError(f"Evaluation failed: {e}")

    if isinstance(result, complex):
        raise CalcError("Complex results are not supported yet")
    if not isinstance(result, (int, float)):
        raise CalcError("Expression did not produce a number")

    used = []
    for name in _re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", expr):
        if name in CONSTANTS and name not in ("pi", "euler", "tau"):
            used.append(name)

    return {
        "expression": original,
        "normalized": expr,
        "result": float(result) if isinstance(result, float) else result,
        "result_str": _fmt(result),
        "steps": unit_steps + ev.steps,
        "constants_used": sorted(set(used)),
    }


def _step(note: str, expr: str, value, unit: str = "") -> dict:
    return {"note": note, "expr": expr, "value": value, "unit": unit}


# =====================================================================
# Phase 89 — Linear equation solver
# =====================================================================
def solve_linear(equation: str, variable: str = "x") -> dict:
    """Solve a linear equation of the form a*x + b = c*x + d.

    Uses expression evaluation at var=0, 1, 2 to extract coefficients.
    This handles every syntactic form the evaluator accepts:
        "2x + 5 = 15"       → x = 5
        "3x - 7 = 2x + 3"   → x = 10
        "x/2 + 3 = 7"       → x = 8
        "-4x = 8"           → x = -2
    Non-linear equations raise CalcError.
    """
    if not equation or "=" not in equation:
        raise CalcError("Equation must contain '='")

    parts = equation.split("=")
    if len(parts) != 2:
        raise CalcError("Equation must have exactly one '='")

    left = parts[0].strip()
    right = parts[1].strip()
    var = (variable or "x").strip()
    if not var.isidentifier():
        raise CalcError(f"Invalid variable name: {var!r}")

    def eval_at(side_expr: str, val: float) -> float:
        """Evaluate one side at var=val."""
        try:
            r = evaluate(side_expr, extra_vars={var: float(val)})
        except CalcError as e:
            raise CalcError(f"Cannot evaluate {side_expr!r}: {e}")
        result = r["result"]
        if not isinstance(result, (int, float)):
            raise CalcError(f"Side {side_expr!r} did not produce a number")
        return float(result)

    def extract(side_expr: str):
        """Return (coef, const) for a linear side of the equation."""
        f0 = eval_at(side_expr, 0.0)
        f1 = eval_at(side_expr, 1.0)
        f2 = eval_at(side_expr, 2.0)

        a = f1 - f0                # coefficient
        b = f0                     # constant term

        # Linear check: second difference should be zero
        curvature = (f2 - f1) - (f1 - f0)
        if abs(curvature) > 1e-9 * max(1.0, abs(a), abs(b)):
            raise CalcError(
                f"Equation is not linear in '{var}' "
                f"(curvature detected in {side_expr!r})"
            )
        return a, b

    a_left, b_left = extract(left)
    a_right, b_right = extract(right)

    # (a_left * x + b_left) = (a_right * x + b_right)
    # → (a_left - a_right) * x = b_right - b_left
    a = a_left - a_right
    b = b_right - b_left

    if abs(a) < 1e-12:
        if abs(b) < 1e-12:
            return {
                "solution": None,
                "variable": var,
                "message": "Infinite solutions (equation is an identity)",
                "steps": [
                    _step("Both sides are identical for all values",
                          "0 = 0", 0),
                ],
                "coefficients": {"a": a, "b": b},
            }
        return {
            "solution": None,
            "variable": var,
            "message": "No solution (contradiction)",
            "steps": [
                _step("Reduced to a false statement",
                      f"{_fmt(b)} = 0 (contradiction)", b),
            ],
            "coefficients": {"a": a, "b": b},
        }

    solution = b / a
    steps = [
        _step("Isolate variable terms on the left",
              f"{_fmt(a)}{var} = {_fmt(b)}", None),
        _step(f"Divide both sides by {_fmt(a)}",
              f"{var} = {_fmt(b)} / {_fmt(a)}", None),
        _step("Solution",
              f"{var} = {_fmt(solution)}", solution),
    ]
    return {
        "solution": solution,
        "variable": var,
        "message": "Unique solution",
        "steps": steps,
        "coefficients": {"a": a, "b": b},
    }
