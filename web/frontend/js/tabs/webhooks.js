// Outbound webhooks management (Phase 87)
const Webhooks = (() => {
    const ALL_EVENTS = [
        "message.created", "dm.created", "user.registered",
        "room.published", "webhook.test",
    ];

    async function load() {
        const list = document.getElementById("webhooks-list");
        if (!list) return;
        if (!API.isLoggedIn()) {
            list.innerHTML = `<div class="empty">Login to manage webhooks.</div>`;
            return;
        }
        try {
            const data = await API.get("/api/webhooks");
            if (!data.webhooks.length) {
                list.innerHTML = `<div class="empty">No webhooks yet.</div>`;
                return;
            }
            list.innerHTML = data.webhooks.map(w => `
                <div class="contact-row">
                    <div>
                        <div class="mono" style="font-size:var(--fs-sm);word-break:break-all;">
                            ${escapeHtml(w.url)}</div>
                        <div class="muted" style="font-size:var(--fs-xs);">
                            ${w.events}
                            ${w.last_status_code ? ` · last: ${w.last_status_code}` : ""}
                            ${w.failure_count ? ` · fails: ${w.failure_count}` : ""}
                        </div>
                    </div>
                    <div style="display:flex;gap:4px;">
                        <button class="btn btn-ghost btn-icon"
                                onclick="Webhooks.test('${w.id}')">▶</button>
                        <button class="btn btn-ghost btn-icon"
                                onclick="Webhooks.deliveries('${w.id}')">📜</button>
                        <button class="btn btn-ghost btn-icon"
                                onclick="Webhooks.remove('${w.id}')">×</button>
                    </div>
                </div>
            `).join("");
        } catch (e) {
            list.innerHTML = `<div class="empty">Error: ${escapeHtml(e.message)}</div>`;
        }
    }

    function create() {
        const body = document.createElement("div");
        body.innerHTML = `
            <div class="field"><label>URL (https://…)</label>
                <input id="wh-url" class="input" placeholder="https://example.com/hook" /></div>
            <div class="field"><label>Description (optional)</label>
                <input id="wh-desc" class="input" /></div>
            <div class="field"><label>Events</label>
                ${ALL_EVENTS.map(e => `
                    <label style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">
                        <input type="checkbox" data-ev="${e}" />
                        <code>${e}</code>
                    </label>`).join("")}
            </div>`;
        UI.modal({
            title: "New webhook",
            body,
            actions: [
                { label: "Create", kind: "primary", close: false, onClick: async (bd) => {
                    const url = bd.querySelector("#wh-url").value.trim();
                    const desc = bd.querySelector("#wh-desc").value.trim();
                    const events = [...bd.querySelectorAll("input[data-ev]")]
                        .filter(i => i.checked).map(i => i.dataset.ev);
                    if (!url || !events.length) return;
                    try {
                        const data = await API.post("/api/webhooks",
                            { url, events, description: desc });
                        UI.modal({
                            title: "Webhook created — save the secret",
                            body: `<p>Signing secret (shown once):</p>
                                <input class="input mono" value="${data.secret}" readonly />`,
                            actions: [{ label: "Done", kind: "primary" }],
                        });
                        load();
                    } catch (e) { UI.toast("Create failed: " + e.message, "error"); }
                }},
                { label: "Cancel" },
            ],
        });
    }

    async function test(id) {
        try {
            const r = await API.post(`/api/webhooks/${id}/test`, {});
            UI.toast(r.sent ? `OK (${r.status_code})` : `Failed: ${r.error}`, r.sent ? "success" : "error");
        } catch (e) { UI.toast("Test failed: " + e.message, "error"); }
    }

    async function deliveries(id) {
        try {
            const data = await API.get(`/api/webhooks/${id}/deliveries`);
            const html = data.deliveries.map(d => `
                <div class="feed-item">
                    <strong>${escapeHtml(d.event)}</strong> —
                    ${d.status_code ? `HTTP ${d.status_code}` : "error"}
                    <span class="muted"> · ${d.duration_ms}ms · ${d.created_at}</span>
                    ${d.error ? `<div class="muted" style="font-size:var(--fs-xs);">${escapeHtml(d.error)}</div>` : ""}
                </div>`).join("") || "<div class='empty'>No deliveries yet.</div>";
            UI.modal({
                title: "Recent deliveries",
                body: html,
                actions: [{ label: "Close", kind: "primary" }],
            });
        } catch (e) { UI.toast("Load failed: " + e.message, "error"); }
    }

    async function remove(id) {
        if (!confirm("Delete this webhook?")) return;
        try {
            await API.del("/api/webhooks/" + id);
            UI.toast("Deleted");
            load();
        } catch (e) { UI.toast("Delete failed: " + e.message, "error"); }
    }

    function escapeHtml(s) {
        return (s ?? "").toString().replace(/[&<>"']/g, c =>
            ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
    }

    function init() {
        document.getElementById("webhooks-new")?.addEventListener("click", create);
        document.getElementById("webhooks-refresh")?.addEventListener("click", load);
    }
    function onShow() { load(); }

    return { init, onShow, load, create, test, deliveries, remove };
})();
