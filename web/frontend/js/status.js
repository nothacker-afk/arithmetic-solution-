// User status picker (Phase 55)
const Status = (() => {
    const STATES = [
        { id: "available", label: "Available", emoji: "🟢" },
        { id: "away",      label: "Away",      emoji: "🟡" },
        { id: "busy",      label: "Busy",      emoji: "🔴" },
        { id: "dnd",       label: "Do not disturb", emoji: "⛔" },
        { id: "invisible", label: "Invisible", emoji: "⚪" },
    ];
    const QUICK_EMOJI = ["💻", "📚", "🎧", "🍕", "☕", "🌙", "🎮", "💤", "🏃", "✈️"];

    let current = { state: "available", emoji: null, message: null };

    async function load() {
        if (!API.isLoggedIn()) return;
        try {
            current = await API.get("/api/status/me");
            renderBadge();
        } catch (e) { /* ignore */ }
    }

    function renderBadge() {
        const el = document.getElementById("status-badge");
        if (!el) return;
        const st = STATES.find(s => s.id === current.state) || STATES[0];
        el.textContent = current.emoji || st.emoji;
        el.title = st.label + (current.message ? " — " + current.message : "");
    }

    function pick() {
        const body = document.createElement("div");
        body.innerHTML = `
            <div class="field"><label>State</label>
                <select id="st-state" class="select">
                    ${STATES.map(s => `<option value="${s.id}" ${current.state === s.id ? "selected" : ""}>${s.emoji} ${s.label}</option>`).join("")}
                </select>
            </div>
            <div class="field"><label>Custom emoji (optional)</label>
                <input id="st-emoji" class="input" maxlength="8" value="${current.emoji || ""}" />
                <div class="chip-row" style="margin-top:6px;">
                    ${QUICK_EMOJI.map(e => `<div class="chip" onclick="document.getElementById('st-emoji').value='${e}'">${e}</div>`).join("")}
                </div>
            </div>
            <div class="field"><label>Status message (optional)</label>
                <input id="st-msg" class="input" maxlength="80" value="${current.message || ""}" placeholder="In a meeting…" />
            </div>`;
        UI.modal({
            title: "Set status",
            body,
            actions: [
                { label: "Save", kind: "primary", close: false, onClick: async (bd) => {
                    const state = bd.querySelector("#st-state").value;
                    const emoji = bd.querySelector("#st-emoji").value.trim() || null;
                    const message = bd.querySelector("#st-msg").value.trim() || null;
                    try {
                        current = await API.put("/api/status/me", { state, emoji, message });
                        renderBadge();
                        UI.toast("Status updated", "success");
                        bd.remove();
                    } catch (e) { UI.toast("Failed: " + e.message, "error"); }
                }},
                { label: "Cancel" },
            ],
        });
    }

    function init() {
        document.getElementById("status-badge")?.addEventListener("click", pick);
        if (API.isLoggedIn()) load();
    }

    return { init, load, pick };
})();
