// Global search across rooms, DMs, groups, wiki, calc (Phase 85)
const GlobalSearch = (() => {
    async function run() {
        const q = document.getElementById("gs-input")?.value.trim();
        const list = document.getElementById("gs-results");
        if (!q || !list) return;

        list.innerHTML = `<div class="skeleton" style="height:50px;margin-bottom:6px;"></div>
                          <div class="skeleton" style="height:50px;"></div>`;
        try {
            const data = await API.get(`/api/search/global?q=${encodeURIComponent(q)}`);
            if (!data.results.length) {
                list.innerHTML = `<div class="empty">No results in any context.</div>`;
                return;
            }
            const kindBadge = {
                chat: "💬 room",
                dm: "📩 dm",
                group: "👥 group",
                wiki: "📖 wiki",
                calc: "🧮 calc",
            };
            list.innerHTML = data.results.map(r => `
                <div class="feed-item" style="cursor:pointer;"
                     onclick="GlobalSearch.open('${r.kind}', '${r.scope_id}', ${r.id})">
                    <div>
                        <span class="badge">${kindBadge[r.kind] || r.kind}</span>
                        ${r.sender ? `<strong>${escapeHtml(r.sender)}</strong>: ` : ""}
                        ${r.title ? `<strong>${escapeHtml(r.title)}</strong> — ` : ""}
                        <span class="muted">${escapeHtml(r.snippet)}</span>
                    </div>
                    <div class="muted" style="font-size:var(--fs-xs);">${r.created_at || ""}</div>
                </div>
            `).join("");
        } catch (e) {
            list.innerHTML = `<div class="empty">Error: ${escapeHtml(e.message)}</div>`;
        }
    }

    function open(kind, scopeId, msgId) {
        if (kind === "chat") {
            Tab.go("realtime");
            setTimeout(() => {
                const inp = document.getElementById("rt-room");
                if (inp) inp.value = scopeId;
                document.getElementById("rt-join")?.click();
            }, 100);
        } else if (kind === "dm") {
            if (window.DMs && DMs.open) {
                Tab.go("dms");
                setTimeout(() => DMs.open(+scopeId), 200);
            }
        } else if (kind === "group") {
            if (window.Groups) {
                Tab.go("groups");
                setTimeout(() => Groups.open(+scopeId, ""), 200);
            }
        } else if (kind === "wiki") {
            Tab.go("room");
            setTimeout(() => {
                const inp = document.getElementById("room-tab-room");
                if (inp) inp.value = scopeId;
                RoomTab.refreshAll();
            }, 100);
        } else if (kind === "calc") {
            Tab.go("history");
        }
    }

    function escapeHtml(s) {
        return (s ?? "").toString().replace(/[&<>"']/g, c =>
            ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
    }

    function init() {
        document.getElementById("gs-go")?.addEventListener("click", run);
        document.getElementById("gs-input")?.addEventListener("keydown", (e) => {
            if (e.key === "Enter") { e.preventDefault(); run(); }
        });
    }

    return { init, run, open };
})();
