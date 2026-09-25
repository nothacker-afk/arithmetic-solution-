"""Configuration for the Flask backend."""
import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    JWT_SECRET = os.environ.get("JWT_SECRET", "dev-jwt-secret-change-me")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRY_HOURS = int(os.environ.get("JWT_EXPIRY_HOURS", "24"))
    MIN_PASSWORD_LENGTH = 8
