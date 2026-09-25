"""Tests for the validation module."""
import pytest
from web.backend.validation import (
    validate_username, validate_email, validate_password,
    validate_number, validate_matrix, ValidationError,
)


def test_username_ok():
    assert validate_username("alice_99") == "alice_99"


def test_username_too_short():
    with pytest.raises(ValidationError):
        validate_username("ab")


def test_username_bad_chars():
    with pytest.raises(ValidationError):
        validate_username("bad-char!")


def test_email_ok():
    assert validate_email("Alice@Example.COM") == "alice@example.com"


def test_email_bad():
    with pytest.raises(ValidationError):
        validate_email("not-an-email")


def test_password_ok():
    assert validate_password("secret123")


def test_password_too_short():
    with pytest.raises(ValidationError):
        validate_password("abc1")


def test_password_no_digit():
    with pytest.raises(ValidationError):
        validate_password("abcdefgh")


def test_password_no_letter():
    with pytest.raises(ValidationError):
        validate_password("12345678")


def test_number_ok():
    assert validate_number("3.14") == 3.14


def test_number_bad():
    with pytest.raises(ValidationError):
        validate_number("not-a-number")


def test_matrix_ok():
    assert validate_matrix([[1, 2], [3, 4]]) == [[1, 2], [3, 4]]


def test_matrix_not_rectangular():
    with pytest.raises(ValidationError):
        validate_matrix([[1, 2], [3]])


def test_matrix_non_numeric():
    with pytest.raises(ValidationError):
        validate_matrix([[1, "x"]])
