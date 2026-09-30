// Event reminders (Phase 73)
const EventReminders = (() => {
    const OPTIONS = [5, 10, 15, 30, 60, 120, 1440];

    function fmtMinutes(m) {
        if (m === 1440) return "1 day";
        if (m >= 60) return `${m / 60} hour${m / 60 > 1 ? "s" : ""}`;
        return `${m} min`;
    }

    async function open(roomId, eventId, eventTitle) {
        if (!API.isLoggedIn()) { UI.toast("Login first", "warning"); return; }
        let existing = [];
        try {
            const data = await API.get(`/api/rooms/${roomId}/events/${eventId}/reminders`);
            existing = data.reminders.map(r => r.minutes_before);
        } catch (e) {
            UI.toast("Load failed: " + e.message, "error");
            return;
        }

        const body = document.createElement("div");
        body.innerHTML = `
            <p class="muted">Get notified before <strong>${eventTitle}</strong>.</p>
            <div style="display:flex;flex-direction:column;gap:6px;">
                ${OPTIONS.map(m => `
                    <label style="display:flex;align-items:center;gap:8px;
                                  padding:6px 10px;background:var(--bg-0);
                                  border:1px solid var(--border);border-radius:6px;">
                        <input type="checkbox" data-minutes="${m}" ${existing.includes(m) ? "checked" : ""} />
                        ${fmtMinutes(m)} before
                    </label>`).join("")}
            </div>`;
        UI.modal({
            title: "Reminders",
            body,
            actions: [
                { label: "Save", kind: "primary", close: false, onClick: async (bd) => {
                    const boxes = [...bd.querySelectorAll("input[data-minutes]")];
                    for (const b of boxes) {
                        const minutes = parseInt(b.dataset.minutes);
                        const has = existing.includes(minutes);
                        if (b.checked && !has) {
                            try {
                                await API.post(`/api/rooms/${roomId}/events/${eventId}/reminders`,
                                    { minutes_before: minutes });
                            } catch (e) { UI.toast("Add failed: " + e.message, "error"); }
                        } else if (!b.checked && has) {
                            try {
                                await API.del(`/api/rooms/${roomId}/events/${eventId}/reminders/${minutes}`);
                            } catch (e) { UI.toast("Remove failed: " + e.message, "error"); }
                        }
                    }
                    UI.toast("Reminders updated", "success");
                    bd.remove();
                }},
                { label: "Cancel" },
            ],
        });
    }

    return { open };
})();
