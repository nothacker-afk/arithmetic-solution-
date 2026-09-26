"""Tests for Phase 64 i18n expansion."""
from web.backend.i18n import TRANSLATIONS, supported_locales, pick_locale


def test_all_expected_locales():
    for loc in ("en", "sw", "fr", "es", "ru", "zh", "hi"):
        assert loc in supported_locales(), f"missing locale: {loc}"


def test_locale_keys_match_english():
    en_keys = set(TRANSLATIONS["en"].keys())
    for loc, strings in TRANSLATIONS.items():
        assert set(strings.keys()) == en_keys, f"{loc} has different keys"


def test_pick_locale_ru():
    assert pick_locale("ru-RU,ru;q=0.9") == "ru"


def test_pick_locale_zh():
    assert pick_locale("zh-CN,zh;q=0.9") == "zh"


def test_pick_locale_hi():
    assert pick_locale("hi-IN") == "hi"


def test_locale_endpoint_serves_ru(client):
    r = client.get("/api/i18n/ru")
    assert r.status_code == 200
    assert r.get_json()["locale"] == "ru"


def test_locale_endpoint_serves_zh(client):
    r = client.get("/api/i18n/zh")
    assert r.status_code == 200


def test_locale_endpoint_serves_hi(client):
    r = client.get("/api/i18n/hi")
    assert r.status_code == 200
