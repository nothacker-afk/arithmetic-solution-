// Web Push subscription (Phase 79)
const WebPush = (() => {
    function supported() {
        return "serviceWorker" in navigator
            && "PushManager" in window
            && "Notification" in window;
    }

    function _b64ToUint8(base64) {
        const pad = "=".repeat((4 - (base64.length % 4)) % 4);
        const b64 = (base64 + pad).replace(/-/g, "+").replace(/_/g, "/");
        const raw = atob(b64);
        const arr = new Uint8Array(raw.length);
        for (let i = 0; i < raw.length; i++) arr[i] = raw.charCodeAt(i);
        return arr;
    }

    async function _getVapidKey() {
        const res = await fetch("/api/push/vapid-public-key");
        if (!res.ok) return null;
        const data = await res.json();
        return data.public_key;
    }

    async function subscribe() {
        if (!supported()) {
            UI.toast("Push notifications not supported on this device", "error");
            return false;
        }
        if (!API.isLoggedIn()) {
            UI.toast("Login to enable push notifications", "warning");
            return false;
        }

        const permission = await Notification.requestPermission();
        if (permission !== "granted") {
            UI.toast("Notification permission denied", "warning");
            return false;
        }

        const pubKey = await _getVapidKey();
        if (!pubKey) {
            UI.toast("Push not configured on server", "error");
            return false;
        }

        try {
            const reg = await navigator.serviceWorker.ready;
            const sub = await reg.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: _b64ToUint8(pubKey),
            });
            const json = sub.toJSON();
            await API.post("/api/push/subscribe", {
                endpoint: json.endpoint,
                keys: json.keys,
            });
            UI.toast("Push notifications enabled", "success");
            return true;
        } catch (e) {
            UI.toast("Subscribe failed: " + e.message, "error");
            return false;
        }
    }

    async function unsubscribe() {
        try {
            const reg = await navigator.serviceWorker.ready;
            const sub = await reg.pushManager.getSubscription();
            if (!sub) { UI.toast("Not subscribed", "info"); return; }
            const json = sub.toJSON();
            await API.del("/api/push/subscribe", { endpoint: json.endpoint });
            await sub.unsubscribe();
            UI.toast("Push disabled");
        } catch (e) {
            UI.toast("Unsubscribe failed: " + e.message, "error");
        }
    }

    async function test() {
        try {
            const r = await API.post("/api/push/test", {});
            if (r.sent) UI.toast(`Sent to ${r.sent} device(s)`, "success");
            else UI.toast("No subscriptions or push not configured", "warning");
        } catch (e) {
            UI.toast("Test failed: " + e.message, "error");
        }
    }

    async function _list() {
        const el = document.getElementById("webpush-list");
        if (!el) return;
        try {
            const data = await API.get("/api/push/subscriptions");
            if (!data.subscriptions.length) {
                el.innerHTML = `<div class="empty">No subscribed devices.</div>`;
                return;
            }
            el.innerHTML = data.subscriptions.map(s => `
                <div class="contact-row">
                    <span>🔔 <span class="mono">${s.endpoint_prefix}</span>
                        <div class="muted" style="font-size:var(--fs-xs);">
                            ${s.user_agent || "unknown"} · last used ${s.last_used_at || "never"}
                        </div>
                    </span>
                </div>
            `).join("");
        } catch (e) {
            el.innerHTML = `<div class="empty">Error: ${e.message}</div>`;
        }
    }

    function init() {
        document.getElementById("webpush-enable")?.addEventListener("click", subscribe);
        document.getElementById("webpush-disable")?.addEventListener("click", unsubscribe);
        document.getElementById("webpush-test")?.addEventListener("click", test);
        document.getElementById("webpush-refresh")?.addEventListener("click", _list);
    }

    function onShow() { _list(); }

    return { init, onShow, subscribe, unsubscribe, test, supported };
})();
