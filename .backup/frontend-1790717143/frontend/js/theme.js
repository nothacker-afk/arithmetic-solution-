// Theme switcher with OS sync
const Theme = (() => {
    const KEY = "theme";
    const MODES = ["auto", "light", "dark"];
    const ICONS = { auto: "🌓", light: "☀️", dark: "🌙" };

    function apply(mode) {
        document.documentElement.classList.remove("theme-light", "theme-dark");
        if (mode === "auto") {
            const dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
            document.documentElement.classList.add(dark ? "theme-dark" : "theme-light");
        } else {
            document.documentElement.classList.add("theme-" + mode);
        }
        localStorage.setItem(KEY, mode);
        const btn = document.getElementById("theme-btn");
        if (btn) {
            btn.textContent = ICONS[mode];
            btn.setAttribute("aria-label", "Theme: " + mode);
        }
    }

    function cycle() {
        const cur = localStorage.getItem(KEY) || "auto";
        const next = MODES[(MODES.indexOf(cur) + 1) % MODES.length];
        apply(next);
        return next;
    }

    function current() { return localStorage.getItem(KEY) || "auto"; }

    function init() {
        apply(current());
        if (window.matchMedia) {
            window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
                if (current() === "auto") apply("auto");
            });
        }
        document.addEventListener("click", (e) => {
            if (e.target.id === "theme-btn" || e.target.closest("#theme-btn")) {
                const mode = cycle();
                if (API.isLoggedIn()) {
                    API.put("/api/prefs", { theme: mode, language: I18n.current() }).catch(() => {});
                }
            }
        });
    }

    return { apply, cycle, current, init };
})();
