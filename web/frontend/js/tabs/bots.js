const Bots = (() => {
    async function load() {
        const list = document.getElementById("bots-list");
        if (!API.isLoggedIn()) {
            list.innerHTML = `<div class="empty">Login to manage bots.</div>`;
            return;
        }
        try {
            const data = await API.get("/api/bots");
            if (!data.bots.length) {
                list.innerHTML = `<div class="empty">No bots yet.</div>`;
                return;
            }
            list.innerHTML = data.bots.map(b => `
                <div class="contact-row">
                    <span>🤖 <strong>${b.name}</strong>
                        <span class="muted">in ${b.room_id}</span></span>
                    <button class="btn btn-ghost btn-icon" onclick="Bots.remove('${b.id}')">×</button>
                </div>
            `).join("");
        } catch (e) {
            list.innerHTML = `<div class="empty">Error: ${e.message}</div>`;
        }
    }

    async function create() {
        const room = document.getElementById("bot-room").value.trim();
        const name = document.getElementById("bot-name").value.trim();
        if (!room || !name) return;
        try {
            const data = await API.post("/api/bots", { room_id: room, name });
            // Show the token in a modal — user must save it
            UI.modal({
                title: "Bot created — save this token",
                body: `<p>The token is shown ONCE. Store it safely.</p>
                       <div class="field"><label>Bot ID</label>
                       <input class="input mono" value="${data.id}" readonly /></div>
                       <div class="field"><label>Token</label>
                       <input class="input mono" value="${data.token}" readonly /></div>
                       <p class="muted" style="font-size:var(--fs-sm);">
                       Post messages with:<br>
                       <code>curl -X POST .../api/bots/${data.id}/messages \\
                       -H 'Authorization: Bot ${data.token}' \\
                       -d '{"body":"!help"}'</code></p>`,
                actions: [{ label: "Done", kind: "primary" }],
            });
            document.getElementById("bot-name").value = "";
            load();
        } catch (e) { UI.toast("Create failed: " + e.message, "error"); }
    }

    async function remove(id) {
        if (!confirm("Delete this bot?")) return;
        try {
            await API.del("/api/bots/" + id);
            UI.toast("Deleted");
            load();
        } catch (e) { UI.toast("Delete failed: " + e.message, "error"); }
    }

    function init() {
        document.getElementById("bot-create")?.addEventListener("click", create);
        document.getElementById("bots-refresh")?.addEventListener("click", load);
    }

    function onShow() { load(); }

    return { init, onShow, load, create, remove };
})();
