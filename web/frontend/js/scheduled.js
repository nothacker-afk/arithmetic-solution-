// Scheduled messages (Phase 46)
const Scheduled = (() => {
    function openComposer() {
        const room = document.getElementById("rt-room")?.value.trim();
        if (!room) { UI.toast("Join a room first", "warning"); return; }
        const user = document.getElementById("rt-user")?.value.trim() || "guest";

        // Default: 15 minutes from now
        const d = new Date(Date.now() + 15 * 60 * 1000);
        const iso = d.toISOString().slice(0, 16); // yyyy-mm-ddThh:mm

        const body = document.createElement("div");
        body.innerHTML = `
            <div class="field"><label>Message</label>
                <textarea id="sched-body" class="input" rows="3" placeholder="Say something later…"></textarea></div>
            <div class="field"><label>Send at (local time)</label>
                <input id="sched-when" class="input" type="datetime-local" value="${iso}" /></div>
            <p class="muted" style="font-size:var(--fs-sm);">
                Message will be delivered to <strong>${room}</strong> as <strong>${user}</strong>.
            </p>`;

        UI.modal({
            title: "Schedule message",
            body,
            actions: [
                { label: "Schedule", kind: "primary", close: false, onClick: async (backdrop) => {
                    const text = backdrop.querySelector("#sched-body").value.trim();
                    const when = backdrop.querySelector("#sched-when").value;
                    if (!text || !when) { UI.toast("Message and time required", "warning"); return; }
                    try {
                        const send_at = new Date(when).toISOString();
                        await API.post("/api/scheduled", {
                            room_id: room, body: text, send_at,
                        });
                        UI.toast("Scheduled ✓", "success");
                        backdrop.remove();
                        listPending();
                    } catch (e) { UI.toast("Failed: " + e.message, "error"); }
                }},
                { label: "Cancel" },
            ],
        });
    }

    async function listPending() {
        const list = document.getElementById("sched-list");
        if (!list) return;
        if (!API.isLoggedIn()) {
            list.innerHTML = `<div class="empty">Login to see scheduled messages.</div>`;
            return;
        }
        try {
            const data = await API.get("/api/scheduled");
            if (!data.pending.length) {
                list.innerHTML = `<div class="empty">No scheduled messages.</div>`;
                return;
            }
            list.innerHTML = data.pending.map(s => {
                const when = new Date(s.send_at).toLocaleString();
                return `
                    <div class="contact-row">
                        <span>⏰ <strong>${s.room_id}</strong>
                            <span class="muted">${when}</span>
                            <div class="mono" style="font-size:var(--fs-sm);">${escapeHtml(s.body).slice(0, 60)}</div>
                        </span>
                        <button class="btn btn-ghost btn-icon" onclick="Scheduled.cancel('${s.id}')">×</button>
                    </div>`;
            }).join("");
        } catch (e) {
            list.innerHTML = `<div class="empty">Error: ${e.message}</div>`;
        }
    }

    async function cancel(id) {
        try {
            await API.del("/api/scheduled/" + id);
            UI.toast("Cancelled");
            listPending();
        } catch (e) { UI.toast("Cancel failed: " + e.message, "error"); }
    }

    function escapeHtml(s) {
        return (s ?? "").toString().replace(/[&<>"']/g, c =>
            ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
    }

    function init() {
        document.getElementById("sched-open")?.addEventListener("click", openComposer);
        document.getElementById("sched-refresh")?.addEventListener("click", listPending);
    }

    return { init, listPending, openComposer, cancel };
})();
