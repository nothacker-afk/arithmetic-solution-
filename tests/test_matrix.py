"""Tests for matrix operations."""
import pytest
from arithmetic.matrix import matrix_add, matrix_subtract, matrix_multiply, matrix_transpose


A = [[1, 2], [3, 4]]
B = [[5, 6], [7, 8]]


def test_matrix_add():
    assert matrix_add(A, B) == [[6, 8], [10, 12]]


def test_matrix_subtract():
    assert matrix_subtract(B, A) == [[4, 4], [4, 4]]


def test_matrix_multiply():
    assert matrix_multiply(A, B) == [[19, 22], [43, 50]]


def test_matrix_transpose():
    assert matrix_transpose(A) == [[1, 3], [2, 4]]


def test_matrix_dimension_mismatch():
    with pytest.raises(ValueError):
        matrix_add(A, [[1, 2, 3]])
