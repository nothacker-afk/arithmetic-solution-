// Multi-device sync (Phase 67)
const Devices = (() => {
    const KEY = "device.id";
    const LABEL_KEY = "device.label";

    function deviceId() {
        let id = localStorage.getItem(KEY);
        if (!id) {
            id = "dev-" + Math.random().toString(36).slice(2, 12)
                     + "-" + Date.now().toString(36);
            localStorage.setItem(KEY, id);
        }
        return id;
    }

    function deviceLabel() {
        let l = localStorage.getItem(LABEL_KEY);
        if (!l) {
            const ua = navigator.userAgent || "";
            l = /Android/i.test(ua) ? "Android"
              : /iPhone|iPad/i.test(ua) ? "iOS"
              : /Mac/i.test(ua) ? "Mac"
              : /Win/i.test(ua) ? "Windows"
              : "Browser";
            localStorage.setItem(LABEL_KEY, l);
        }
        return l;
    }

    async function register() {
        if (!API.isLoggedIn()) return;
        try {
            await API.post("/api/sync/devices/register", {
                device_id: deviceId(),
                label: deviceLabel(),
                platform: navigator.platform || "web",
            });
        } catch (e) { console.warn("[sync] register failed:", e.message); }
    }

    async function list() {
        const el = document.getElementById("devices-list");
        if (!el) return;
        try {
            const data = await API.get("/api/sync/devices");
            if (!data.devices.length) {
                el.innerHTML = `<div class="empty">No devices registered.</div>`;
                return;
            }
            const myId = deviceId();
            el.innerHTML = data.devices.map(d => `
                <div class="contact-row">
                    <span>💻 <strong>${d.label || d.device_id}</strong>
                        ${d.device_id === myId ? '<span class="badge live">this device</span>' : ""}
                        <div class="muted" style="font-size:var(--fs-xs);">
                            ${d.platform || ""} · last seen ${d.last_seen_at || ""}
                        </div>
                    </span>
                    ${d.device_id !== myId
                        ? `<button class="btn btn-ghost btn-icon"
                                   onclick="Devices.remove('${d.device_id}')">×</button>`
                        : ""}
                </div>
            `).join("");
        } catch (e) {
            el.innerHTML = `<div class="empty">Error: ${e.message}</div>`;
        }
    }

    async function remove(deviceIdToRemove) {
        if (!confirm("Remove this device?")) return;
        try {
            await API.del(`/api/sync/devices/${deviceIdToRemove}`);
            UI.toast("Device removed");
            list();
        } catch (e) { UI.toast("Remove failed: " + e.message, "error"); }
    }

    async function syncReadState(room, messageId) {
        if (!API.isLoggedIn() || !room || !messageId) return;
        try {
            await API.post("/api/sync/read-state", {
                device_id: deviceId(),
                room_id: room,
                last_read_message_id: messageId,
            });
        } catch (e) { /* silent */ }
    }

    function init() {
        // Register on load if logged in
        if (API.isLoggedIn()) register();
        document.getElementById("devices-refresh")?.addEventListener("click", list);
    }

    return { init, register, list, remove, deviceId, deviceLabel, syncReadState };
})();
