// Command palette (Ctrl+K / Cmd+K)
const Commands = (() => {
    let _root = null;

    function _commands() {
        return [
            { id: "tab-basic", label: "Go to Basic", kbd: "1", action: () => Tab.go("basic") },
            { id: "tab-sci", label: "Go to Scientific", kbd: "2", action: () => Tab.go("scientific") },
            { id: "tab-matrix", label: "Go to Matrix", kbd: "3", action: () => Tab.go("matrix") },
            { id: "tab-ai", label: "Go to AI", kbd: "4", action: () => Tab.go("ai") },
            { id: "tab-live", label: "Go to Live", kbd: "5", action: () => Tab.go("realtime") },
            { id: "tab-history", label: "Go to History", kbd: "6", action: () => Tab.go("history") },
            { id: "theme", label: "Toggle theme", kbd: "T", action: () => Theme.cycle() },
            { id: "lang", label: "Cycle language", kbd: "L", action: () => I18n.cycle().then(() => location.reload()) },
            { id: "login", label: "Login / Register", kbd: "", action: () => document.getElementById("auth-btn")?.click() },
            { id: "logout", label: "Logout", kbd: "", action: () => {
                if (API.isLoggedIn()) { API.setAuth(null); UI.toast("Logged out"); location.reload(); }
            }},
            { id: "admin", label: "Open admin dashboard", kbd: "", action: () => location.href = "/admin" },
            { id: "install", label: "Install app (PWA)", kbd: "", action: () => document.getElementById("install-btn")?.click() },
        ];
    }

    function open() {
        if (_root) return;
        const cmds = _commands();
        _root = document.createElement("div");
        _root.className = "cmdk-backdrop";
        _root.innerHTML = `
            <div class="cmdk" role="dialog" aria-label="Command palette">
                <input class="cmdk-input" placeholder="Type a command…" autofocus />
                <div class="cmdk-list"></div>
            </div>`;
        document.body.appendChild(_root);

        const input = _root.querySelector(".cmdk-input");
        const list = _root.querySelector(".cmdk-list");
        let selected = 0;

        function render(filter = "") {
            const f = filter.toLowerCase();
            const filtered = cmds.filter(c => c.label.toLowerCase().includes(f));
            selected = Math.min(selected, Math.max(0, filtered.length - 1));
            list.innerHTML = filtered.map((c, i) =>
                `<div class="cmdk-item ${i === selected ? "selected" : ""}" data-idx="${i}">
                    <span>${c.label}</span>
                    ${c.kbd ? `<span class="cmdk-kbd">${c.kbd}</span>` : ""}
                </div>`
            ).join("") || `<div class="empty">No commands</div>`;
            list.querySelectorAll(".cmdk-item").forEach(el => {
                el.addEventListener("click", () => {
                    const idx = +el.dataset.idx;
                    run(filtered[idx]);
                });
            });
            return filtered;
        }

        let _filtered = render("");
        input.addEventListener("input", () => { _filtered = render(input.value); });
        input.addEventListener("keydown", (e) => {
            if (e.key === "Escape") return close();
            if (e.key === "ArrowDown") { e.preventDefault(); selected = Math.min(selected + 1, _filtered.length - 1); _filtered = render(input.value); }
            if (e.key === "ArrowUp") { e.preventDefault(); selected = Math.max(selected - 1, 0); _filtered = render(input.value); }
            if (e.key === "Enter") { e.preventDefault(); run(_filtered[selected]); }
        });

        function run(cmd) {
            if (!cmd) return;
            close();
            setTimeout(() => cmd.action(), 50);
        }

        function close() {
            if (_root) { _root.remove(); _root = null; }
        }
    }

    function init() {
        document.addEventListener("keydown", (e) => {
            const mod = e.metaKey || e.ctrlKey;
            if (mod && e.key === "k") {
                e.preventDefault();
                open();
                return;
            }
            // Single-letter shortcuts (only when not typing)
            const tag = (e.target.tagName || "").toLowerCase();
            if (tag === "input" || tag === "textarea" || tag === "select") return;
            if (e.altKey || e.ctrlKey || e.metaKey) return;
            const map = { "1": "basic", "2": "scientific", "3": "matrix", "4": "ai", "5": "realtime", "6": "history" };
            if (map[e.key]) { e.preventDefault(); Tab.go(map[e.key]); }
            if (e.key === "t" || e.key === "T") { e.preventDefault(); Theme.cycle(); }
        });
    }

    return { open, init };
})();
