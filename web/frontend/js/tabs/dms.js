const DMs = (() => {
    let currentThreadId = null;
    let currentOther = null;
    let dmKey = null;

    async function deriveKey(passphrase, me, other) {
        const names = [me, other].sort().join(":");
        return window.deriveKey(passphrase, "dm:" + names);
    }

    async function ensureKey() {
        if (dmKey) return dmKey;
        const pass = document.getElementById("dm-passphrase").value;
        if (!pass || !currentOther) return null;
        dmKey = await deriveKey(pass, API.username || "", currentOther);
        return dmKey;
    }

    async function listThreads() {
        const list = document.getElementById("dm-threads");
        if (!API.isLoggedIn()) {
            list.innerHTML = `<div class="empty">Login to use DMs.</div>`;
            return;
        }
        list.innerHTML = `<div class="skeleton" style="height:40px;margin-bottom:6px;"></div>
                          <div class="skeleton" style="height:40px;"></div>`;
        try {
            const data = await API.get("/api/dms/threads");
            if (!data.threads.length) {
                list.innerHTML = `<div class="empty">No conversations yet.</div>`;
                return;
            }
            list.innerHTML = data.threads.map(t => `
                <div class="feed-item" data-tid="${t.id}" style="cursor:pointer;display:flex;justify-content:space-between;align-items:center;">
                    <span><strong>${t.other_username}</strong></span>
                    ${t.unread ? `<span class="badge live">${t.unread}</span>` : ""}
                </div>
            `).join("");
            list.querySelectorAll("[data-tid]").forEach(el => {
                el.addEventListener("click", () => openThread(+el.dataset.tid, el.querySelector("strong").textContent));
            });
        } catch (e) {
            list.innerHTML = `<div class="empty">Error: ${e.message}</div>`;
        }
    }

    async function startThread() {
        const input = document.getElementById("dm-new-user");
        const username = input.value.trim();
        if (!username) return;
        try {
            const data = await API.post("/api/dms/threads", { username });
            input.value = "";
            await listThreads();
            await openThread(data.thread_id, data.other_username);
        } catch (e) {
            UI.toast("Could not start conversation: " + e.message, "error");
        }
    }

    async function openThread(threadId, otherName) {
        currentThreadId = threadId;
        currentOther = otherName;
        dmKey = null;
        document.getElementById("dm-conversation-title").textContent = otherName;
        document.getElementById("dm-conversation").classList.remove("hidden");
        await loadMessages();
    }

    async function loadMessages() {
        const log = document.getElementById("dm-messages");
        log.innerHTML = `<div class="skeleton" style="height:40px;margin-bottom:6px;"></div>
                         <div class="skeleton" style="height:40px;"></div>`;
        try {
            const data = await API.get(`/api/dms/threads/${currentThreadId}?limit=100`);
            const key = await ensureKey();
            log.innerHTML = "";
            for (const m of data.messages) {
                addMessage(m, key, data.participants);
            }
        } catch (e) {
            log.innerHTML = `<div class="empty">Error: ${e.message}</div>`;
        }
    }

    function addMessage(m, key, participants) {
        const log = document.getElementById("dm-messages");
        const div = document.createElement("div");
        div.className = "chat-line";
        const isMine = m.sender === (participants.me || API.username);
        const align = isMine ? "text-align:right;" : "";
        div.style.cssText = align + "margin-bottom:6px;";
        let text = m.body;
        if (m.encrypted) text = key ? "(encrypted)" : "(🔒 enter passphrase)";
        div.innerHTML = `<strong>${m.sender}</strong>: <span class="dm-body">${text}</span>`;
        log.appendChild(div);
        if (m.encrypted && key) {
            decrypt(key, m.body).then(plain => {
                const s = div.querySelector(".dm-body");
                if (s) s.textContent = plain;
            }).catch(() => {});
        }
        log.scrollTop = log.scrollHeight;
    }

    async function send() {
        if (!currentThreadId) return;
        const input = document.getElementById("dm-input");
        const text = input.value.trim();
        if (!text) return;

        const key = await ensureKey();
        if (!key) { UI.toast("Enter a passphrase first", "warning"); return; }

        const ciphertext = await encryptMessage(key, text);
        try {
            await API.post(`/api/dms/threads/${currentThreadId}`, {
                body: ciphertext, encrypted: true,
            });
            const log = document.getElementById("dm-messages");
            const div = document.createElement("div");
            div.className = "chat-line";
            div.style.cssText = "text-align:right;margin-bottom:6px;";
            div.innerHTML = `<strong>${API.username}</strong>: ${text}`;
            log.appendChild(div);
            log.scrollTop = log.scrollHeight;
            input.value = "";
        } catch (e) {
            UI.toast("Send failed: " + e.message, "error");
        }
    }

    function init() {
        document.getElementById("dm-start")?.addEventListener("click", startThread);
        document.getElementById("dm-send")?.addEventListener("click", send);
        document.getElementById("dm-input")?.addEventListener("keydown", (e) => {
            if (e.key === "Enter") { e.preventDefault(); send(); }
        });
        document.getElementById("dm-refresh")?.addEventListener("click", listThreads);
        document.getElementById("dm-passphrase")?.addEventListener("change", () => {
            dmKey = null;
            if (currentThreadId) loadMessages();
        });
    }

    function onShow() { listThreads(); }

    return { init, onShow, listThreads };
})();
