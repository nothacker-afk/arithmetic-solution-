const DMs = (() => {
    let currentThreadId = null;
    let currentOther = null;
    let dmKey = null;
    let participants = { me: "", other: "" };
    const messagesById = {};



    // ---- Phase 37: presence over WebSocket ----
    let dmSocket = null;
    let myUserId = null;
    function parseUserId() {
        if (!API.token) return null;
        try {
            return parseInt(JSON.parse(atob(API.token.split(".")[1])).sub, 10);
        } catch { return null; }
    }

    function ensureDmSocket() {
        if (dmSocket) return dmSocket;
        if (typeof io === "undefined") return null;
        myUserId = parseUserId();
        dmSocket = io(API.base || undefined);
        dmSocket.on("connect", () => {
            if (myUserId) dmSocket.emit("dm_join", { user_id: myUserId });
        });
        dmSocket.on("dm_typing", (d) => {
            if (d.thread_id !== currentThreadId) return;
            const el = document.getElementById("dm-typing");
            if (!el) return;
            el.textContent = d.state === "start" ? d.username + " is typing…" : "";
        });
        dmSocket.on("dm_read", (d) => {
            if (d.thread_id !== currentThreadId) return;
            // Mark all my messages as read visually
            document.querySelectorAll(".msg-wrap.mine .read-tag").forEach(t => {
                t.textContent = "✓✓ read";
            });
        });
        return dmSocket;
    }

    let typingTimer = null;
    function onTyping() {
        const s = ensureDmSocket();
        if (!s || !currentThreadId) return;
        s.emit("dm_typing_start", {
            thread_id: currentThreadId,
            recipient_id: otherUserId || null,
            username: API.username,
        });
        clearTimeout(typingTimer);
        typingTimer = setTimeout(() => {
            s.emit("dm_typing_stop", {
                thread_id: currentThreadId,
                recipient_id: otherUserId || null,
                username: API.username,
            });
        }, 1200);
    }

    let otherUserId = null;

    async function deriveKeyDm(passphrase, me, other) {
        const names = [me, other].sort().join(":");
        return window.deriveKey(passphrase, "dm:" + names);
    }

    async function ensureKey() {
        if (dmKey) return dmKey;
        const pass = document.getElementById("dm-passphrase").value;
        if (!pass || !currentOther) return null;
        dmKey = await deriveKeyDm(pass, API.username || "", currentOther);
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
        for (const k of Object.keys(messagesById)) delete messagesById[k];
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
            participants = data.participants;
            otherUserId = data.other_user_id || null;
            const key = await ensureKey();
            log.innerHTML = "";
            if (window.Reactions && data.messages.length) {
                await Reactions.load("dm", data.messages.map(m => m.id));
            }
            for (const m of data.messages) appendMessage(m, key);
        } catch (e) {
            log.innerHTML = `<div class="empty">Error: ${e.message}</div>`;
        }
    }

    async function appendMessage(m, key) {
        const log = document.getElementById("dm-messages");
        if (messagesById[m.id]) return;
        messagesById[m.id] = m;
        const isMine = (m.sender || m.username) === (participants.me || API.username);
        const wrap = document.createElement("div");
        wrap.className = "msg-wrap";
        wrap.dataset.mid = m.id;
        wrap.style.cssText = isMine ? "text-align:right;" : "";
        wrap.innerHTML = `
            <div class="msg-head"><strong>${m.sender || m.username}</strong></div>
            <div class="msg-body"></div>
            <div class="reaction-chips" style="${isMine ? "justify-content:flex-end;" : ""}"></div>
            <div class="reaction-picker" style="${isMine ? "margin-left:auto;" : ""}"></div>`;
        const body = wrap.querySelector(".msg-body");

        if (m.kind === "voice" && m.attachment_id) {
            body.innerHTML = `<div class="voice-player" style="${isMine ? "margin-left:auto;" : ""}">
                <audio controls preload="none"></audio>
                <span class="voice-dur">${m.duration_ms ? (m.duration_ms/1000).toFixed(1) + "s" : ""}</span>
            </div>`;
            const audio = body.querySelector("audio");
            body.querySelector(".voice-player").addEventListener("click", async (e) => {
                if (e.target.tagName === "AUDIO") return;
                try { await VoiceRecorder.loadAndPlay(m.attachment_id, !!m.encrypted, key, audio); }
                catch (err) { UI.toast("Play failed: " + err.message, "error"); }
            }, { once: true });
        } else if (m.encrypted) {
            if (key) {
                try { body.textContent = await decrypt(key, m.body); }
                catch { body.textContent = "🔒 [decrypt failed]"; }
            } else {
                body.textContent = "🔒 [encrypted — enter passphrase]";
            }
        } else {
            body.textContent = m.body;
        }

        // Read tag (only on my own messages)
        if (isMine) {
            const tag = document.createElement("span");
            tag.className = "read-tag";
            tag.textContent = m.read_at ? "✓✓ read" : "✓ sent";
            wrap.querySelector(".msg-head").appendChild(tag);
        }

        if (window.Reactions) {
            Reactions.renderPicker("dm", m.id, wrap.querySelector(".reaction-picker"));
            Reactions.renderChips("dm", m.id, wrap.querySelector(".reaction-chips"));
        }
        if (window.MessageActions && isMine) {
            MessageActions.attachDots(wrap, {
                canEdit: !m.deleted,
                canDelete: !m.deleted,
                onEdit: async () => {
                    const newText = prompt("Edit message:", m.body);
                    if (!newText || newText === m.body) return;
                    try {
                        const upd = await API.request(
                            `/api/dms/threads/${currentThreadId}/messages/${m.id}`,
                            { method: "PATCH", body: { body: newText } });
                        body.textContent = upd.body + "  (edited)";
                    } catch (e) { UI.toast("Edit failed: " + e.message, "error"); }
                },
                onDelete: async () => {
                    if (!confirm("Delete this DM?")) return;
                    try {
                        await API.request(
                            `/api/dms/threads/${currentThreadId}/messages/${m.id}`,
                            { method: "DELETE" });
                        body.textContent = "(deleted)";
                        body.classList.add("deleted");
                    } catch (e) { UI.toast("Delete failed: " + e.message, "error"); }
                },
                onViewEdits: () => {
                    MessageActions.showEditHistory(
                        `/api/dms/threads/${currentThreadId}/messages/${m.id}/edits`);
                },
            });
        }
        log.appendChild(wrap);
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
            const stored = await API.post(`/api/dms/threads/${currentThreadId}`, {
                body: ciphertext, encrypted: true,
            });
            await appendMessage({ ...stored, encrypted: true, body: ciphertext,
                                  sender: API.username }, key);
            input.value = "";
        } catch (e) {
            UI.toast("Send failed: " + e.message, "error");
        }
    }

    async function sendVoiceDm() {
        if (!currentThreadId) return;
        const btn = document.getElementById("dm-mic");
        if (!VoiceRecorder.isRecording()) {
            try {
                await VoiceRecorder.start();
                btn.classList.add("recording");
                btn.textContent = "⏹";
            } catch (e) { UI.toast("Mic error: " + e.message, "error"); }
            return;
        }
        try {
            const { blob, durationMs } = await VoiceRecorder.stop();
            btn.classList.remove("recording");
            btn.textContent = "🎤";
            const key = await ensureKey();
            const data = await VoiceRecorder.upload(blob, durationMs, key);
            await API.post(`/api/dms/threads/${currentThreadId}`, {
                body: "", encrypted: !!key, kind: "voice", attachment_id: data.id,
            });
            await appendMessage({
                id: Date.now(), sender: API.username, body: "", encrypted: !!key,
                kind: "voice", attachment_id: data.id, duration_ms: durationMs,
            }, key);
        } catch (e) {
            UI.toast("Voice DM failed: " + e.message, "error");
        }
    }

    function init() {
        document.getElementById("dm-start")?.addEventListener("click", startThread);
        document.getElementById("dm-send")?.addEventListener("click", send);
        document.getElementById("dm-input")?.addEventListener("keydown", (e) => {
            if (e.key === "Enter") { e.preventDefault(); send(); }
        });
        document.getElementById("dm-input")?.addEventListener("input", onTyping);
        document.getElementById("dm-mic")?.addEventListener("click", sendVoiceDm);
        document.getElementById("dm-refresh")?.addEventListener("click", listThreads);
        document.getElementById("dm-passphrase")?.addEventListener("change", () => {
            dmKey = null;
            if (currentThreadId) loadMessages();
        });
        document.getElementById("dm-export-md")?.addEventListener("click", () => {
            if (currentThreadId) ExportUI.download("dm", currentThreadId, "md", "dm");
        });
        document.getElementById("dm-export-html")?.addEventListener("click", () => {
            if (currentThreadId) ExportUI.download("dm", currentThreadId, "html", "dm");
        });
    }

    function onShow() { ensureDmSocket(); listThreads(); }

    return { init, onShow, listThreads };
})();
