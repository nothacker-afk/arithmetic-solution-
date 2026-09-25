"""Input validation for auth and API payloads."""
import re

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")


class ValidationError(ValueError):
    pass


def validate_username(s: str) -> str:
    if not isinstance(s, str):
        raise ValidationError("Username must be a string")
    s = s.strip()
    if not USERNAME_RE.match(s):
        raise ValidationError(
            "Username must be 3-32 characters: letters, numbers, underscores"
        )
    return s


def validate_email(s: str) -> str:
    if not isinstance(s, str):
        raise ValidationError("Email must be a string")
    s = s.strip().lower()
    if not EMAIL_RE.match(s):
        raise ValidationError("Invalid email format")
    return s


def validate_password(s: str, min_length: int = 8) -> str:
    if not isinstance(s, str):
        raise ValidationError("Password must be a string")
    if len(s) < min_length:
        raise ValidationError(f"Password must be at least {min_length} characters")
    if not any(c.isdigit() for c in s):
        raise ValidationError("Password must contain at least one digit")
    if not any(c.isalpha() for c in s):
        raise ValidationError("Password must contain at least one letter")
    return s


def validate_number(value, name: str = "value") -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{name} must be a number")


def validate_matrix(value, name: str = "matrix") -> list:
    if not isinstance(value, list) or not value:
        raise ValidationError(f"{name} must be a non-empty list of lists")
    width = len(value[0])
    if width == 0:
        raise ValidationError(f"{name} rows cannot be empty")
    for row in value:
        if not isinstance(row, list) or len(row) != width:
            raise ValidationError(f"{name} must be rectangular")
        for x in row:
            try:
                float(x)
            except (TypeError, ValueError):
                raise ValidationError(f"{name} contains a non-numeric value")
    return value
