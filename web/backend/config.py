"""Backend configuration.

Secrets default to auto-generated values of >= 32 bytes (RFC 7518).
Set JWT_SECRET / SECRET_KEY env vars in production for stable sessions.
"""
import os
import secrets
import sys
from pathlib import Path


def _dev_secret(name: str, min_bytes: int = 32) -> str:
    val = os.environ.get(name)
    if val:
        if len(val.encode("utf-8")) < min_bytes:
            sys.stderr.write(
                f"[config] WARNING: {name} is shorter than {min_bytes} bytes\n"
            )
        return val
    # token_hex(n) returns 2*n hex chars, each 1 byte -> n bytes minimum
    return secrets.token_hex(min_bytes)


class Config:
    SECRET_KEY = _dev_secret("SECRET_KEY")
    JWT_SECRET = _dev_secret("JWT_SECRET")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS", "24"))
    MIN_PASSWORD_LENGTH = int(os.environ.get("MIN_PASSWORD_LENGTH", "8"))

    FILE_STORAGE_DIR = os.environ.get(
        "FILE_STORAGE_DIR", str(Path.home() / ".arithmetic_files"),
    )
    MAX_FILE_SIZE_MB = int(os.environ.get("MAX_FILE_SIZE_MB", "5"))
    MAX_FILES_PER_ROOM = int(os.environ.get("MAX_FILES_PER_ROOM", "100"))
    MAX_TOTAL_BYTES_PER_ROOM = int(
        os.environ.get("MAX_TOTAL_BYTES_PER_ROOM", str(50 * 1024 * 1024))
    )

    INVITE_TTL_HOURS = int(os.environ.get("INVITE_TTL_HOURS", "24"))
    MAX_INVITE_TTL_HOURS = int(os.environ.get("MAX_INVITE_TTL_HOURS", "720"))
