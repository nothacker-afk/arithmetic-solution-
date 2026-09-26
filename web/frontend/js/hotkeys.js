// Configurable keyboard shortcuts (Phase 58)
const Hotkeys = (() => {
    const STORAGE_KEY = "hotkeys.config";

    // Default bindings: key -> {action, label}
    const DEFAULTS = {
        "1": { label: "Basic tab", fn: () => window.Tab?.go("basic") },
        "2": { label: "Scientific tab", fn: () => window.Tab?.go("scientific") },
        "3": { label: "Matrix tab", fn: () => window.Tab?.go("matrix") },
        "4": { label: "AI tab", fn: () => window.Tab?.go("ai") },
        "5": { label: "Live tab", fn: () => window.Tab?.go("realtime") },
        "6": { label: "History tab", fn: () => window.Tab?.go("history") },
        "7": { label: "Search tab", fn: () => window.Tab?.go("search") },
        "8": { label: "DMs tab", fn: () => window.Tab?.go("dms") },
        "9": { label: "Groups tab", fn: () => window.Tab?.go("groups") },
        "t": { label: "Toggle theme", fn: () => window.Theme?.cycle() },
        "l": { label: "Cycle language", fn: () => window.I18n?.cycle().then(() => location.reload()) },
        "?": { label: "Show this help", fn: () => show() },
        "/": { label: "Focus search", fn: () => {
            window.Tab?.go("search");
            setTimeout(() => document.getElementById("search-input")?.focus(), 80);
        }},
    };

    function loadCustom() {
        try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}"); }
        catch { return {}; }
    }

    function saveCustom(cfg) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(cfg));
    }

    function effective() {
        // Start from defaults, drop any user-disabled shortcuts
        const custom = loadCustom();
        const out = {};
        for (const [k, v] of Object.entries(DEFAULTS)) {
            if (custom[k] === false) continue;
            out[k] = v;
        }
        return out;
    }

    function _isTyping(e) {
        const t = e.target;
        if (!t) return false;
        const tag = (t.tagName || "").toLowerCase();
        return tag === "input" || tag === "textarea" || tag === "select" || t.isContentEditable;
    }

    function init() {
        document.addEventListener("keydown", (e) => {
            // Ctrl/Cmd+K handled elsewhere (command palette)
            if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") return;

            if (e.altKey || e.ctrlKey || e.metaKey) return;
            if (_isTyping(e)) return;

            const bindings = effective();
            const key = e.key === "?" ? "?" : e.key.toLowerCase();
            const binding = bindings[key];
            if (binding && binding.fn) {
                e.preventDefault();
                binding.fn();
            }
        });
    }

    function show() {
        const bindings = effective();
        const body = document.createElement("div");
        const custom = loadCustom();

        body.innerHTML = `
            <table style="width:100%;font-size:var(--fs-sm);">
                <thead><tr><th style="text-align:left;color:var(--fg-3);font-size:var(--fs-xs);">
                    Key</th><th style="text-align:left;color:var(--fg-3);font-size:var(--fs-xs);">
                    Action</th><th></th></tr></thead>
                <tbody>
                    ${Object.entries(bindings).map(([k, b]) => `
                        <tr>
                            <td><span class="cmdk-kbd">${k}</span></td>
                            <td>${b.label}</td>
                            <td style="text-align:right;">
                                <button class="btn btn-ghost btn-icon" data-disable="${k}"
                                        title="Disable this shortcut">✕</button>
                            </td>
                        </tr>`).join("")}
                </tbody>
            </table>
            <hr style="border:none;border-top:1px solid var(--border);margin:var(--sp-4) 0;" />
            <h4>Disabled shortcuts</h4>
            <div id="hotkeys-disabled">
                ${Object.keys(DEFAULTS).filter(k => custom[k] === false).map(k =>
                    `<span class="badge" style="margin-right:4px;">
                        ${k}
                        <button class="btn btn-ghost btn-icon" style="padding:0 4px;min-width:auto;"
                                data-enable="${k}">↺</button>
                    </span>`).join("") || `<span class="muted">None</span>`}
            </div>
            <p class="muted mt-4" style="font-size:var(--fs-xs);">
                Ctrl+K opens the command palette · Ctrl+? opens this panel
            </p>`;

        UI.modal({
            title: "Keyboard shortcuts",
            body,
            actions: [{ label: "Close", kind: "primary" }],
        });

        // Wire disable buttons
        document.querySelectorAll("[data-disable]").forEach(btn => {
            btn.addEventListener("click", () => {
                const cfg = loadCustom();
                cfg[btn.dataset.disable] = false;
                saveCustom(cfg);
                UI.toast("Shortcut disabled");
                // Re-open to refresh the list
                document.querySelector(".modal-backdrop")?.remove();
                show();
            });
        });

        // Wire enable buttons
        document.querySelectorAll("[data-enable]").forEach(btn => {
            btn.addEventListener("click", () => {
                const cfg = loadCustom();
                delete cfg[btn.dataset.enable];
                saveCustom(cfg);
                UI.toast("Shortcut restored");
                document.querySelector(".modal-backdrop")?.remove();
                show();
            });
        });
    }

    return { init, show, effective, DEFAULTS };
})();
