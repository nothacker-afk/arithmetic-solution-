// Wiki comments (Phase 68)
const WikiComments = (() => {
    let currentPageId = null;

    async function open(pageId, pageTitle) {
        currentPageId = pageId;
        const body = document.createElement("div");
        body.innerHTML = `
            <div id="wc-list" style="max-height:50vh;overflow-y:auto;"></div>
            <hr style="border:none;border-top:1px solid var(--border);margin:12px 0;" />
            <div class="field-row">
                <input id="wc-input" class="input" placeholder="Write a comment…" />
                <button id="wc-send" class="btn btn-primary" style="flex:0 0 auto;">Post</button>
            </div>`;
        UI.modal({
            title: `Comments — ${pageTitle}`,
            body,
            actions: [{ label: "Close", kind: "primary" }],
        });
        document.getElementById("wc-send").addEventListener("click", post);
        document.getElementById("wc-input").addEventListener("keydown", (e) => {
            if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); post(); }
        });
        await load();
    }

    async function load() {
        const list = document.getElementById("wc-list");
        list.innerHTML = `<div class="skeleton" style="height:40px;"></div>`;
        try {
            const data = await API.get(`/api/wiki/${currentPageId}/comments`);
            if (!data.comments.length) {
                list.innerHTML = `<div class="empty">No comments yet.</div>`;
                return;
            }
            list.innerHTML = data.comments.map(c => renderComment(c)).join("");
        } catch (e) {
            list.innerHTML = `<div class="empty">Error: ${e.message}</div>`;
        }
    }

    function renderComment(c) {
        const replies = (c.replies || []).map(r => `
            <div class="wc-reply">
                <strong>${escape(r.username)}</strong>: ${escape(r.body)}
                ${r.edited_at ? ' <span class="muted">(edited)</span>' : ""}
            </div>
        `).join("");
        return `
            <div class="wc-comment">
                <div><strong>${escape(c.username)}</strong>
                    <span class="muted" style="font-size:var(--fs-xs);">${c.created_at}</span>
                    ${c.edited_at ? ' <span class="muted">(edited)</span>' : ""}</div>
                <div>${escape(c.body)}</div>
                <div class="mt-2" style="margin-left:20px;">${replies}</div>
                <button class="btn btn-ghost" style="font-size:var(--fs-xs);"
                        onclick="WikiComments.replyTo(${c.id})">Reply</button>
            </div>`;
    }

    async function post(parentId = null) {
        const input = document.getElementById("wc-input");
        const body = input.value.trim();
        if (!body) return;
        try {
            await API.post(`/api/wiki/${currentPageId}/comments`,
                { body, parent_id: parentId });
            input.value = "";
            await load();
        } catch (e) { UI.toast("Post failed: " + e.message, "error"); }
    }

    function replyTo(parentId) {
        const existing = document.getElementById("wc-reply-to");
        if (existing) existing.remove();
        const input = document.getElementById("wc-input");
        const bar = document.createElement("div");
        bar.id = "wc-reply-to";
        bar.className = "muted";
        bar.style.cssText = "font-size:var(--fs-xs);margin-bottom:4px;";
        bar.innerHTML = `Replying to comment #${parentId} ·
            <a href="#" onclick="event.preventDefault();this.parentElement.remove();">cancel</a>`;
        input.parentElement.parentElement.insertBefore(bar, input.parentElement);
        input.dataset.parentId = parentId;
        input.focus();
    }

    function escape(s) {
        return (s ?? "").toString().replace(/[&<>"']/g, c =>
            ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
    }

    // Expose for the room wiki modal
    window.WikiComments = { open };
    return { open };
})();
