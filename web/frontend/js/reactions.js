// Message reactions (Phase 32)
const Reactions = (() => {
    const PALETTE = ["👍", "❤️", "😂", "🎉", "🔥", "👀"];
    const cache = {};  // key: "kind:message_id" -> {emoji: [user_ids]}

    function key(kind, id) { return `${kind}:${id}`; }

    async function load(kind, ids) {
        if (!ids.length) return {};
        try {
            const data = await API.get(
                `/api/reactions?kind=${kind}&message_ids=${ids.join(",")}`);
            for (const [mid, m] of Object.entries(data.reactions)) {
                cache[key(kind, mid)] = m;
            }
            return data.reactions;
        } catch (e) {
            console.warn("reactions load failed:", e);
            return {};
        }
    }

    async function toggle(kind, messageId, emoji) {
        const k = key(kind, messageId);
        const current = cache[k] || {};
        const mine = (current[emoji] || []).includes(myUserId());
        try {
            if (mine) {
                await API.del("/api/reactions", { kind, message_id: messageId, emoji });
            } else {
                await API.post("/api/reactions", { kind, message_id: messageId, emoji });
            }
            // Optimistic update
            if (!current[emoji]) current[emoji] = [];
            if (mine) current[emoji] = current[emoji].filter(u => u !== myUserId());
            else current[emoji].push(myUserId());
            if (!current[emoji].length) delete current[emoji];
            cache[k] = current;
            return current;
        } catch (e) {
            UI.toast("Reaction failed: " + e.message, "error");
            return current;
        }
    }

    function myUserId() {
        const t = API.token;
        if (!t) return 0;
        try {
            const payload = JSON.parse(atob(t.split(".")[1]));
            return parseInt(payload.sub, 10) || 0;
        } catch { return 0; }
    }

    function renderChips(kind, messageId, container) {
        const data = cache[key(kind, messageId)] || {};
        const entries = Object.entries(data).filter(([, users]) => users.length);
        if (!entries.length) {
            container.innerHTML = "";
            return;
        }
        const me = myUserId();
        container.innerHTML = entries.map(([emoji, users]) => `
            <button class="reaction-chip ${users.includes(me) ? "mine" : ""}"
                    data-emoji="${emoji}" data-kind="${kind}" data-mid="${messageId}">
                ${emoji} <span>${users.length}</span>
            </button>
        `).join("");
        container.querySelectorAll(".reaction-chip").forEach(btn => {
            btn.addEventListener("click", async () => {
                await toggle(btn.dataset.kind, +btn.dataset.mid, btn.dataset.emoji);
                renderChips(kind, +btn.dataset.mid, container);
            });
        });
    }

    function renderPicker(kind, messageId, container) {
        container.innerHTML = PALETTE.map(e =>
            `<button class="reaction-pick" data-emoji="${e}">${e}</button>`
        ).join("");
        container.querySelectorAll(".reaction-pick").forEach(btn => {
            btn.addEventListener("click", async () => {
                await toggle(kind, messageId, btn.dataset.emoji);
                container.parentElement.querySelector(".reaction-chips");
                renderChips(kind, messageId, container.parentElement);
            });
        });
    }

    return { PALETTE, load, toggle, renderChips, renderPicker };
})();
