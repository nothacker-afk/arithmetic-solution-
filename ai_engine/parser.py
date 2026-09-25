"""Rule-based natural language parser for arithmetic expressions.

Handles phrases like:
    "add 5 and 3"
    "what is 15% of 240"
    "square root of 81"
    "10 divided by 4"
    "factorial of 6"
    "sin of 0"

Falls back to a clean error if the phrase can't be parsed.
"""
import re
from typing import Any, Callable, Dict, Optional

from arithmetic import (
    add, subtract, multiply, divide, power, modulo,
    sqrt, cbrt, log10, sin, cos, tan, factorial, absolute,
)

NUMBER = r"(-?\d+(?:\.\d+)?)"


class ParseError(ValueError):
    """Raised when a natural language phrase cannot be parsed."""


# -------------------------------------------------------------------------
# Binary operation patterns (require two numbers)
# -------------------------------------------------------------------------
BINARY_PATTERNS = [
    (re.compile(rf"{NUMBER}\s*(?:\+|plus|added to|and)\s*{NUMBER}", re.I), "add", add),
    (re.compile(rf"add\s+{NUMBER}\s+(?:and|to|plus)\s+{NUMBER}", re.I),      "add", add),

    (re.compile(rf"{NUMBER}\s*(?:-|minus|less)\s*{NUMBER}", re.I),           "subtract", subtract),
    (re.compile(rf"subtract\s+{NUMBER}\s+from\s+{NUMBER}", re.I),            "subtract_rev", subtract),

    (re.compile(rf"{NUMBER}\s*(?:\*|x|times|multiplied by)\s*{NUMBER}", re.I), "multiply", multiply),
    (re.compile(rf"multiply\s+{NUMBER}\s+(?:by|and|with)\s+{NUMBER}", re.I),   "multiply", multiply),

    (re.compile(rf"{NUMBER}\s*(?:/|divided by|over)\s*{NUMBER}", re.I),      "divide", divide),
    (re.compile(rf"divide\s+{NUMBER}\s+by\s+{NUMBER}", re.I),                "divide", divide),

    (re.compile(rf"{NUMBER}\s*(?:\^|\*\*|to the power of|raised to)\s*{NUMBER}", re.I), "power", power),
    (re.compile(rf"{NUMBER}\s*(?:%|mod|modulo)\s*{NUMBER}", re.I),           "modulo", modulo),
]

# -------------------------------------------------------------------------
# Percentage: "15% of 240"
# -------------------------------------------------------------------------
PERCENT_RE = re.compile(rf"{NUMBER}\s*%\s*of\s*{NUMBER}", re.I)

# -------------------------------------------------------------------------
# Unary operation patterns (require one number)
# -------------------------------------------------------------------------
UNARY_PATTERNS = [
    (re.compile(rf"(?:square\s+root|sqrt)\s+of\s+{NUMBER}", re.I), "sqrt", sqrt),
    (re.compile(rf"(?:cube\s+root|cbrt)\s+of\s+{NUMBER}", re.I),   "cbrt", cbrt),
    (re.compile(rf"log(?:10)?\s+of\s+{NUMBER}", re.I),             "log10", log10),
    (re.compile(rf"sin(?:e)?\s+of\s+{NUMBER}", re.I),              "sin", sin),
    (re.compile(rf"cos(?:ine)?\s+of\s+{NUMBER}", re.I),            "cos", cos),
    (re.compile(rf"tan(?:gent)?\s+of\s+{NUMBER}", re.I),           "tan", tan),
    (re.compile(rf"factorial\s+of\s+{NUMBER}", re.I),              "factorial", factorial),
    (re.compile(rf"(?:absolute|abs)\s+(?:value\s+)?of\s+{NUMBER}", re.I), "absolute", absolute),
    (re.compile(rf"sqrt\s*\(?\s*{NUMBER}\s*\)?", re.I),            "sqrt", sqrt),
]


def _to_number(value: str) -> float:
    """Convert matched string to int if possible, else float."""
    f = float(value)
    return int(f) if f.is_integer() else f


def parse_and_solve(text: str) -> Dict[str, Any]:
    """Parse a natural-language phrase and return the result.

    Returns:
        {
            "input": <original string>,
            "operation": <str>,
            "operands": [<a>, <b>] or [<x>],
            "result": <value>,
            "expression": <human-readable>,
        }

    Raises:
        ParseError: if the phrase cannot be interpreted.
    """
    if not text or not text.strip():
        raise ParseError("Empty input.")

    text = text.strip()
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)

    # 1) Percentage: "15% of 240"
    m = PERCENT_RE.search(text)
    if m:
        pct, base = _to_number(m.group(1)), _to_number(m.group(2))
        result = (pct / 100) * base
        return {
            "input": text,
            "operation": "percent_of",
            "operands": [pct, base],
            "result": result,
            "expression": f"{pct}% of {base}",
        }

    # 2) Binary operations
    for pattern, name, func in BINARY_PATTERNS:
        m = pattern.search(text)
        if m:
            a, b = _to_number(m.group(1)), _to_number(m.group(2))
            if name == "subtract_rev":
                a, b = b, a  # "subtract 3 from 10" -> 10 - 3
                name = "subtract"
            try:
                result = func(a, b)
            except ValueError as e:
                raise ParseError(str(e))
            symbol = {
                "add": "+", "subtract": "-", "multiply": "*",
                "divide": "/", "power": "**", "modulo": "%",
            }[name]
            return {
                "input": text,
                "operation": name,
                "operands": [a, b],
                "result": result,
                "expression": f"{a} {symbol} {b}",
            }

    # 3) Unary operations
    for pattern, name, func in UNARY_PATTERNS:
        m = pattern.search(text)
        if m:
            x = _to_number(m.group(1))
            try:
                result = func(x)
            except ValueError as e:
                raise ParseError(str(e))
            return {
                "input": text,
                "operation": name,
                "operands": [x],
                "result": result,
                "expression": f"{name}({x})",
            }

    raise ParseError(f"Could not interpret: {text!r}")
