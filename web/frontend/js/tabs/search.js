const Search = (() => {
    let lastQuery = "";

    function render(results, engine) {
        const list = document.getElementById("search-results");
        const engineEl = document.getElementById("search-engine");
        engineEl.textContent = results.length
            ? `${results.length} result(s) · engine: ${engine}`
            : `No results · engine: ${engine}`;
        if (!results.length) {
            list.innerHTML = `<div class="empty">Try a different query.</div>`;
            return;
        }
        list.innerHTML = results.map(r => {
            if (r.kind === "calculation") {
                return `<div class="feed-item">
                    <span class="badge">calc</span>
                    <span class="mono">${r.expression} = <strong>${r.result}</strong></span>
                    <span class="muted" style="font-size:var(--fs-xs);margin-left:8px;">${r.created_at || ""}</span>
                </div>`;
            }
            return `<div class="feed-item">
                <span class="badge">chat</span>
                <strong>${r.username}</strong>: ${r.body}
                <span class="muted" style="font-size:var(--fs-xs);margin-left:8px;">in ${r.room_id}</span>
            </div>`;
        }).join("");
    }

    async function run() {
        const q = document.getElementById("search-input").value.trim();
        if (!q) return;
        lastQuery = q;
        const scope = document.getElementById("search-scope").value;
        const list = document.getElementById("search-results");
        list.innerHTML = `<div class="skeleton" style="height:40px;margin-bottom:8px;"></div>
                          <div class="skeleton" style="height:40px;"></div>`;
        try {
            const data = await API.get(`/api/search?q=${encodeURIComponent(q)}&scope=${scope}`);
            render(data.results, data.engine);
        } catch (e) {
            list.innerHTML = `<div class="empty">Error: ${e.message}</div>`;
        }
    }

    function init() {
        document.getElementById("search-go")?.addEventListener("click", run);
        document.getElementById("search-input")?.addEventListener("keydown", (e) => {
            if (e.key === "Enter") { e.preventDefault(); run(); }
        });
    }

    return { init, run };
})();
