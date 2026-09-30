"""Tests for the safe expression evaluator."""
import math
import pytest

from web.backend.calc_engine import (
    evaluate, solve_linear, CalcError, _normalize_implicit_multiplication,
)
from web.backend.physics_constants import FORMULAS, CONSTANTS


# ---------------------------------------------------------------------
# Arithmetic
# ---------------------------------------------------------------------
def test_basic_add():
    assert evaluate("2 + 3")["result"] == 5


def test_precedence():
    assert evaluate("2 + 3 * 4")["result"] == 14


def test_parens():
    assert evaluate("(2 + 3) * 4")["result"] == 20


def test_power():
    assert evaluate("2^10")["result"] == 1024
    assert evaluate("2 ** 10")["result"] == 1024


def test_unicode_minus():
    assert evaluate("5 − 3")["result"] == 2


def test_modulo():
    assert evaluate("17 mod 5")["result"] == 2


# ---------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------
def test_sqrt():
    assert evaluate("sqrt(144)")["result"] == 12.0


def test_cbrt():
    assert abs(evaluate("cbrt(27)")["result"] - 3.0) < 1e-9


def test_trig():
    assert abs(evaluate("sin(0)")["result"]) < 1e-9
    assert abs(evaluate("cos(0)")["result"] - 1) < 1e-9


def test_log10():
    assert abs(evaluate("log10(1000)")["result"] - 3.0) < 1e-9


def test_factorial():
    assert evaluate("fact(5)")["result"] == 120


# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------
def test_pi():
    assert abs(evaluate("pi")["result"] - math.pi) < 1e-9


def test_c():
    assert evaluate("c")["result"] == 299792458.0


# ---------------------------------------------------------------------
# Implicit multiplication
# ---------------------------------------------------------------------
def test_normalizer_2x():
    assert _normalize_implicit_multiplication("2x") == "2*x"


def test_normalizer_number_paren():
    assert _normalize_implicit_multiplication("2(x+1)") == "2*(x+1)"


def test_normalizer_keeps_function_calls():
    assert _normalize_implicit_multiplication("sin(x)") == "sin(x)"


def test_evaluate_implicit_multiplication():
    r = evaluate("2x + 5", extra_vars={"x": 3})
    assert r["result"] == 11


# ---------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------
def test_steps_recorded():
    r = evaluate("2 + 3 * 4")
    assert len(r["steps"]) == 2
    assert r["steps"][0]["result"] == 12


# ---------------------------------------------------------------------
# Unit conversion
# ---------------------------------------------------------------------
def test_km_to_m():
    assert evaluate("5 km + 300 m")["result"] == 5300.0


def test_ms_to_s():
    assert abs(evaluate("500 ms")["result"] - 0.5) < 1e-9


def test_ly_constant():
    assert evaluate("1 ly")["result"] > 9.4e15


# ---------------------------------------------------------------------
# Physics
# ---------------------------------------------------------------------
def test_schwarzschild_sun():
    r = evaluate("2 * G * M_sun / c^2")["result"]
    assert 2900 < r < 3000


# ---------------------------------------------------------------------
# Solver
# ---------------------------------------------------------------------
def test_solve_basic():
    assert solve_linear("2x + 5 = 15", "x")["solution"] == 5.0


def test_solve_both_sides():
    assert solve_linear("3x - 7 = 2x + 3", "x")["solution"] == 10.0


def test_solve_fraction():
    assert solve_linear("x/2 + 3 = 7", "x")["solution"] == 8.0


def test_solve_identity():
    assert solve_linear("2x = 2x", "x")["solution"] is None


def test_solve_contradiction():
    assert solve_linear("2x = 2x + 5", "x")["solution"] is None


def test_solve_non_linear_rejected():
    with pytest.raises(CalcError):
        solve_linear("x^2 = 4", "x")


def test_solve_missing_equals():
    with pytest.raises(CalcError):
        solve_linear("2x + 5", "x")


# ---------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------
def test_empty():
    with pytest.raises(CalcError):
        evaluate("")


def test_syntax_error():
    with pytest.raises(CalcError):
        evaluate("2 +")


def test_div_by_zero():
    with pytest.raises(CalcError):
        evaluate("1 / 0")


def test_unknown_function():
    with pytest.raises(CalcError):
        evaluate("evil()")


def test_no_import_access():
    with pytest.raises(CalcError):
        evaluate("__import__('os')")


# ---------------------------------------------------------------------
# Formulas
# ---------------------------------------------------------------------
def test_kinetic_energy():
    r = FORMULAS["kinetic_energy"](2.0, 3.0)
    assert abs(r["result"] - 9.0) < 1e-9


def test_escape_velocity_earth():
    r = FORMULAS["escape_velocity"](CONSTANTS["M_earth"], CONSTANTS["R_earth"])
    assert 11000 < r["result"] < 11500
