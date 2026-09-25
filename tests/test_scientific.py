"""Tests for scientific arithmetic operations."""
import math
import pytest
from arithmetic.scientific import sqrt, cbrt, log, ln, log10, sin, cos, tan, factorial, absolute


def test_sqrt():
    assert sqrt(9) == 3.0
    with pytest.raises(ValueError):
        sqrt(-1)


def test_cbrt():
    assert cbrt(27) == pytest.approx(3.0)
    assert cbrt(-8) == pytest.approx(-2.0)


def test_log():
    assert log(100, 10) == pytest.approx(2.0)
    with pytest.raises(ValueError):
        log(-1)


def test_ln():
    assert ln(math.e) == pytest.approx(1.0)


def test_log10():
    assert log10(1000) == pytest.approx(3.0)


def test_trig():
    assert sin(0) == pytest.approx(0.0)
    assert cos(0) == pytest.approx(1.0)
    assert tan(0) == pytest.approx(0.0)


def test_factorial():
    assert factorial(5) == 120
    assert factorial(0) == 1
    with pytest.raises(ValueError):
        factorial(-1)


def test_absolute():
    assert absolute(-5) == 5
    assert absolute(3.14) == 3.14
