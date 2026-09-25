"""Scientific arithmetic operations using the standard math module."""
import math
from typing import Union

Number = Union[int, float]


def sqrt(x: Number) -> float:
    """Return the square root of x."""
    if x < 0:
        raise ValueError("Cannot take square root of a negative number")
    return math.sqrt(x)


def cbrt(x: Number) -> float:
    """Return the cube root of x. Handles negatives."""
    return math.copysign(abs(x) ** (1 / 3), x)


def log(x: Number, base: Number = math.e) -> float:
    """Return the logarithm of x with the given base (default: natural log)."""
    if x <= 0:
        raise ValueError("Logarithm undefined for non-positive numbers")
    return math.log(x, base)


def ln(x: Number) -> float:
    """Return the natural logarithm of x."""
    return log(x)


def log10(x: Number) -> float:
    """Return the base-10 logarithm of x."""
    return log(x, 10)


def sin(x: Number) -> float:
    """Return the sine of x (radians)."""
    return math.sin(x)


def cos(x: Number) -> float:
    """Return the cosine of x (radians)."""
    return math.cos(x)


def tan(x: Number) -> float:
    """Return the tangent of x (radians)."""
    return math.tan(x)


def factorial(n: int) -> int:
    """Return the factorial of n. n must be a non-negative integer."""
    if not isinstance(n, int) or n < 0:
        raise ValueError("Factorial requires a non-negative integer")
    return math.factorial(n)


def absolute(x: Number) -> Number:
    """Return the absolute value of x."""
    return abs(x)
