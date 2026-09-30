const Contacts = (() => {
    async function load() {
        const list = document.getElementById("contacts-list");
        if (!API.isLoggedIn()) {
            list.innerHTML = `<div class="empty">Login to manage contacts.</div>`;
            return;
        }
        list.innerHTML = `<div class="skeleton" style="height:40px;margin-bottom:6px;"></div>
                          <div class="skeleton" style="height:40px;"></div>`;
        try {
            const data = await API.get("/api/contacts");
            if (!data.contacts.length) {
                list.innerHTML = `<div class="empty">No contacts yet.</div>`;
                return;
            }
            list.innerHTML = data.contacts.map(c => `
                <div class="contact-row">
                    <span class="contact-name">
                        ${c.favourite ? "⭐ " : ""}<strong>${c.nickname || c.username}</strong>
                        ${c.nickname ? `<span class="muted">(${c.username})</span>` : ""}
                        ${c.shared_threads ? `<span class="badge">${c.shared_threads}</span>` : ""}
                    </span>
                    <span class="contact-actions">
                        <button class="btn btn-ghost btn-icon" title="Toggle favourite"
                                onclick="Contacts.toggleFav(${c.contact_user_id}, ${c.favourite ? 0 : 1})">
                            ${c.favourite ? "★" : "☆"}
                        </button>
                        <button class="btn btn-ghost btn-icon" title="Message"
                                onclick="Contacts.openDm('${c.username}')">💬</button>
                        <button class="btn btn-ghost btn-icon" title="Remove"
                                onclick="Contacts.remove(${c.contact_user_id})">×</button>
                    </span>
                </div>
            `).join("");
        } catch (e) {
            list.innerHTML = `<div class="empty">Error: ${e.message}</div>`;
        }
    }

    async function add() {
        const u = document.getElementById("contact-username").value.trim();
        if (!u) return;
        try {
            await API.post("/api/contacts", { username: u });
            UI.toast("Contact added", "success");
            document.getElementById("contact-username").value = "";
            load();
        } catch (e) { UI.toast("Add failed: " + e.message, "error"); }
    }

    async function remove(id) {
        if (!confirm("Remove this contact?")) return;
        try {
            await API.del("/api/contacts/" + id);
            UI.toast("Removed", "success");
            load();
        } catch (e) { UI.toast("Remove failed: " + e.message, "error"); }
    }

    async function toggleFav(id, fav) {
        try {
            await API.put(`/api/contacts/${id}/favourite`, { favourite: !!fav });
            load();
        } catch (e) { UI.toast("Favourite failed: " + e.message, "error"); }
    }

    async function openDm(username) {
        if (window.DMs) {
            Tab.go("dms");
            setTimeout(() => {
                const inp = document.getElementById("dm-new-user");
                if (inp) { inp.value = username; }
                document.getElementById("dm-start")?.click();
            }, 100);
        }
    }

    // Blocks
    async function loadBlocks() {
        const list = document.getElementById("blocks-list");
        if (!list) return;
        try {
            const data = await API.get("/api/blocks");
            if (!data.blocks.length) {
                list.innerHTML = `<div class="empty">No blocks.</div>`;
                return;
            }
            list.innerHTML = data.blocks.map(b => `
                <div class="contact-row">
                    <span>🚫 <strong>${b.username}</strong>
                        <span class="muted">${b.reason || ""}</span>
                    </span>
                    <button class="btn btn-ghost btn-icon" onclick="Contacts.unblock(${b.blocked_id})">×</button>
                </div>
            `).join("");
        } catch (e) {
            list.innerHTML = `<div class="empty">Error: ${e.message}</div>`;
        }
    }

    async function block() {
        const u = document.getElementById("block-username").value.trim();
        if (!u) return;
        try {
            await API.post("/api/blocks", { username: u });
            UI.toast("Blocked", "success");
            document.getElementById("block-username").value = "";
            loadBlocks();
        } catch (e) { UI.toast("Block failed: " + e.message, "error"); }
    }

    async function unblock(id) {
        try {
            await API.del("/api/blocks/" + id);
            UI.toast("Unblocked");
            loadBlocks();
        } catch (e) { UI.toast("Unblock failed: " + e.message, "error"); }
    }

    function init() {
        document.getElementById("contact-add")?.addEventListener("click", add);
        document.getElementById("block-add")?.addEventListener("click", block);
        document.getElementById("contacts-refresh")?.addEventListener("click", load);
    }

    function onShow() { load(); loadBlocks(); }

    return { init, onShow, load, loadBlocks, add, remove, toggleFav, openDm, block, unblock };
})();
