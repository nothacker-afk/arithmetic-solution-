// Message actions menu (Phase 38) — edit + delete
const MessageActions = (() => {
    function menu(anchorEl, opts) {
        // opts: { canEdit, canDelete, onEdit, onDelete, onViewEdits }
        const existing = document.querySelector(".msg-menu");
        if (existing) existing.remove();

        const menu = document.createElement("div");
        menu.className = "msg-menu";
        menu.innerHTML = `
            ${opts.canEdit ? '<button data-act="edit">✏️ Edit</button>' : ""}
            ${opts.canDelete ? '<button data-act="delete">🗑 Delete</button>' : ""}
            <button data-act="edits">📜 Edit history</button>
        `;
        const rect = anchorEl.getBoundingClientRect();
        menu.style.cssText = `
            position:fixed;left:${rect.left}px;top:${rect.bottom + 4}px;
            z-index:9998;`;
        document.body.appendChild(menu);

        menu.querySelectorAll("button").forEach(btn => {
            btn.addEventListener("click", () => {
                const act = btn.dataset.act;
                menu.remove();
                if (act === "edit" && opts.onEdit) opts.onEdit();
                else if (act === "delete" && opts.onDelete) opts.onDelete();
                else if (act === "edits" && opts.onViewEdits) opts.onViewEdits();
            });
        });

        // Close on outside click
        const closer = (e) => {
            if (!menu.contains(e.target)) {
                menu.remove();
                document.removeEventListener("click", closer);
            }
        };
        setTimeout(() => document.addEventListener("click", closer), 0);
    }

    function attachDots(wrap, opts) {
        if (wrap.querySelector(".msg-dots")) return;
        const dots = document.createElement("button");
        dots.className = "msg-dots";
        dots.textContent = "⋯";
        dots.addEventListener("click", (e) => {
            e.stopPropagation();
            menu(dots, opts);
        });
        wrap.querySelector(".msg-head").appendChild(dots);
    }

    async function showEditHistory(listUrl) {
        try {
            const data = await API.get(listUrl);
            const edits = data.edits || [];
            if (!edits.length) {
                UI.toast("No edit history", "info");
                return;
            }
            const html = edits.map(e => `
                <div class="feed-item">
                    <div class="mono">${escapeHtml(e.old_body)}</div>
                    <div class="muted" style="font-size:var(--fs-xs);">${e.created_at || ""}</div>
                </div>
            `).join("");
            UI.modal({
                title: "Edit history",
                body: html,
                actions: [{ label: "Close", kind: "primary" }],
            });
        } catch (e) {
            UI.toast("Failed to load history: " + e.message, "error");
        }
    }

    function escapeHtml(s) {
        return (s ?? "").toString().replace(/[&<>"']/g, c => (
            {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
    }

    return { attachDots, showEditHistory };
})();
