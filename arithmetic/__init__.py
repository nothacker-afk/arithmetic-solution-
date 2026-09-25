"""Arithmetic Super App - Core Engine."""
from .basic import add, subtract, multiply, divide, power, modulo, floor_divide
from .scientific import sqrt, cbrt, log, ln, log10, sin, cos, tan, factorial, absolute
from .matrix import matrix_add, matrix_subtract, matrix_multiply, matrix_transpose

__version__ = "0.1.0"

# Plugin system
from . import plugins  # noqa: E402,F401
