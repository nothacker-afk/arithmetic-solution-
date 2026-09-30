// Room retention overrides (Phase 84)
const RoomRetention = (() => {
    async function load() {
        const el = document.getElementById("retention-status");
        const room = document.getElementById("room-tab-room")?.value.trim();
        if (!el || !room) return;
        if (!API.isLoggedIn()) {
            el.innerHTML = `<div class="empty">Login to manage retention.</div>`;
            return;
        }
        try {
            const data = await API.get(`/api/rooms/${room}/retention`);
            el.innerHTML = `
                <div class="field"><label>Chat messages TTL (days, blank = global)</label>
                    <input id="rr-chat" class="input" type="number" min="0" max="3650"
                           value="${data.chat_days ?? ""}" /></div>
                <div class="field"><label>Audit entries TTL (days, blank = global)</label>
                    <input id="rr-audit" class="input" type="number" min="0" max="3650"
                           value="${data.audit_days ?? ""}" /></div>
                <button id="rr-save" class="btn btn-primary">Save</button>
                <button id="rr-reset" class="btn btn-danger">Reset to global</button>
                <p class="muted" style="font-size:var(--fs-xs);margin-top:8px;">
                    ${data.is_custom ? "Custom retention active for this room." :
                      "Using global defaults."}
                </p>`;
            document.getElementById("rr-save").addEventListener("click", () => save(room));
            document.getElementById("rr-reset").addEventListener("click", () => reset(room));
        } catch (e) {
            el.innerHTML = `<div class="empty">Error: ${e.message}</div>`;
        }
    }

    function _num(id) {
        const v = document.getElementById(id).value.trim();
        return v === "" ? null : parseInt(v);
    }

    async function save(room) {
        try {
            await API.put(`/api/rooms/${room}/retention`, {
                chat_days: _num("rr-chat"),
                audit_days: _num("rr-audit"),
            });
            UI.toast("Retention saved", "success");
            load();
        } catch (e) { UI.toast("Save failed: " + e.message, "error"); }
    }

    async function reset(room) {
        if (!confirm("Reset to global retention defaults?")) return;
        try {
            await API.del(`/api/rooms/${room}/retention`);
            UI.toast("Reset");
            load();
        } catch (e) { UI.toast("Reset failed: " + e.message, "error"); }
    }

    function init() {}
    function onShow() { load(); }
    return { init, onShow, load, save, reset };
})();
