// Custom emoji packs (Phase 61)
const EmojiPacks = (() => {
    async function load() {
        const list = document.getElementById("emoji-packs-list");
        if (!API.isLoggedIn()) {
            list.innerHTML = `<div class="empty">Login to manage emoji packs.</div>`;
            return;
        }
        try {
            const data = await API.get("/api/emoji_packs");
            if (!data.packs.length) {
                list.innerHTML = `<div class="empty">No emoji packs yet.</div>`;
                return;
            }
            list.innerHTML = data.packs.map(p => `
                <div class="feed-item" style="display:flex;justify-content:space-between;align-items:center;">
                    <span>🎨 <strong>${p.name}</strong>
                        ${p.is_public ? '<span class="badge">public</span>' : ""}
                        ${p.room_id ? `<span class="badge">${p.room_id}</span>` : ""}
                        <span class="muted" style="font-size:var(--fs-xs);"> · ${p.item_count} items</span>
                    </span>
                    <button class="btn btn-ghost btn-icon" onclick="EmojiPacks.open('${p.id}', '${p.name}')">👁</button>
                </div>
            `).join("");
        } catch (e) {
            list.innerHTML = `<div class="empty">Error: ${e.message}</div>`;
        }
    }

    async function create() {
        const body = document.createElement("div");
        body.innerHTML = `
            <div class="field"><label>Pack name</label>
                <input id="pk-name" class="input" placeholder="My pack" /></div>
            <div class="field"><label>Room (optional)</label>
                <input id="pk-room" class="input" placeholder="leave blank for personal" /></div>
            <div class="field">
                <label><input id="pk-public" type="checkbox" style="width:auto;margin-right:6px;" />
                Make this pack public (visible to everyone)</label>
            </div>`;
        UI.modal({
            title: "New emoji pack",
            body,
            actions: [
                { label: "Create", kind: "primary", close: false, onClick: async (bd) => {
                    const name = bd.querySelector("#pk-name").value.trim();
                    const room_id = bd.querySelector("#pk-room").value.trim() || null;
                    const is_public = bd.querySelector("#pk-public").checked;
                    if (!name) return;
                    try {
                        const pack = await API.post("/api/emoji_packs",
                            { name, room_id, is_public });
                        UI.toast("Pack created", "success");
                        bd.remove();
                        await load();
                        open(pack.id, pack.name);
                    } catch (e) { UI.toast("Create failed: " + e.message, "error"); }
                }},
                { label: "Cancel" },
            ],
        });
    }

    async function open(packId, packName) {
        try {
            const pack = await API.get(`/api/emoji_packs/${packId}`);
            const body = document.createElement("div");
            body.innerHTML = `
                <div style="display:flex;flex-wrap:wrap;gap:6px;min-height:40px;margin-bottom:12px;">
                    ${pack.items.map(it => `
                        <span title=":${it.name}:" style="font-size:1.6em;padding:4px;background:var(--bg-0);border-radius:6px;">
                            ${it.image_url ? `<img src="${it.image_url}" style="width:24px;height:24px;vertical-align:middle;">` : it.emoji}
                        </span>`).join("") || `<span class="muted">No items yet.</span>`}
                </div>
                <hr style="border:none;border-top:1px solid var(--border);margin:12px 0;" />
                <h4>Add item</h4>
                <div class="field"><label>Name (a-z, 0-9, _)</label>
                    <input id="ei-name" class="input" placeholder="party" /></div>
                <div class="field"><label>Emoji (unicode)</label>
                    <input id="ei-emoji" class="input" placeholder="🎉" maxlength="8" /></div>
                <div class="field"><label>Or image URL</label>
                    <input id="ei-img" class="input" placeholder="https://…" /></div>`;
            UI.modal({
                title: packName,
                body,
                actions: [
                    { label: "Add", kind: "primary", close: false, onClick: async (bd) => {
                        const name = bd.querySelector("#ei-name").value.trim().toLowerCase();
                        const emoji = bd.querySelector("#ei-emoji").value.trim() || null;
                        const image_url = bd.querySelector("#ei-img").value.trim() || null;
                        if (!name || (!emoji && !image_url)) return;
                        try {
                            await API.post(`/api/emoji_packs/${packId}/items`,
                                { name, emoji, image_url });
                            UI.toast("Item added", "success");
                            bd.remove();
                            open(packId, packName);
                        } catch (e) { UI.toast("Failed: " + e.message, "error"); }
                    }},
                    { label: "Close", kind: "ghost" },
                ],
            });
        } catch (e) { UI.toast("Load failed: " + e.message, "error"); }
    }

    function init() {
        document.getElementById("emoji-packs-new")?.addEventListener("click", create);
        document.getElementById("emoji-packs-refresh")?.addEventListener("click", load);
    }

    function onShow() { load(); }

    return { init, onShow, load, create, open };
})();
