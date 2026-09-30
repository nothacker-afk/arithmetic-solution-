// Group DMs (Phase 56)
const Groups = (() => {
    let currentGroupId = null;
    let currentGroupName = null;

    async function load() {
        const list = document.getElementById("groups-list");
        if (!API.isLoggedIn()) {
            list.innerHTML = `<div class="empty">Login to use groups.</div>`;
            return;
        }
        list.innerHTML = `<div class="skeleton" style="height:40px;margin-bottom:6px;"></div>
                          <div class="skeleton" style="height:40px;"></div>`;
        try {
            const data = await API.get("/api/groups");
            if (!data.groups.length) {
                list.innerHTML = `<div class="empty">No groups yet.</div>`;
                return;
            }
            list.innerHTML = data.groups.map(g => `
                <div class="feed-item" data-gid="${g.id}" style="cursor:pointer;display:flex;justify-content:space-between;align-items:center;">
                    <span><strong>${g.name}</strong>
                        <span class="muted" style="font-size:var(--fs-xs);"> · ${g.member_count} members</span>
                    </span>
                    ${g.unread ? `<span class="badge live">${g.unread}</span>` : ""}
                </div>
            `).join("");
            list.querySelectorAll("[data-gid]").forEach(el => {
                el.addEventListener("click", () => open(+el.dataset.gid,
                    el.querySelector("strong").textContent));
            });
        } catch (e) {
            list.innerHTML = `<div class="empty">Error: ${e.message}</div>`;
        }
    }

    async function create() {
        const name = prompt("Group name:");
        if (!name) return;
        const membersRaw = prompt("Usernames (comma-separated):", "");
        const usernames = (membersRaw || "").split(",").map(s => s.trim()).filter(Boolean);
        try {
            const data = await API.post("/api/groups", { name, usernames });
            UI.toast(`Created ${data.name}`, "success");
            await load();
            await open(data.id, data.name);
        } catch (e) { UI.toast("Create failed: " + e.message, "error"); }
    }

    async function open(groupId, groupName) {
        currentGroupId = groupId;
        currentGroupName = groupName;
        document.getElementById("group-conversation-title").textContent = groupName;
        document.getElementById("group-conversation").classList.remove("hidden");
        await loadMessages();
    }

    async function loadMessages() {
        const log = document.getElementById("group-messages");
        log.innerHTML = `<div class="skeleton" style="height:40px;"></div>`;
        try {
            const data = await API.get(`/api/groups/${currentGroupId}/messages?limit=100`);
            log.innerHTML = "";
            for (const m of data.messages) {
                appendMessage(m);
            }
        } catch (e) {
            log.innerHTML = `<div class="empty">Error: ${e.message}</div>`;
        }
    }

    function appendMessage(m) {
        const log = document.getElementById("group-messages");
        const div = document.createElement("div");
        div.className = "chat-line";
        const mine = m.sender === API.username;
        div.style.cssText = (mine ? "text-align:right;" : "") + "margin-bottom:6px;";
        div.innerHTML = `<strong>${m.sender}</strong>: ${m.encrypted ? "🔒 " : ""}${m.body || ""}`;
        log.appendChild(div);
        log.scrollTop = log.scrollHeight;
    }

    async function send() {
        const input = document.getElementById("group-input");
        const text = input.value.trim();
        if (!text || !currentGroupId) return;
        try {
            await API.post(`/api/groups/${currentGroupId}/messages`, {
                body: text, encrypted: false,
            });
            appendMessage({ sender: API.username, body: text, encrypted: false });
            input.value = "";
        } catch (e) { UI.toast("Send failed: " + e.message, "error"); }
    }

    function init() {
        document.getElementById("group-new")?.addEventListener("click", create);
        document.getElementById("group-refresh")?.addEventListener("click", load);
        document.getElementById("group-send")?.addEventListener("click", send);
        document.getElementById("group-input")?.addEventListener("keydown", (e) => {
            if (e.key === "Enter") { e.preventDefault(); send(); }
        });
    }

    function onShow() { load(); }

    return { init, onShow, load, create, open, send };
})();
