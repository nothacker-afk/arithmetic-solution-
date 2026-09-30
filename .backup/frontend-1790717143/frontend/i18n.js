/* Runtime i18n for Arithmetic Super App.
 *
 * Usage:
 *   await i18n.load("sw");
 *   i18n.t("app.title")         // -> "Programu Kuu ya Hesabu"
 *   i18n.apply()                // updates every [data-i18n] element
 *
 * Detects the initial language from:
 *   1. localStorage("language")
 *   2. <html lang="...">
 *   3. navigator.language
 *   4. Backend /api/i18n/detect (Accept-Language)
 */
const i18n = (() => {
    let _locale = "en";
    let _strings = {};

    function detectFromNavigator() {
        const raw = navigator.language || "en";
        return raw.toLowerCase().split("-")[0];
    }

    async function load(locale) {
        // Try the requested locale; fall back to English on 404
        let res = await fetch("/api/i18n/" + encodeURIComponent(locale));
        if (!res.ok) {
            locale = "en";
            res = await fetch("/api/i18n/en");
        }
        const data = await res.json();
        _locale = data.locale;
        _strings = data.strings;
        document.documentElement.lang = _locale;
        localStorage.setItem("language", _locale);
        apply();
        return _locale;
    }

    function t(key, fallback) {
        if (Object.prototype.hasOwnProperty.call(_strings, key)) {
            return _strings[key];
        }
        return fallback !== undefined ? fallback : key;
    }

    function apply() {
        document.querySelectorAll("[data-i18n]").forEach((el) => {
            const key = el.getAttribute("data-i18n");
            const val = t(key, null);
            if (val !== null) el.textContent = val;
        });
        document.querySelectorAll("[data-i18n-title]").forEach((el) => {
            const key = el.getAttribute("data-i18n-title");
            const val = t(key, null);
            if (val !== null) el.setAttribute("title", val);
        });
        document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
            const key = el.getAttribute("data-i18n-placeholder");
            const val = t(key, null);
            if (val !== null) el.setAttribute("placeholder", val);
        });
    }

    function currentLocale() { return _locale; }
    function available() { return ["en", "sw", "fr", "es"]; }

    return { load, t, apply, currentLocale, available, detectFromNavigator };
})();
