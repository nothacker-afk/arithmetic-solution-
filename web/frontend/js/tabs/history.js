const History = (() => {
    function render(items) {
        const list = document.getElementById("history-list");
        if (!items.length) {
            list.innerHTML = `<div class="empty">No calculations yet.</div>`;
            return;
        }
        list.innerHTML = items.map(it => `
            <div class="feed-item" style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
                <span class="mono">${it.expression} = <strong>${it.result}</strong></span>
                <button class="btn btn-ghost btn-icon" data-id="${it.id}" aria-label="Delete">×</button>
            </div>
        `).join("");
        list.querySelectorAll("button[data-id]").forEach(btn => {
            btn.addEventListener("click", () => remove(btn.dataset.id));
        });
    }

    async function load() {
        const list = document.getElementById("history-list");
        if (!API.isLoggedIn()) {
            list.innerHTML = `<div class="empty">Login to see your history.</div>`;
            return;
        }
        list.innerHTML = `<div class="skeleton" style="height:40px;margin-bottom:8px;"></div>
                          <div class="skeleton" style="height:40px;margin-bottom:8px;"></div>
                          <div class="skeleton" style="height:40px;"></div>`;
        try {
            const items = await API.get("/api/history?limit=50");
            render(items);
        } catch (e) {
            // Offline fallback: use cached calculations from IndexedDB
            if (window.Offline && Offline.listCalcs) {
                try {
                    const cached = await Offline.listCalcs(50);
                    if (cached.length) {
                        render(cached.map(c => ({
                            id: c.id,
                            expression: c.expression,
                            result: c.result,
                        })));
                        UI.toast && UI.toast("Showing cached history (offline)", "warning");
                        return;
                    }
                } catch (cacheErr) { /* ignore */ }
            }
            list.innerHTML = `<div class="empty">Error: ${e.message}</div>`;
        }
    }

    async function remove(id) {
        try {
            await API.del("/api/history/" + id);
            UI.toast("Deleted", "success");
            load();
        } catch (e) {
            UI.toast("Delete failed: " + e.message, "error");
        }
    }

    function init() {
        document.getElementById("history-refresh")?.addEventListener("click", load);
    }

    return { init, load, remove };
})();
