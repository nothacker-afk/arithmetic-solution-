"""Scientific arithmetic operations using the standard math module."""
import math

def sqrt(x):
    """Return the square root of x."""
    if x < 0:
        raise ValueError("Cannot take square root of a negative number")
    return math.sqrt(x)

def cbrt(x):
    """Return the cube root of x. Handles negatives."""
    return math.copysign(abs(x) ** (1 / 3), x)

def log(x, base=math.e):
    """Return the logarithm of x with the given base."""
    if x <= 0:
        raise ValueError("Logarithm undefined for non-positive numbers")
    return math.log(x, base)

def ln(x):
    """Return the natural logarithm of x."""
    return log(x)

def log10(x):
    """Return the base-10 logarithm of x."""
    return log(x, 10)

def sin(x):
    """Return the sine of x (radians)."""
    return math.sin(x)

def cos(x):
    """Return the cosine of x (radians)."""
    return math.cos(x)

def tan(x):
    """Return the tangent of x (radians)."""
    return math.tan(x)

def factorial(n):
    """Return the factorial of n."""
    if not isinstance(n, int) or n < 0:
        raise ValueError("Factorial requires a non-negative integer")
    return math.factorial(n)

def absolute(x):
    """Return the absolute value of x."""
    return abs(x)
