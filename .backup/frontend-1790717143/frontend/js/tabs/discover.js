const Discover = (() => {
    async function load() {
        const list = document.getElementById("discover-list");
        list.innerHTML = `<div class="skeleton" style="height:60px;margin-bottom:6px;"></div>
                          <div class="skeleton" style="height:60px;"></div>`;
        const q = document.getElementById("discover-q")?.value.trim() || "";
        const tag = document.getElementById("discover-tag")?.value.trim() || "";
        try {
            const params = new URLSearchParams();
            if (q) params.set("q", q);
            if (tag) params.set("tag", tag);
            const data = await API.get("/api/discover/rooms?" + params.toString());
            if (!data.rooms.length) {
                list.innerHTML = `<div class="empty">No public rooms found.</div>`;
                return;
            }
            list.innerHTML = data.rooms.map(r => `
                <div class="card" style="padding:12px;margin-bottom:8px;">
                    <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
                        <div>
                            <strong>${r.name}</strong>
                            <div class="muted" style="font-size:var(--fs-xs);">
                                by ${r.owner || "?"} · ${r.member_count} members · ${r.message_count} messages
                            </div>
                            <div style="font-size:var(--fs-sm);margin-top:6px;">${r.description || ""}</div>
                            ${r.tags ? `<div style="margin-top:6px;">${r.tags.split(",").map(t =>
                                `<span class="badge" style="margin-right:4px;">${t.trim()}</span>`).join("")}</div>` : ""}
                        </div>
                        <button class="btn btn-primary" onclick="Discover.join('${r.name}')">Join</button>
                    </div>
                </div>
            `).join("");
        } catch (e) {
            list.innerHTML = `<div class="empty">Error: ${e.message}</div>`;
        }
    }

    async function join(room) {
        try {
            await API.post(`/api/rooms/${room}/join`, {});
            UI.toast("Joined " + room, "success");
            Tab.go("realtime");
            setTimeout(() => {
                const inp = document.getElementById("rt-room");
                if (inp) inp.value = room;
                document.getElementById("rt-join")?.click();
            }, 100);
        } catch (e) { UI.toast("Join failed: " + e.message, "error"); }
    }

    function init() {
        document.getElementById("discover-refresh")?.addEventListener("click", load);
        document.getElementById("discover-q")?.addEventListener("keydown", (e) => {
            if (e.key === "Enter") { e.preventDefault(); load(); }
        });
    }

    function onShow() { load(); }

    return { init, onShow, load, join };
})();
