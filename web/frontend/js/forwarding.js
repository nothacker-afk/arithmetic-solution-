// Message forwarding (Phase 86)
const Forward = (() => {
    function picker(kind, messageId) {
        const body = document.createElement("div");
        body.innerHTML = `
            <div class="field"><label>Forward to</label>
                <select id="fwd-dest" class="select">
                    <option value="chat">Room (type name below)</option>
                    <option value="dm">Direct message (thread id)</option>
                    <option value="group">Group (group id)</option>
                </select>
            </div>
            <div class="field"><label>Destination</label>
                <input id="fwd-target" class="input" placeholder="room name or numeric id" />
            </div>
            <div class="field"><label>Optional note</label>
                <input id="fwd-note" class="input" placeholder="FYI…" maxlength="300" />
            </div>
            <button id="fwd-go" class="btn btn-primary">Forward</button>
            <div id="fwd-status" class="mt-4"></div>`;
        UI.modal({
            title: "Forward message",
            body,
            actions: [{ label: "Close" }],
        });
        body.querySelector("#fwd-go").addEventListener("click", async () => {
            const status = body.querySelector("#fwd-status");
            const destKind = body.querySelector("#fwd-dest").value;
            const rawTarget = body.querySelector("#fwd-target").value.trim();
            const note = body.querySelector("#fwd-note").value.trim();
            if (!rawTarget) { status.textContent = "Enter a destination."; return; }

            const destId = destKind === "chat" ? rawTarget : parseInt(rawTarget, 10);
            if (destKind !== "chat" && !Number.isInteger(destId)) {
                status.textContent = "Destination must be a numeric id for DMs/groups.";
                return;
            }
            status.textContent = "Forwarding…";
            try {
                const data = await API.post("/api/forward", {
                    source_kind: kind,
                    source_id: messageId,
                    dest_kind: destKind,
                    dest_id: destId,
                    note,
                });
                status.textContent = `✅ Forwarded as message ${data.new_message_id}`;
            } catch (e) {
                status.textContent = "❌ " + e.message;
            }
        });
    }
    return { picker };
})();
