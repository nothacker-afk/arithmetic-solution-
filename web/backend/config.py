"""Configuration for the Flask backend."""
import os
from pathlib import Path


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    JWT_SECRET = os.environ.get("JWT_SECRET", "dev-jwt-secret-change-me")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS", "24"))
    MIN_PASSWORD_LENGTH = 8

    # Phase 10: file sharing
    FILE_STORAGE_DIR = os.environ.get(
        "FILE_STORAGE_DIR",
        str(Path.home() / ".arithmetic_files"),
    )
    MAX_FILE_SIZE_MB = int(os.environ.get("MAX_FILE_SIZE_MB", "5"))
    MAX_FILES_PER_ROOM = int(os.environ.get("MAX_FILES_PER_ROOM", "100"))
    MAX_TOTAL_BYTES_PER_ROOM = int(
        os.environ.get("MAX_TOTAL_BYTES_PER_ROOM", str(50 * 1024 * 1024))
    )
