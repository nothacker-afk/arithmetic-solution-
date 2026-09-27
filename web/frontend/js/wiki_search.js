// Wiki search (Phase 80)
const WikiSearch = (() => {
    async function run() {
        const q = document.getElementById("wikisearch-input")?.value.trim();
        const room = document.getElementById("wikisearch-room")?.value.trim() || "";
        const list = document.getElementById("wikisearch-results");
        if (!list) return;
        if (!q) { list.innerHTML = ""; return; }

        list.innerHTML = `<div class="skeleton" style="height:50px;margin-bottom:6px;"></div>
                          <div class="skeleton" style="height:50px;"></div>`;
        try {
            const params = new URLSearchParams({ q });
            if (room) params.set("room", room);
            const data = await API.get("/api/wiki/search?" + params.toString());
            if (!data.results.length) {
                list.innerHTML = `<div class="empty">No wiki pages matched.</div>`;
                return;
            }
            list.innerHTML = data.results.map(r => `
                <div class="feed-item">
                    <div><strong>${escapeHtml(r.title)}</strong>
                        <span class="muted" style="font-size:var(--fs-xs);">in ${escapeHtml(r.room_id)}</span></div>
                    <div class="muted" style="font-size:var(--fs-sm);margin-top:4px;">
                        ${escapeHtml(r.snippet)}
                    </div>
                    <button class="btn btn-ghost"
                            onclick="WikiSearch.open('${escapeHtml(r.room_id)}','${escapeHtml(r.slug)}')">
                        Open page →
                    </button>
                </div>
            `).join("");
        } catch (e) {
            list.innerHTML = `<div class="empty">Error: ${e.message}</div>`;
        }
    }

    function open(room, slug) {
        // Reuse the room wiki modal opener
        if (window.RoomTab && RoomTab.openWiki) {
            // Set the room in the input so RoomTab targets the right room
            const inp = document.getElementById("room-tab-room");
            if (inp) inp.value = room;
            Tab.go("room");
            setTimeout(() => RoomTab.openWiki(slug), 100);
        } else {
            UI.toast("Open the Room tab and load " + room);
        }
    }

    function escapeHtml(s) {
        return (s ?? "").toString().replace(/[&<>"']/g, c =>
            ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
    }

    function init() {
        document.getElementById("wikisearch-go")?.addEventListener("click", run);
        document.getElementById("wikisearch-input")?.addEventListener("keydown", (e) => {
            if (e.key === "Enter") { e.preventDefault(); run(); }
        });
    }

    return { init, run, open };
})();
