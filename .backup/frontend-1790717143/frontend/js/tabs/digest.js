// Email digest subscription (Phase 75)
const Digest = (() => {
    async function load() {
        const el = document.getElementById("digest-status");
        if (!el) return;
        if (!API.isLoggedIn()) {
            el.innerHTML = `<div class="empty">Login to manage digests.</div>`;
            return;
        }
        try {
            const data = await API.get("/api/digest/subscription");
            el.innerHTML = `
                <div class="field">
                    <label>Frequency</label>
                    <select id="digest-freq" class="select">
                        <option value="daily" ${data.frequency === "daily" ? "selected" : ""}>Daily</option>
                        <option value="weekly" ${data.frequency === "weekly" ? "selected" : ""}>Weekly</option>
                    </select>
                </div>
                <div class="field">
                    <label><input id="digest-enabled" type="checkbox"
                        style="width:auto;margin-right:6px;"
                        ${data.enabled ? "checked" : ""} /> Send me digests</label>
                </div>
                <p class="muted" style="font-size:var(--fs-xs);">
                    Last sent: ${data.last_sent_at || "never"}
                </p>
                <button id="digest-save" class="btn btn-primary">Save</button>
                <button id="digest-test" class="btn">Send test</button>
            `;
            document.getElementById("digest-save").addEventListener("click", save);
            document.getElementById("digest-test").addEventListener("click", test);
        } catch (e) {
            el.innerHTML = `<div class="empty">Error: ${e.message}</div>`;
        }
    }

    async function save() {
        try {
            await API.put("/api/digest/subscription", {
                frequency: document.getElementById("digest-freq").value,
                enabled: document.getElementById("digest-enabled").checked,
            });
            UI.toast("Saved", "success");
        } catch (e) { UI.toast("Save failed: " + e.message, "error"); }
    }

    async function test() {
        try {
            const r = await API.post("/api/digest/test", {});
            UI.toast(r.sent ? "Sent!" : "Failed: " + r.message,
                     r.sent ? "success" : "error");
        } catch (e) { UI.toast("Test failed: " + e.message, "error"); }
    }

    function init() {}
    function onShow() { load(); }

    return { init, onShow, load, save, test };
})();
