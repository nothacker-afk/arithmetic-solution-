"""Tests for basic arithmetic operations."""
import pytest
from arithmetic.basic import add, subtract, multiply, divide, power, modulo, floor_divide


def test_add():
    assert add(2, 3) == 5
    assert add(-1, 1) == 0
    assert add(2.5, 2.5) == 5.0


def test_subtract():
    assert subtract(5, 3) == 2
    assert subtract(3, 5) == -2


def test_multiply():
    assert multiply(3, 4) == 12
    assert multiply(-2, 5) == -10
    assert multiply(0.5, 4) == 2.0


def test_divide():
    assert divide(10, 2) == 5
    assert divide(7, 2) == 3.5


def test_divide_by_zero():
    with pytest.raises(ValueError):
        divide(1, 0)


def test_power():
    assert power(2, 10) == 1024
    assert power(9, 0.5) == 3.0


def test_modulo():
    assert modulo(10, 3) == 1
    with pytest.raises(ValueError):
        modulo(1, 0)


def test_floor_divide():
    assert floor_divide(10, 3) == 3
    with pytest.raises(ValueError):
        floor_divide(1, 0)
