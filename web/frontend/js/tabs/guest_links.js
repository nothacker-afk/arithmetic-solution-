// Guest access links (Phase 65)
const GuestLinks = (() => {
    async function create() {
        const room = document.getElementById("rt-room")?.value.trim()
                  || document.getElementById("room-tab-room")?.value.trim();
        if (!room) { UI.toast("Enter a room name first", "warning"); return; }
        if (!API.isLoggedIn()) { UI.toast("Login first", "warning"); return; }

        const body = document.createElement("div");
        body.innerHTML = `
            <div class="field"><label>Label (optional)</label>
                <input id="gl-label" class="input" placeholder="Friend invite" /></div>
            <div class="field"><label>Expires in (hours)</label>
                <input id="gl-hours" class="input" type="number" min="1" max="2160" value="168" /></div>
            <div class="field"><label>Max uses (blank = unlimited)</label>
                <input id="gl-uses" class="input" type="number" min="1" max="1000" /></div>
            <div class="field">
                <label><input id="gl-write" type="checkbox" style="width:auto;margin-right:6px;" />
                Allow guest to post messages</label>
            </div>`;
        UI.modal({
            title: `Guest link for ${room}`,
            body,
            actions: [
                { label: "Create link", kind: "primary", close: false, onClick: async (bd) => {
                    const label = bd.querySelector("#gl-label").value.trim() || null;
                    const hours = parseInt(bd.querySelector("#gl-hours").value) || 168;
                    const uses = bd.querySelector("#gl-uses").value.trim();
                    const max_uses = uses ? parseInt(uses) : null;
                    const allow_write = bd.querySelector("#gl-write").checked;
                    try {
                        const data = await API.post(`/api/rooms/${room}/guest_tokens`,
                            { label, expires_in_hours: hours, max_uses, allow_write });
                        const fullUrl = window.location.origin + data.url;
                        // Copy to clipboard
                        try { await navigator.clipboard.writeText(fullUrl); } catch {}
                        bd.innerHTML = `
                            <p>Guest link created and copied to clipboard:</p>
                            <input class="input mono" value="${fullUrl}" readonly />
                            <p class="muted" style="font-size:var(--fs-sm);margin-top:8px;">
                                Expires: ${data.expires_at}<br>
                                Uses: ${data.uses_remaining ?? "unlimited"}<br>
                                Write access: ${data.allow_write}
                            </p>`;
                    } catch (e) { UI.toast("Create failed: " + e.message, "error"); }
                }},
                { label: "Close" },
            ],
        });
    }

    function init() {
        document.getElementById("guest-link-create")?.addEventListener("click", create);
    }

    return { init, create };
})();
