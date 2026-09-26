// Client-side i18n helper — wraps the existing i18n.js globals
const I18n = (() => {
    let _locale = "en";

    async function load(locale) {
        try {
            const data = await API.get("/api/i18n/" + encodeURIComponent(locale));
            _locale = data.locale;
            window.i18n && window.i18n.load && await window.i18n.load(locale);
        } catch (e) {
            console.warn("i18n load failed:", e);
        }
        return _locale;
    }

    function t(key, fallback) {
        if (window.i18n && window.i18n.t) return window.i18n.t(key, fallback);
        return fallback || key;
    }

    function current() { return _locale; }

    function cycle() {
        const list = ["en", "sw", "fr", "es"];
        const next = list[(list.indexOf(_locale) + 1) % list.length];
        return load(next);
    }

    return { load, t, current, cycle };
})();
