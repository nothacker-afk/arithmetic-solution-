// "Room" tab aggregator — pins, wiki, events, voice channels (Phases 51-54)
const RoomTab = (() => {
    let currentRoom = null;

    function _room() {
        return document.getElementById("room-tab-room")?.value.trim() ||
               document.getElementById("rt-room")?.value.trim() ||
               currentRoom;
    }

    // ---------- Pins ----------
    async function loadPins() {
        const room = _room();
        const list = document.getElementById("room-pins-list");
        if (!room) { list.innerHTML = `<div class="empty">Enter a room name.</div>`; return; }
        try {
            const data = await API.get(`/api/rooms/${room}/pins`);
            if (!data.pins.length) {
                list.innerHTML = `<div class="empty">No pins yet. Right-click a message → pin.</div>`;
                return;
            }
            list.innerHTML = data.pins.map(p => `
                <div class="pin-row">
                    <div>
                        <strong>${p.author || "?"}</strong>: ${p.body ? p.body.slice(0, 120) : "(attachment)"}
                        ${p.note ? `<div class="muted" style="font-size:var(--fs-xs);">📝 ${p.note}</div>` : ""}
                        <div class="muted" style="font-size:var(--fs-xs);">
                            pinned by ${p.pinned_by} · ${p.created_at}
                        </div>
                    </div>
                    <button class="btn btn-ghost btn-icon" onclick="RoomTab.unpin(${p.message_id})">×</button>
                </div>
            `).join("");
        } catch (e) {
            list.innerHTML = `<div class="empty">Error: ${e.message}</div>`;
        }
    }

    async function unpin(messageId) {
        const room = _room();
        if (!room) return;
        try {
            await API.del(`/api/rooms/${room}/pins/${messageId}`);
            UI.toast("Unpinned");
            loadPins();
        } catch (e) { UI.toast("Unpin failed: " + e.message, "error"); }
    }

    async function pinFromMessage(messageId) {
        const room = _room();
        if (!room) { UI.toast("Enter a room first"); return; }
        const note = prompt("Optional note for this pin:", "") || "";
        try {
            await API.post(`/api/rooms/${room}/pins`, { message_id: messageId, note });
            UI.toast("Pinned", "success");
            loadPins();
        } catch (e) { UI.toast("Pin failed: " + e.message, "error"); }
    }

    // ---------- Wiki ----------
    async function loadWiki() {
        const room = _room();
        const list = document.getElementById("room-wiki-list");
        if (!room) { list.innerHTML = `<div class="empty">Enter a room name.</div>`; return; }
        try {
            const data = await API.get(`/api/rooms/${room}/wiki`);
            if (!data.pages.length) {
                list.innerHTML = `<div class="empty">No wiki pages yet.</div>`;
                return;
            }
            list.innerHTML = data.pages.map(p => `
                <div class="pin-row">
                    <div>
                        <strong>${p.title}</strong>
                        <div class="muted" style="font-size:var(--fs-xs);">
                            ${p.body_length} bytes · updated ${p.updated_at}
                        </div>
                    </div>
                    <button class="btn btn-ghost btn-icon" onclick="RoomTab.openWiki('${p.slug}')">📖</button>
                </div>
            `).join("");
        } catch (e) {
            list.innerHTML = `<div class="empty">Error: ${e.message}</div>`;
        }
    }

    function newWikiPage() {
        const body = document.createElement("div");
        body.innerHTML = `
            <div class="field"><label>Title</label><input id="wiki-title" class="input" /></div>
            <div class="field"><label>Body</label><textarea id="wiki-body" class="input" rows="10"></textarea></div>`;
        UI.modal({
            title: "New wiki page",
            body,
            actions: [
                { label: "Create", kind: "primary", close: false, onClick: async (bd) => {
                    const title = bd.querySelector("#wiki-title").value.trim();
                    const text = bd.querySelector("#wiki-body").value;
                    if (!title) return;
                    try {
                        await API.post(`/api/rooms/${_room()}/wiki`, { title, body: text });
                        UI.toast("Page created", "success");
                        bd.remove();
                        loadWiki();
                    } catch (e) { UI.toast("Create failed: " + e.message, "error"); }
                }},
                { label: "Cancel" },
            ],
        });
    }

    async function openWiki(slug) {
        try {
            const p = await API.get(`/api/rooms/${_room()}/wiki/${slug}`);
            const body = document.createElement("div");
            body.innerHTML = `
                <h3>${p.title}</h3>
                <pre style="white-space:pre-wrap;font-family:inherit;font-size:var(--fs-sm);
                            max-height:60vh;overflow-y:auto;">${escapeHtml(p.body)}</pre>`;
            UI.modal({
                title: p.title,
                body,
                actions: [
                    { label: "Edit", onClick: () => editWiki(slug) },
                    { label: "Close", kind: "primary" },
                ],
            });
        } catch (e) { UI.toast("Load failed: " + e.message, "error"); }
    }

    async function editWiki(slug) {
        try {
            const p = await API.get(`/api/rooms/${_room()}/wiki/${slug}`);
            const body = document.createElement("div");
            body.innerHTML = `
                <div class="field"><label>Title</label><input id="wiki-edit-title" class="input" value="${escapeHtml(p.title)}" /></div>
                <div class="field"><label>Body</label><textarea id="wiki-edit-body" class="input" rows="10">${escapeHtml(p.body)}</textarea></div>`;
            UI.modal({
                title: "Edit page",
                body,
                actions: [
                    { label: "Save", kind: "primary", close: false, onClick: async (bd) => {
                        const title = bd.querySelector("#wiki-edit-title").value;
                        const text = bd.querySelector("#wiki-edit-body").value;
                        try {
                            await API.put(`/api/rooms/${_room()}/wiki/${slug}`, { title, body: text });
                            UI.toast("Saved", "success");
                            bd.remove();
                            loadWiki();
                        } catch (e) { UI.toast("Save failed: " + e.message, "error"); }
                    }},
                    { label: "Cancel" },
                ],
            });
        } catch (e) { UI.toast("Edit failed: " + e.message, "error"); }
    }

    // ---------- Events ----------
    async function loadEvents() {
        const room = _room();
        const list = document.getElementById("room-events-list");
        if (!room) { list.innerHTML = `<div class="empty">Enter a room name.</div>`; return; }
        try {
            const data = await API.get(`/api/rooms/${room}/events`);
            const all = [
                ...(data.upcoming || []).map(e => ({...e, _kind: "upcoming"})),
                ...(data.past || []).map(e => ({...e, _kind: "past"})),
            ];
            if (!all.length) {
                list.innerHTML = `<div class="empty">No events.</div>`;
                return;
            }
            list.innerHTML = all.map(e => `
                <div class="event-row ${e._kind === "past" ? "past" : ""}">
                    <div>
                        <strong>${escapeHtml(e.title)}</strong>
                        <div class="muted" style="font-size:var(--fs-xs);">
                            🕐 ${e.starts_at}${e.ends_at ? " → " + e.ends_at : ""}
                            ${e.location ? " · 📍 " + escapeHtml(e.location) : ""}
                        </div>
                        ${e.description ? `<div style="font-size:var(--fs-sm);">${escapeHtml(e.description)}</div>` : ""}
                        <div style="margin-top:6px;">
                            <span class="badge">👥 ${e.going_count} going</span>
                        </div>
                    </div>
                    <div style="display:flex;flex-direction:column;gap:4px;">
                        <button class="btn btn-ghost btn-icon" onclick="RoomTab.rsvp('${e.id}','going')" title="Going">✓</button>
                        <button class="btn btn-ghost btn-icon" onclick="RoomTab.rsvp('${e.id}','maybe')" title="Maybe">?</button>
                        <button class="btn btn-ghost btn-icon" onclick="RoomTab.rsvp('${e.id}','no')" title="Not going">✗</button>
                    </div>
                </div>
            `).join("");
        } catch (e) {
            list.innerHTML = `<div class="empty">Error: ${e.message}</div>`;
        }
    }

    async function rsvp(eventId, status) {
        try {
            await API.post(`/api/rooms/${_room()}/events/${eventId}/rsvp`, { status });
            UI.toast("RSVP: " + status);
            loadEvents();
        } catch (e) { UI.toast("RSVP failed: " + e.message, "error"); }
    }

    function newEvent() {
        const d = new Date(Date.now() + 24 * 3600 * 1000);
        const iso = d.toISOString().slice(0, 16);
        const body = document.createElement("div");
        body.innerHTML = `
            <div class="field"><label>Title</label><input id="ev-title" class="input" /></div>
            <div class="field"><label>Starts at</label><input id="ev-start" class="input" type="datetime-local" value="${iso}" /></div>
            <div class="field"><label>Ends at (optional)</label><input id="ev-end" class="input" type="datetime-local" /></div>
            <div class="field"><label>Location (optional)</label><input id="ev-loc" class="input" /></div>
            <div class="field"><label>Description</label><textarea id="ev-desc" class="input" rows="3"></textarea></div>`;
        UI.modal({
            title: "New event",
            body,
            actions: [
                { label: "Create", kind: "primary", close: false, onClick: async (bd) => {
                    const title = bd.querySelector("#ev-title").value.trim();
                    const s = bd.querySelector("#ev-start").value;
                    const e = bd.querySelector("#ev-end").value;
                    if (!title || !s) return;
                    try {
                        await API.post(`/api/rooms/${_room()}/events`, {
                            title,
                            starts_at: new Date(s).toISOString(),
                            ends_at: e ? new Date(e).toISOString() : null,
                            location: bd.querySelector("#ev-loc").value.trim(),
                            description: bd.querySelector("#ev-desc").value.trim(),
                        });
                        UI.toast("Event created", "success");
                        bd.remove();
                        loadEvents();
                    } catch (err) { UI.toast("Create failed: " + err.message, "error"); }
                }},
                { label: "Cancel" },
            ],
        });
    }

    // ---------- Voice Channels ----------
    async function loadVC() {
        const room = _room();
        const list = document.getElementById("room-vc-list");
        if (!room) { list.innerHTML = `<div class="empty">Enter a room name.</div>`; return; }
        try {
            const data = await API.get(`/api/rooms/${room}/voice_channels`);
            list.innerHTML = data.channels.map(ch => `
                <div class="vc-channel">
                    <div class="vc-head">
                        🔊 <strong>${ch.name}</strong>
                        <span class="muted">${ch.members.length}</span>
                        <button class="btn btn-ghost" onclick="RoomTab.vcJoin('${ch.name}')">Join</button>
                    </div>
                    ${ch.members.length ? `
                        <div class="vc-members">
                            ${ch.members.map(m =>
                                `<span class="vc-member">${m.muted ? "🔇" : "🎤"} ${escapeHtml(m.username)}</span>`
                            ).join("")}
                        </div>` : ""}
                </div>
            `).join("");
        } catch (e) {
            list.innerHTML = `<div class="empty">Error: ${e.message}</div>`;
        }
    }

    async function vcJoin(channel) {
        try {
            await API.post(`/api/rooms/${_room()}/voice_channels/join`, { channel });
            UI.toast("Joined " + channel, "success");
            loadVC();
        } catch (e) { UI.toast("Join failed: " + e.message, "error"); }
    }

    async function vcLeave() {
        try {
            await API.post(`/api/rooms/${_room()}/voice_channels/leave`, {});
            UI.toast("Left");
            loadVC();
        } catch (e) { UI.toast("Leave failed: " + e.message, "error"); }
    }

    async function vcToggleMute() {
        try {
            const cur = window._vcMuted || false;
            await API.post(`/api/rooms/${_room()}/voice_channels/mute`, { muted: !cur });
            window._vcMuted = !cur;
            loadVC();
        } catch (e) { UI.toast("Mute failed: " + e.message, "error"); }
    }

    // ---------- Utilities ----------
    function escapeHtml(s) {
        return (s ?? "").toString().replace(/[&<>"']/g, c =>
            ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
    }

    function init() {
        document.getElementById("room-refresh")?.addEventListener("click", refreshAll);
        document.getElementById("room-wiki-new")?.addEventListener("click", newWikiPage);
        document.getElementById("room-event-new")?.addEventListener("click", newEvent);
        document.getElementById("room-vc-leave")?.addEventListener("click", vcLeave);
        document.getElementById("room-vc-mute")?.addEventListener("click", vcToggleMute);
    }

    function refreshAll() {
        currentRoom = _room();
        loadPins(); loadWiki(); loadEvents(); loadVC();
    }

    function onShow() { refreshAll(); }

    return { init, onShow, refreshAll,
             loadPins, loadWiki, loadEvents, loadVC,
             unpin, pinFromMessage, openWiki, rsvp, vcJoin, vcLeave, vcToggleMute };
})();
