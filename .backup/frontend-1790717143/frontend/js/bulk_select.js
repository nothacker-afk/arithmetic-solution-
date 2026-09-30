// Bulk message selection (Phase 74)
const BulkSelect = (() => {
    let active = false;
    const selected = new Set();
    let currentRoom = null;

    function enter(room) {
        active = true;
        currentRoom = room;
        selected.clear();
        _renderBar();
        _decorateMessages();
    }

    function exit() {
        active = false;
        selected.clear();
        currentRoom = null;
        document.getElementById("bulk-bar")?.remove();
        document.querySelectorAll(".msg-wrap").forEach(w => {
            w.classList.remove("bulk-selected");
            const cb = w.querySelector(".bulk-checkbox");
            if (cb) cb.remove();
            const handler = w._bulkClick;
            if (handler) w.removeEventListener("click", handler);
            delete w._bulkClick;
        });
    }

    function _decorateMessages() {
        document.querySelectorAll(".msg-wrap").forEach(w => {
            if (w.querySelector(".bulk-checkbox")) return;
            const mid = parseInt(w.dataset.mid);
            if (!mid) return;

            const cb = document.createElement("input");
            cb.type = "checkbox";
            cb.className = "bulk-checkbox";
            cb.style.cssText = "margin-right:8px;vertical-align:middle;";
            cb.checked = selected.has(mid);
            cb.addEventListener("change", (e) => {
                e.stopPropagation();
                if (cb.checked) selected.add(mid);
                else selected.delete(mid);
                w.classList.toggle("bulk-selected", cb.checked);
                _updateCount();
            });
            w.querySelector(".msg-head")?.prepend(cb);

            const handler = (e) => {
                if (e.target.tagName === "INPUT" || e.target.tagName === "BUTTON") return;
                e.preventDefault();
                cb.checked = !cb.checked;
                cb.dispatchEvent(new Event("change"));
            };
            w._bulkClick = handler;
            w.addEventListener("click", handler);
        });
    }

    function _renderBar() {
        document.getElementById("bulk-bar")?.remove();
        const bar = document.createElement("div");
        bar.id = "bulk-bar";
        bar.className = "bulk-bar";
        bar.innerHTML = `
            <span class="bulk-count">0 selected</span>
            <button class="btn" id="bulk-cancel">Cancel</button>
            <button class="btn btn-danger" id="bulk-delete">Delete</button>
        `;
        document.querySelector(".app-shell")?.appendChild(bar);
        bar.querySelector("#bulk-cancel").addEventListener("click", exit);
        bar.querySelector("#bulk-delete").addEventListener("click", _deleteSelected);
    }

    function _updateCount() {
        const el = document.querySelector(".bulk-count");
        if (el) el.textContent = `${selected.size} selected`;
    }

    async function _deleteSelected() {
        if (!selected.size) { UI.toast("Nothing selected", "warning"); return; }
        if (!confirm(`Delete ${selected.size} message(s)?`)) return;
        try {
            const res = await API.post(`/api/rooms/${currentRoom}/messages/bulk`, {
                action: "delete",
                message_ids: [...selected],
            });
            UI.toast(`Deleted ${res.affected}`, "success");
            exit();
            if (window.Live && Live.reload) Live.reload();
        } catch (e) {
            UI.toast("Delete failed: " + e.message, "error");
        }
    }

    function init() {
        // Add "Select" toggle to the chat action bar
        const btn = document.getElementById("bulk-enter");
        if (btn && !btn._wired) {
            btn._wired = true;
            btn.addEventListener("click", () => {
                if (active) exit();
                else enter(document.getElementById("rt-room")?.value.trim());
            });
        }
    }

    return { init, enter, exit };
})();
