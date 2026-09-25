"""Basic arithmetic operations."""
from typing import Union
Number = Union[int, float]

def add(x, y):
    """Return the sum of x and y."""
    return x + y

def subtract(x, y):
    """Return the difference of x and y."""
    return x - y

def multiply(x, y):
    """Return the product of x and y."""
    return x * y

def divide(x, y):
    """Return the quotient of x and y. Raises ValueError on divide by zero."""
    if y == 0:
        raise ValueError("Cannot divide by zero")
    return x / y

def power(x, y):
    """Return x raised to the power of y."""
    return x ** y

def modulo(x, y):
    """Return the remainder of x divided by y."""
    if y == 0:
        raise ValueError("Cannot modulo by zero")
    return x % y

def floor_divide(x, y):
    """Return the floor division of x by y."""
    if y == 0:
        raise ValueError("Cannot floor-divide by zero")
    return x // y
