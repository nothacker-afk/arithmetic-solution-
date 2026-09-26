const Live = (() => {
    let socket = null;
    let currentRoom = null;
    let cryptoKey = null;

    function status(msg) {
        const el = document.getElementById("rt-status");
        if (el) el.textContent = msg;
    }

    function addChat(msg) {
        const log = document.getElementById("rt-chat-log");
        const line = document.createElement("div");
        line.className = "chat-line" + (msg.username === "system" ? " system" : "");
        const who = msg.username === "system" ? "" : `<strong>${msg.username}</strong>: `;
        const lock = msg.encrypted ? "🔒 " : "";
        line.innerHTML = who + lock + (msg.decrypted || msg.body || "");
        log.appendChild(line);
        log.scrollTop = log.scrollHeight;
        while (log.children.length > 100) log.removeChild(log.firstChild);
    }

    function ensureSocket() {
        if (socket) return socket;
        socket = io(API.base || undefined);
        socket.on("connect", () => status("Connected."));
        socket.on("disconnect", () => status("Disconnected."));
        socket.on("joined", (d) => {
            currentRoom = d.room;
            status("Joined: " + d.room);
            setUsers(d.users);
            loadHistory();
            refreshFiles();
        });
        socket.on("user_joined", (d) => { addChat({ username: "system", body: d.username + " joined" }); setUsers(d.users); });
        socket.on("user_left", (d) => { addChat({ username: "system", body: d.username + " left" }); setUsers(d.users); });
        socket.on("chat_message", async (d) => {
            if (d.encrypted) {
                const key = await ensureKey();
                if (!key) return addChat({ username: d.username, body: "[encrypted]", encrypted: true });
                try { addChat({ username: d.username, body: await decrypt(key, d.body), encrypted: true }); }
                catch { addChat({ username: d.username, body: "[decrypt failed]", encrypted: true }); }
            } else addChat(d);
        });
        socket.on("typing", (d) => {
            const el = document.getElementById("rt-typing");
            if (el) el.textContent = d.state === "start" ? d.username + " is typing…" : "";
        });
        socket.on("calc_received", (d) => {
            const feed = document.getElementById("rt-feed");
            const item = document.createElement("div");
            item.className = "feed-item";
            item.innerHTML = `<strong>${d.username}</strong>: ${d.expression} = ${d.result}`;
            feed.prepend(item);
            while (feed.children.length > 30) feed.removeChild(feed.lastChild);
        });
        return socket;
    }

    function setUsers(users) {
        users = users || [];
        if (window.Presence) {
            Presence.renderStrip("rt-avatars", users);
        }
        const el = document.getElementById("rt-users");
        if (el) el.textContent = "";
    }

    async function ensureKey() {
        const e2e = document.getElementById("rt-e2e")?.checked;
        if (!e2e) return null;
        if (cryptoKey) return cryptoKey;
        const pass = document.getElementById("rt-passphrase").value;
        if (!pass || !currentRoom) return null;
        cryptoKey = await deriveKey(pass, currentRoom);
        return cryptoKey;
    }

    function join() {
        const room = document.getElementById("rt-room").value.trim();
        const user = document.getElementById("rt-user").value.trim() || "guest";
        if (!room) return status("Room name required");
        ensureSocket().emit("join", { room, username: user });
    }
    function leave() {
        if (!socket || !currentRoom) return;
        socket.emit("leave", { room: currentRoom });
        currentRoom = null;
        status("Left room.");
        setUsers([]);
    }

    async function sendChat() {
        const input = document.getElementById("rt-chat-input");
        const text = input.value.trim();
        if (!text || !currentRoom) return;
        const user = document.getElementById("rt-user").value.trim() || "guest";
        const e2e = document.getElementById("rt-e2e").checked;
        let body = text, encrypted = false;
        if (e2e) {
            const key = await ensureKey();
            if (!key) { UI.toast("Enter a passphrase first", "warning"); return; }
            body = await encryptMessage(key, text);
            encrypted = true;
        }
        try {
            const stored = await API.post(`/api/chat/${currentRoom}`, { username: user, body, encrypted });
            addChat({ username: user, body: text, decrypted: text, encrypted });
            socket.emit("chat_send", { room: currentRoom, username: user, body, encrypted, id: stored.id });
        } catch (e) { UI.toast("Send failed: " + e.message, "error"); }
        input.value = "";
    }

    async function loadHistory() {
        if (!currentRoom) return;
        const log = document.getElementById("rt-chat-log");
        log.innerHTML = "";
        try {
            const data = await API.get(`/api/chat/${currentRoom}?limit=50`);
            const key = await ensureKey();
            for (const m of data.messages) {
                if (m.encrypted && key) {
                    try { addChat({ username: m.username, body: await decrypt(key, m.body), encrypted: true }); }
                    catch { addChat({ username: m.username, body: "[encrypted]", encrypted: true }); }
                } else addChat(m);
            }
        } catch (e) { console.warn(e); }
    }

    async function refreshFiles() {
        const list = document.getElementById("rt-file-list");
        if (!list) return;
        try {
            const data = await API.get(`/api/files/${currentRoom}`);
            if (!data.files.length) { list.innerHTML = `<div class="empty">No files yet.</div>`; return; }
            list.innerHTML = data.files.map(f => `
                <div class="feed-item" style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
                    <span>🔒 <strong>${f.filename}</strong> <span class="muted">(${fmtBytes(f.size_bytes)})</span></span>
                    <button class="btn btn-ghost btn-icon" data-dl="${f.id}" data-name="${f.filename}">↓</button>
                </div>
            `).join("");
        } catch (e) { console.warn(e); }
    }

    function fmtBytes(n) {
        if (n < 1024) return n + " B";
        if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
        return (n / 1024 / 1024).toFixed(2) + " MB";
    }

    function init() {
        document.getElementById("rt-join")?.addEventListener("click", join);
        document.getElementById("rt-leave")?.addEventListener("click", leave);
        document.getElementById("rt-send")?.addEventListener("click", sendChat);
        document.getElementById("rt-chat-input")?.addEventListener("keydown", (e) => {
            if (e.key === "Enter") { e.preventDefault(); sendChat(); }
        });
        document.getElementById("rt-e2e")?.addEventListener("change", (e) => {
            document.getElementById("rt-passphrase").style.display = e.target.checked ? "block" : "none";
        });
    }

    function onShow() {
        if (currentRoom) refreshFiles();
    }

    return { init, onShow };
})();
