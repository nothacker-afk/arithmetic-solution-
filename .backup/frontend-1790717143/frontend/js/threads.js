// Chat threads (Phase 33)
const Threads = (() => {
    const openThreads = new Set();

    async function loadReplies(room, parentId) {
        return await API.get(`/api/chat/${room}/${parentId}/replies`);
    }

    async function reply(room, parentId, body, encrypted) {
        return await API.post(`/api/chat/${room}`, {
            username: (document.getElementById("rt-user")?.value.trim()) || "guest",
            body, encrypted, parent_id: parentId,
        });
    }

    function renderThreadToggle(container, room, parentId, replyCount = 0) {
        const label = replyCount > 0 ? `🧵 ${replyCount} ${replyCount === 1 ? "reply" : "replies"}` : "🧵 Reply";
        container.innerHTML = `<button class="thread-toggle">${label}</button>`;
        container.querySelector(".thread-toggle").addEventListener("click", async () => {
            if (openThreads.has(parentId)) {
                openThreads.delete(parentId);
                const box = container.parentElement.querySelector(".thread-box");
                if (box) box.remove();
                container.querySelector(".thread-toggle").textContent = label;
                return;
            }
            openThreads.add(parentId);
            container.querySelector(".thread-toggle").textContent = "▾ Replies";
            const box = document.createElement("div");
            box.className = "thread-box";
            box.innerHTML = `<div class="thread-loading skeleton" style="height:32px;"></div>`;
            container.parentElement.appendChild(box);
            try {
                const data = await loadReplies(room, parentId);
                renderBox(box, data.replies, room, parentId);
                updateCount(room, parentId, data.replies.length);
            } catch (e) {
                box.innerHTML = `<div class="muted">Error: ${e.message}</div>`;
            }
        });
    }

    function renderBox(box, replies, room, parentId) {
        const rowsHtml = replies.length
            ? replies.map(r => `
                <div class="thread-reply">
                    <strong>${esc(r.username)}</strong>: ${r.encrypted ? "🔒 " : ""}${esc(r.body || "")}
                </div>`).join("")
            : `<div class="muted" style="font-size:var(--fs-xs);padding:4px 8px;">No replies yet.</div>`;
        box.innerHTML = rowsHtml;
        const bar = document.createElement("div");
        bar.className = "thread-reply-bar";
        bar.innerHTML = `<input class="input" placeholder="Reply…" />
                         <button class="btn btn-primary">Send</button>`;
        box.appendChild(bar);
        const input = bar.querySelector("input");
        const btn = bar.querySelector("button");
        const doSend = async () => {
            const text = input.value.trim();
            if (!text) return;
            try {
                await reply(room, parentId, text, false);
                input.value = "";
                const d2 = await loadReplies(room, parentId);
                renderBox(box, d2.replies, room, parentId);
                updateCount(room, parentId, d2.replies.length);
            } catch (e) { UI.toast("Reply failed: " + e.message, "error"); }
        };
        btn.addEventListener("click", doSend);
        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") { e.preventDefault(); doSend(); }
        });
    }

    function esc(s) {
        return (s ?? "").toString().replace(/[&<>"']/g, c => (
            {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
    }

    function updateCount(room, parentId, count) {
        const msg = document.querySelector(`.msg-wrap[data-mid="${parentId}"]`);
        if (!msg) return;
        const toggle = msg.querySelector(".thread-toggle");
        if (!toggle) return;
        // Only change text if the thread is currently open
        if (openThreads.has(parentId)) {
            toggle.textContent = "▾ Replies";
        } else {
            toggle.textContent = count > 0
                ? `🧵 ${count} ${count === 1 ? "reply" : "replies"}`
                : "🧵 Reply";
        }
    }

    function jumpToThread(parentId) {
        const el = document.querySelector(`.msg-wrap[data-mid="${parentId}"]`);
        if (!el) return;
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        el.style.transition = "background 300ms";
        el.style.background = "var(--accent-soft)";
        setTimeout(() => { el.style.background = ""; }, 900);
        // Ensure thread is open
        if (!openThreads.has(parentId)) {
            el.querySelector(".thread-toggle")?.click();
        }
    }

    return { loadReplies, reply, renderThreadToggle, jumpToThread };
})();
