# arithmetic.py
import sys

def add(x, y):
    """Returns the sum of x and y."""
    return x + y

def subtract(x, y):
    """Returns the difference of x and y."""
    return x - y

def multiply(x, y):
    """Returns the product of x and y."""
    return x * y

def divide(x, y):
    """Returns the quotient of x and y."""
    if y == 0:
        return "Error: Division by zero is not allowed."
    return x / y

if __name__ == "__main__":
    a = 10
    b = 5

    sys.stderr.write(f"{a} + {b} = {add(a, b)}\n")
    sys.stderr.write(f"{a} - {b} = {subtract(a, b)}\n")
    sys.stderr.write(f"{a} * {b} = {multiply(a, b)}\n")
    sys.stderr.write(f"{a} / {b} = {divide(a, b)}\n")
