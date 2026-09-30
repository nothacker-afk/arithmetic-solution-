/* Save / share calculations (Phase 88) */
const CalcShare = (() => {
    async function saveCurrent() {
        if (!API.isLoggedIn()) { UI.toast("Sign in to save calculations", "warning"); return; }
        const resultEl = document.getElementById("result");
        const exprInput = document.getElementById("calc-expr");
        if (!resultEl || !exprInput) return;
        const expression = exprInput.value.trim();
        const resultText = resultEl.querySelector(".calc-result-value")?.textContent || resultEl.textContent;
        if (!expression) { UI.toast("Nothing to save", "warning"); return; }
        try {
            const data = await API.post("/api/calc/save", {
                expression, result: resultText, is_public: true,
            });
            const url = window.location.origin + data.url;
            try { await navigator.clipboard.writeText(url); } catch {}
            UI.toast("Saved + link copied: " + data.url, "success", 5000);
        } catch (e) { UI.toast("Save failed: " + e.message, "error"); }
    }
    async function showMine() {
        if (!API.isLoggedIn()) { UI.toast("Sign in first", "warning"); return; }
        try {
            const data = await API.get("/api/calc/saved");
            const html = data.calculations.length
                ? data.calculations.map(c => `
                    <div class="feed-item">
                        <code>${escapeHtml(c.expression)}</code>
                        = <strong>${escapeHtml(c.result)}</strong>
                        <div class="muted" style="font-size:var(--fs-xs);">
                            ${c.views} views · ${c.created_at}
                        </div>
                        <button class="btn btn-ghost btn-sm"
                                onclick="CalcShare.copyLink('${c.id}')">Copy link</button>
                    </div>`).join("")
                : "<div class='empty'>No saved calculations.</div>";
            UI.modal({ title: "My saved", body: html, actions: [{ label: "Close", kind: "primary" }] });
        } catch (e) { UI.toast("Load failed: " + e.message, "error"); }
    }
    function copyLink(id) {
        const url = window.location.origin + "/calc/" + id;
        try { navigator.clipboard.writeText(url); } catch {}
        UI.toast("Link copied: " + url, "success");
    }
    function init() {
        document.getElementById("calc-save-btn")?.addEventListener("click", saveCurrent);
        document.getElementById("calc-share-list")?.addEventListener("click", showMine);
        document.getElementById("calc-solve-btn")?.addEventListener("click", () => {
            if (window.Solver) Solver.open();
        });
        document.getElementById("calc-plot-btn")?.addEventListener("click", () => {
            if (window.Plotter) Plotter.open();
        });
    }
    function escapeHtml(s) {
        return String(s ?? "").replace(/[&<>"']/g, c =>
            ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
    }
    return { init, saveCurrent, showMine, copyLink };
})();
