"""Arithmetic Super App - Core Engine.

A modular arithmetic library supporting basic, scientific, and matrix operations.
"""
from .basic import (
    add, subtract, multiply, divide,
    power, modulo, floor_divide,
)
from .scientific import (
    sqrt, cbrt, log, ln, log10,
    sin, cos, tan, factorial, absolute,
)
from .matrix import (
    matrix_add, matrix_subtract, matrix_multiply, matrix_transpose,
)

__version__ = "0.1.0"

__all__ = [
    "add", "subtract", "multiply", "divide",
    "power", "modulo", "floor_divide",
    "sqrt", "cbrt", "log", "ln", "log10",
    "sin", "cos", "tan", "factorial", "absolute",
    "matrix_add", "matrix_subtract", "matrix_multiply", "matrix_transpose",
]
