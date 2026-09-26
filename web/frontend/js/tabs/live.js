const Live = (() => {
    let socket = null;
    let currentRoom = null;
    let cryptoKey = null;
    const messagesById = {};
    const readsBy = {};  // { last_read_message_id, username }

    function status(msg) {
        const el = document.getElementById("rt-status");
        if (el) el.textContent = msg;
    }

    function esc(s) { return (s ?? "").toString().replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c])); }

    function msgElement(msg) {
        const wrap = document.createElement("div");
        wrap.className = "msg-wrap";
        wrap.dataset.mid = msg.id;
        wrap.innerHTML = `
            <div class="msg-head"><strong>${esc(msg.username)}</strong></div>
            <div class="msg-body"></div>
            <div class="reaction-chips"></div>
            <div class="reaction-picker"></div>
            <div class="thread-slot"></div>`;
        const body = wrap.querySelector(".msg-body");
        applyBody(body, msg);
        // Reactions
        if (window.Reactions) {
            Reactions.renderPicker("chat", msg.id, wrap.querySelector(".reaction-picker"));
            Reactions.renderChips("chat", msg.id, wrap.querySelector(".reaction-chips"));
        }
        // Thread toggle (only top-level)
        if (window.Threads && !msg.parent_id) {
            Threads.renderThreadToggle(
                wrap.querySelector(".thread-slot"),
                currentRoom,
                msg.id,
                msg.reply_count || 0,
            );
        }
        // Message actions menu (Phase 38)
        if (window.MessageActions) {
            const me = (document.getElementById("rt-user")?.value || "").trim();
            const isMine = (msg.username === me);
            MessageActions.attachDots(wrap, {
                canEdit: isMine && !msg.deleted,
                canDelete: isMine && !msg.deleted,
                onEdit: async () => {
                    const newText = prompt("Edit message:", msg.body);
                    if (!newText || newText === msg.body) return;
                    try {
                        const updated = await API.request(
                            `/api/chat/${currentRoom}/${msg.id}`,
                            { method: "PATCH", body: { body: newText, username: msg.username } });
                        msg.body = updated.body;
                        msg.edited_at = updated.edited_at;
                        bodyEl.textContent = newText + "  (edited)";
                    } catch (e) { UI.toast("Edit failed: " + e.message, "error"); }
                },
                onDelete: async () => {
                    if (!confirm("Delete this message?")) return;
                    try {
                        await API.request(
                            `/api/chat/${currentRoom}/${msg.id}?username=${encodeURIComponent(msg.username)}`,
                            { method: "DELETE" });
                        bodyEl.textContent = "(deleted)";
                        bodyEl.classList.add("deleted");
                    } catch (e) { UI.toast("Delete failed: " + e.message, "error"); }
                },
                onViewEdits: () => {
                    MessageActions.showEditHistory(`/api/chat/${currentRoom}/${msg.id}/edits`);
                },
            });
        }
        return wrap;
    }

    async function applyBody(bodyEl, msg) {
        if (msg.kind === "voice" && msg.attachment_id) {
            bodyEl.innerHTML = `
                <div class="voice-player">
                    <audio controls preload="none"></audio>
                    <span class="voice-dur">${msg.duration_ms ? (msg.duration_ms/1000).toFixed(1) + "s" : ""}</span>
                    <button class="transcribe-btn" title="Transcribe">📝</button>
                </div>
                <div class="transcript"></div>`;
            const trBtn = bodyEl.querySelector(".transcribe-btn");
            const trBox = bodyEl.querySelector(".transcript");
            trBtn.addEventListener("click", async () => {
                trBox.textContent = "Transcribing…";
                try {
                    // If clip is encrypted locally, we need to send plaintext
                    const res = await fetch(`${API.base}/api/voice/${msg.attachment_id}`);
                    const buf = await res.arrayBuffer();
                    let audioBytes;
                    if (msg.encrypted && cryptoKey) {
                        const b64 = btoa(String.fromCharCode(...new Uint8Array(buf)));
                        audioBytes = await decryptBytes(cryptoKey, b64);
                    } else {
                        audioBytes = new Uint8Array(buf);
                    }
                    let bin = "";
                    for (const b of audioBytes) bin += String.fromCharCode(b);
                    const audio_b64 = btoa(bin);
                    const out = await API.post("/api/transcribe/upload", {
                        audio_b64, mime: "audio/webm",
                    });
                    trBox.textContent = out.text || "(empty transcript)";
                } catch (e) {
                    trBox.textContent = "⚠ " + e.message;
                }
            });
            const audio = bodyEl.querySelector("audio");
            bodyEl.querySelector(".voice-player").addEventListener("click", async (e) => {
                if (e.target.tagName === "AUDIO") return;
                try {
                    await VoiceRecorder.loadAndPlay(msg.attachment_id, !!msg.encrypted, cryptoKey, audio);
                } catch (err) { UI.toast("Play failed: " + err.message, "error"); }
            }, { once: true });
            if (!msg.encrypted) {
                try { await VoiceRecorder.loadAndPlay(msg.attachment_id, false, null, audio); }
                catch {}
            }
        } else if (msg.encrypted) {
            const key = cryptoKey || await ensureKey();
            if (key) {
                try { bodyEl.textContent = await decrypt(key, msg.body); }
                catch { bodyEl.textContent = "🔒 [decrypt failed]"; }
            } else {
                bodyEl.textContent = "🔒 [encrypted — enter passphrase]";
            }
        } else {
            bodyEl.textContent = msg.body;
        }
    }

    function _myUsername() {
        return (document.getElementById("rt-user")?.value || "").trim();
    }

    function _refreshReadMarkers() {
        // Find the highest message the "reader" marked as read
        const entries = Object.values(readsBy);
        if (!entries.length) return;
        const maxRead = Math.max(...entries.map(e => e.last_read_message_id || 0));
        if (!maxRead) return;
        // Hide all markers first
        document.querySelectorAll(".read-marker").forEach(el => el.remove());
        // Attach to the latest message I sent with id <= maxRead
        let target = null;
        for (const [mid, msg] of Object.entries(messagesById)) {
            if (msg.username === _myUsername() && msg.id <= maxRead) {
                if (!target || msg.id > target.id) target = msg;
            }
        }
        if (!target) return;
        const wrap = document.querySelector(`.msg-wrap[data-mid="${target.id}"]`);
        if (!wrap) return;
        const marker = document.createElement("div");
        marker.className = "read-marker";
        const names = entries.filter(e => e.last_read_message_id >= target.id)
                              .map(e => e.username).filter(Boolean);
        marker.textContent = "✓✓ read by " + (names.join(", ") || "someone");
        wrap.querySelector(".msg-body").appendChild(marker);
    }

    async function loadReads() {
        if (!currentRoom) return;
        try {
            const data = await API.get(`/api/chat/${currentRoom}/reads?since=0`);
            for (const r of data.reads) readsBy[r.username] = r;
            _refreshReadMarkers();
        } catch (e) { /* ignore */ }
    }

    async function markRead(latestId) {
        if (!currentRoom || !latestId) return;
        try { await API.post(`/api/chat/${currentRoom}/read`, { last_message_id: latestId }); }
        catch (e) { /* ignore */ }
    }

    function appendMessage(msg) {
        const log = document.getElementById("rt-chat-log");
        if (!log || messagesById[msg.id]) return;
        messagesById[msg.id] = msg;
        log.appendChild(msgElement(msg));
        log.scrollTop = log.scrollHeight;
        while (log.children.length > 100) {
            const first = log.firstChild;
            if (first.dataset && first.dataset.mid) delete messagesById[first.dataset.mid];
            log.removeChild(first);
        }
    }

    async function setUsers(users) {
        users = users || [];
        if (window.Presence) Presence.renderStrip("rt-avatars", users);
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
        });
        socket.on("user_joined", (d) => { setUsers(d.users); });
        socket.on("user_left", (d) => { setUsers(d.users); });
        socket.on("chat_message", (d) => {
            appendMessage(d);
            if (d.id) markRead(d.id);
        });
        socket.on("screen_share_started", (d) => {
            status((d.username || "peer") + " is sharing their screen…");
            _showScreenBanner(d.sid, d.username);
        });
        socket.on("screen_share_stopped", (d) => {
            status((d.username || "peer") + " stopped sharing.");
            _removeScreenBanner(d.sid);
        });
        socket.on("screen_track_ready", async (d) => {
            // Peer will renegotiate: we handle incoming tracks via ontrack
            status("Receiving screen from " + (d.from_sid || "peer"));
        });
        socket.on("room_read", (d) => {
            if (d.room !== currentRoom) return;
            readsBy[d.username] = d;
            _refreshReadMarkers();
        });
        socket.on("typing", (d) => {
            const el = document.getElementById("rt-typing");
            if (el) el.textContent = d.state === "start" ? d.username + " is typing…" : "";
        });
        socket.on("calc_received", (d) => {
            const feed = document.getElementById("rt-feed");
            if (!feed) return;
            const item = document.createElement("div");
            item.className = "feed-item";
            item.innerHTML = `<strong>${esc(d.username)}</strong>: ${esc(d.expression)} = ${esc(d.result)}`;
            feed.prepend(item);
            while (feed.children.length > 30) feed.removeChild(feed.lastChild);
        });
        return socket;
    }

    async function ensureKey() {
        const e2e = document.getElementById("rt-e2e")?.checked;
        if (!e2e) return null;
        if (cryptoKey) return cryptoKey;
        const pass = document.getElementById("rt-passphrase")?.value;
        if (!pass || !currentRoom) return null;
        cryptoKey = await deriveKey(pass, currentRoom);
        return cryptoKey;
    }

    function join() {
        const room = document.getElementById("rt-room").value.trim();
        const user = document.getElementById("rt-user").value.trim() || "guest";
        if (!room) return status("Room name required");
        messagesByIdClear();
        ensureSocket().emit("join", { room, username: user });
    }
    function leave() {
        if (!socket || !currentRoom) return;
        socket.emit("leave", { room: currentRoom });
        currentRoom = null;
        status("Left room.");
        setUsers([]);
    }
    function messagesByIdClear() {
        for (const k of Object.keys(messagesById)) delete messagesById[k];
        const log = document.getElementById("rt-chat-log");
        if (log) log.innerHTML = "";
    }

    async function sendChat() {
        const input = document.getElementById("rt-chat-input");
        const text = input.value.trim();
        if (!text || !currentRoom) return;
        const user = document.getElementById("rt-user").value.trim() || "guest";
        const e2e = document.getElementById("rt-e2e")?.checked;
        let body = text, encrypted = false;
        if (e2e) {
            const key = await ensureKey();
            if (!key) { UI.toast("Enter a passphrase first", "warning"); return; }
            body = await encryptMessage(key, text);
            encrypted = true;
        }
        try {
            const stored = await API.post(`/api/chat/${currentRoom}`, { username: user, body, encrypted });
            appendMessage({ ...stored, decrypted: text });
            socket.emit("chat_send", { room: currentRoom, username: user, body, encrypted, id: stored.id });
        } catch (e) { UI.toast("Send failed: " + e.message, "error"); }
        input.value = "";
    }

    async function sendVoice() {
        if (!currentRoom) return;
        const btn = document.getElementById("rt-mic");
        if (!VoiceRecorder.isRecording()) {
            try {
                await VoiceRecorder.start();
                btn.classList.add("recording");
                btn.textContent = "⏹ Stop";
                status("Recording…");
            } catch (e) { UI.toast("Mic error: " + e.message, "error"); }
            return;
        }
        try {
            const { blob, durationMs } = await VoiceRecorder.stop();
            btn.classList.remove("recording");
            btn.textContent = "🎤 Voice";
            status("Uploading…");
            const key = await ensureKey();
            const data = await VoiceRecorder.upload(blob, durationMs, key);
            const user = document.getElementById("rt-user").value.trim() || "guest";
            const stored = await API.post(`/api/chat/${currentRoom}`, {
                username: user, body: "", encrypted: !!key,
                kind: "voice", attachment_id: data.id,
            });
            // Optimistic
            const optimistic = { ...stored, kind: "voice",
                                 attachment_id: data.id, duration_ms: durationMs,
                                 encrypted: !!key };
            appendMessage(optimistic);
            socket.emit("chat_send", { room: currentRoom, username: user,
                                       body: "", encrypted: !!key,
                                       id: stored.id });
            status("Sent voice clip.");
        } catch (e) {
            UI.toast("Voice send failed: " + e.message, "error");
            status("Error.");
        }
    }

    async function loadHistory() {
        if (!currentRoom) return;
        const log = document.getElementById("rt-chat-log");
        if (!log) return;
        log.innerHTML = "";
        for (const k of Object.keys(messagesById)) delete messagesById[k];
        try {
            const data = await API.get(`/api/chat/${currentRoom}?limit=100`);
            // Load reactions in one batch
            if (window.Reactions && data.messages.length) {
                const ids = data.messages.map(m => m.id);
                await Reactions.load("chat", ids);
            }
            for (const m of data.messages) appendMessage(m);
            if (data.messages.length) {
                markRead(data.messages[data.messages.length - 1].id);
            }
            loadReads();
        } catch (e) { console.warn(e); }
    }

    let screenStream = null;
    const screenTracks = {};  // peer_sid -> MediaStream

    async function startScreenShare() {
        if (!currentRoom) { status("Join a room first"); return; }
        if (!navigator.mediaDevices || !navigator.mediaDevices.getDisplayMedia) {
            UI.toast("Screen sharing not supported", "error");
            return;
        }
        try {
            screenStream = await navigator.mediaDevices.getDisplayMedia({
                video: true, audio: false,
            });
        } catch (e) {
            UI.toast("Screen share denied: " + e.message, "error");
            return;
        }

        // For each existing peer connection, add the screen track
        const user = document.getElementById("rt-user").value.trim() || "guest";
        ensureSocket().emit("screen_share_start", { room: currentRoom, username: user });

        for (const [sid, pc] of Object.entries(window._rtcPcs || {})) {
            try {
                const track = screenStream.getVideoTracks()[0];
                pc.addTrack(track, screenStream);
                socket.emit("screen_track_ready", { target_sid: sid });
            } catch (e) { console.warn("addTrack failed for", sid, e); }
        }

        // Track ended by user
        screenStream.getVideoTracks()[0].onended = stopScreenShare;

        const btn = document.getElementById("rt-screen");
        if (btn) { btn.textContent = "⏹ Stop share"; btn.classList.add("recording"); }
        status("Sharing screen…");
    }

    function stopScreenShare() {
        if (screenStream) {
            screenStream.getTracks().forEach(t => t.stop());
            screenStream = null;
        }
        const user = document.getElementById("rt-user")?.value.trim() || "guest";
        if (socket && currentRoom) {
            socket.emit("screen_share_stop", { room: currentRoom, username: user });
        }
        const btn = document.getElementById("rt-screen");
        if (btn) { btn.textContent = "📺 Share"; btn.classList.remove("recording"); }
        status("Screen share stopped.");
    }

    function init() {
        document.getElementById("rt-join")?.addEventListener("click", join);
        document.getElementById("rt-leave")?.addEventListener("click", leave);
        document.getElementById("rt-send")?.addEventListener("click", sendChat);
        document.getElementById("rt-mic")?.addEventListener("click", sendVoice);
        document.getElementById("rt-screen")?.addEventListener("click", () => {
            if (screenStream) stopScreenShare(); else startScreenShare();
        });
        document.getElementById("rt-chat-input")?.addEventListener("keydown", (e) => {
            if (e.key === "Enter") { e.preventDefault(); sendChat(); }
        });
        document.getElementById("rt-e2e")?.addEventListener("change", (e) => {
            const p = document.getElementById("rt-passphrase");
            if (p) p.style.display = e.target.checked ? "block" : "none";
        });
        document.getElementById("rt-export-md")?.addEventListener("click", () => {
            if (currentRoom) ExportUI.download("room", currentRoom, "md", "chat");
        });
        document.getElementById("rt-export-html")?.addEventListener("click", () => {
            if (currentRoom) ExportUI.download("room", currentRoom, "html", "chat");
        });
    }

    function _showScreenBanner(sid, username) {
        let banner = document.getElementById("screen-banner-" + sid);
        if (!banner) {
            banner = document.createElement("div");
            banner.id = "screen-banner-" + sid;
            banner.className = "screen-banner";
            banner.innerHTML = `📺 <strong>${username}</strong> is sharing a screen`;
            const videos = document.getElementById("rt-videos");
            (videos || document.querySelector(".tab-panel.active")).appendChild(banner);
        }
    }

    function _removeScreenBanner(sid) {
        document.getElementById("screen-banner-" + sid)?.remove();
    }

    function onShow() {}

    return { init, onShow };
})();
