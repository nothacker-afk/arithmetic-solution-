"""Tests for i18n (Phases 12 + 64)."""
import pytest
from web.backend.i18n import (
    DEFAULT_LOCALE, TRANSLATIONS, supported_locales, pick_locale, get_strings,
)


# ---------------------------------------------------------------------
# Registry invariants
# ---------------------------------------------------------------------
def test_supported_locales():
    locales = supported_locales()
    for expected in ("en", "sw", "fr", "es", "ru", "zh", "hi"):
        assert expected in locales


def test_every_locale_has_same_keys():
    """All locales must expose the same key set (no partial translations)."""
    en_keys = set(TRANSLATIONS["en"].keys())
    for locale, strings in TRANSLATIONS.items():
        assert set(strings.keys()) == en_keys, (
            f"{locale} has different keys: "
            f"missing={en_keys - set(strings.keys())}, "
            f"extra={set(strings.keys()) - en_keys}"
        )


def test_get_strings_falls_back_to_english():
    """Missing keys fall back to English strings."""
    strings = get_strings("sw")
    # Every English key should be present
    for k in TRANSLATIONS["en"]:
        assert k in strings


# ---------------------------------------------------------------------
# Locale detection
# ---------------------------------------------------------------------
def test_pick_locale_exact():
    assert pick_locale("fr") == "fr"
    assert pick_locale("sw") == "sw"
    assert pick_locale("ru") == "ru"
    assert pick_locale("zh") == "zh"
    assert pick_locale("hi") == "hi"


def test_pick_locale_with_region():
    assert pick_locale("fr-CA") == "fr"
    assert pick_locale("es-MX,en-US;q=0.9") == "es"
    assert pick_locale("zh-TW") == "zh"
    assert pick_locale("ru-RU") == "ru"


def test_pick_locale_fallback():
    # A language we don't support at all → English
    assert pick_locale("ko-KR") == DEFAULT_LOCALE
    assert pick_locale("xx") == DEFAULT_LOCALE
    assert pick_locale("") == DEFAULT_LOCALE
    assert pick_locale(None) == DEFAULT_LOCALE


def test_pick_locale_quality_order():
    assert pick_locale("en;q=1,fr;q=0.5") == "en"
    assert pick_locale("fr;q=1") == "fr"


# ---------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------
def test_locales_endpoint(client):
    r = client.get("/api/i18n/locales")
    assert r.status_code == 200
    body = r.get_json()
    assert body["default"] == "en"
    for loc in ("en", "sw", "fr", "es", "ru", "zh", "hi"):
        assert loc in body["locales"]


def test_get_locale(client):
    r = client.get("/api/i18n/fr")
    assert r.status_code == 200
    body = r.get_json()
    assert body["locale"] == "fr"
    assert body["strings"]["app.title"].startswith("Super")


def test_get_unknown_locale(client):
    r = client.get("/api/i18n/xx")
    assert r.status_code == 404


def test_detect_endpoint(client):
    r = client.get("/api/i18n/detect", headers={"Accept-Language": "sw-KE,sw;q=0.9"})
    assert r.status_code == 200
    assert r.get_json()["locale"] == "sw"


def test_detect_endpoint_ru(client):
    r = client.get("/api/i18n/detect", headers={"Accept-Language": "ru-RU,ru;q=0.9"})
    assert r.get_json()["locale"] == "ru"


def test_detect_endpoint_fallback(client):
    # Only unsupported languages → fall back to English
    r = client.get("/api/i18n/detect", headers={"Accept-Language": "ko-KR,ja-JP"})
    assert r.get_json()["locale"] == "en"
