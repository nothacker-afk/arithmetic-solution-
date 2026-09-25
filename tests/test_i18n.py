"""Tests for i18n (Phase 12)."""
import pytest
from web.backend.i18n import (
    DEFAULT_LOCALE, TRANSLATIONS, supported_locales, pick_locale,
)


# ---------------------------------------------------------------------
# Unit-level
# ---------------------------------------------------------------------
def test_supported_locales():
    locales = supported_locales()
    for expected in ("en", "sw", "fr", "es"):
        assert expected in locales


def test_every_locale_has_same_keys():
    """All locales should expose the same keys (no partial translations)."""
    en_keys = set(TRANSLATIONS["en"].keys())
    for locale, strings in TRANSLATIONS.items():
        assert set(strings.keys()) == en_keys, f"{locale} has a different key set"


def test_pick_locale_exact():
    assert pick_locale("fr") == "fr"
    assert pick_locale("sw") == "sw"


def test_pick_locale_with_region():
    assert pick_locale("fr-CA") == "fr"
    assert pick_locale("es-MX,en-US;q=0.9") == "es"


def test_pick_locale_fallback():
    assert pick_locale("zh-TW") == DEFAULT_LOCALE
    assert pick_locale("") == DEFAULT_LOCALE
    assert pick_locale(None) == DEFAULT_LOCALE


def test_pick_locale_quality_order():
    # "en" is q=1, "fr" is q=0.5 — but fr isn't first, so en wins
    assert pick_locale("en;q=1,fr;q=0.5") == "en"
    # If only fr is listed (or en missing), fr wins
    assert pick_locale("fr;q=1") == "fr"


# ---------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------
def test_locales_endpoint(client):
    r = client.get("/api/i18n/locales")
    assert r.status_code == 200
    body = r.get_json()
    assert body["default"] == "en"
    for loc in ("en", "sw", "fr", "es"):
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


def test_detect_endpoint_fallback(client):
    r = client.get("/api/i18n/detect", headers={"Accept-Language": "zh,ja"})
    assert r.get_json()["locale"] == "en"
