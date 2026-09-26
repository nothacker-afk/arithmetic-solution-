// Offline-first layer using IndexedDB (Phase 28)
//
// Caches:
//   - recent calculations for offline viewing
//   - pending requests queued when offline
//   - user preferences
//
// Auto-flushes the queue when the connection returns.
const Offline = (() => {
    const DB_NAME = "arith-offline";
    const DB_VERSION = 1;
    const STORES = { calcs: "calcs", queue: "queue", prefs: "prefs" };
    let _db = null;

    function supported() {
        return typeof indexedDB !== "undefined";
    }

    function open() {
        if (_db) return Promise.resolve(_db);
        if (!supported()) return Promise.reject(new Error("IndexedDB unavailable"));
        return new Promise((resolve, reject) => {
            const req = indexedDB.open(DB_NAME, DB_VERSION);
            req.onupgradeneeded = (e) => {
                const db = e.target.result;
                if (!db.objectStoreNames.contains(STORES.calcs)) {
                    db.createObjectStore(STORES.calcs, { keyPath: "id", autoIncrement: true });
                }
                if (!db.objectStoreNames.contains(STORES.queue)) {
                    db.createObjectStore(STORES.queue, { keyPath: "id", autoIncrement: true });
                }
                if (!db.objectStoreNames.contains(STORES.prefs)) {
                    db.createObjectStore(STORES.prefs, { keyPath: "k" });
                }
            };
            req.onsuccess = () => { _db = req.result; resolve(_db); };
            req.onerror = () => reject(req.error);
        });
    }

    async function _tx(store, mode, fn) {
        const db = await open();
        return new Promise((resolve, reject) => {
            const tx = db.transaction(store, mode);
            const s = tx.objectStore(store);
            const req = fn(s);
            tx.oncomplete = () => resolve(req ? req.result : undefined);
            tx.onerror = () => reject(tx.error);
        });
    }

    // ---- Calculations cache ----
    async function cacheCalc(entry) {
        if (!supported()) return;
        try {
            await _tx(STORES.calcs, "readwrite", (s) => s.add({
                ...entry,
                cachedAt: Date.now(),
            }));
            // Keep only last 200
            const all = await listCalcs();
            if (all.length > 200) {
                const excess = all.slice(0, all.length - 200);
                for (const e of excess) {
                    await _tx(STORES.calcs, "readwrite", (s) => s.delete(e.id));
                }
            }
        } catch (e) { console.warn("[offline] cacheCalc", e); }
    }

    async function listCalcs(limit = 50) {
        if (!supported()) return [];
        try {
            const all = await _tx(STORES.calcs, "readonly", (s) => s.getAll());
            return all.sort((a, b) => b.cachedAt - a.cachedAt).slice(0, limit);
        } catch { return []; }
    }

    async function clearCalcs() {
        if (!supported()) return;
        await _tx(STORES.calcs, "readwrite", (s) => s.clear());
    }

    // ---- Request queue ----
    async function enqueue(req) {
        if (!supported()) return;
        await _tx(STORES.queue, "readwrite", (s) => s.add({
            ...req, queuedAt: Date.now(),
        }));
        UI.toast && UI.toast("Saved offline — will retry when online", "warning");
        updateBadge();
    }

    async function listQueue() {
        if (!supported()) return [];
        try {
            return await _tx(STORES.queue, "readonly", (s) => s.getAll());
        } catch { return []; }
    }

    async function flushQueue() {
        const items = await listQueue();
        if (!items.length) return;
        let ok = 0;
        for (const item of items) {
            try {
                await API.request(item.path, {
                    method: item.method,
                    body: item.body,
                });
                await _tx(STORES.queue, "readwrite", (s) => s.delete(item.id));
                ok++;
            } catch (e) {
                console.warn("[offline] flush failed for", item.path, e);
                break; // stop on first failure; retry next time
            }
        }
        if (ok) {
            UI.toast && UI.toast(`Synced ${ok} queued action(s)`, "success");
            updateBadge();
        }
    }

    // ---- Preferences ----
    async function setPref(k, v) {
        if (!supported()) return;
        await _tx(STORES.prefs, "readwrite", (s) => s.put({ k, v }));
    }
    async function getPref(k) {
        if (!supported()) return null;
        try {
            const row = await _tx(STORES.prefs, "readonly", (s) => s.get(k));
            return row ? row.v : null;
        } catch { return null; }
    }

    // ---- Online/offline handling ----
    function updateBadge() {
        let badge = document.getElementById("offline-badge");
        if (!badge) {
            badge = document.createElement("span");
            badge.id = "offline-badge";
            badge.className = "badge off";
            badge.style.cssText = "margin-left:6px;font-size:10px;";
            document.querySelector(".header-actions")?.prepend(badge);
        }
        listQueue().then(q => {
            if (!navigator.onLine) {
                badge.textContent = "offline" + (q.length ? ` (${q.length})` : "");
                badge.className = "badge off";
                badge.style.display = "";
            } else if (q.length) {
                badge.textContent = `pending ${q.length}`;
                badge.className = "badge";
                badge.style.display = "";
            } else {
                badge.style.display = "none";
            }
        });
    }

    function init() {
        if (!supported()) return;
        window.addEventListener("online", () => { UI.toast("Back online", "success"); flushQueue(); updateBadge(); });
        window.addEventListener("offline", () => { UI.toast("You're offline", "warning"); updateBadge(); });
        updateBadge();
        // Intercept API failures globally
        const originalRequest = API.request.bind(API);
        API.request = async function (path, opts = {}) {
            try {
                return await originalRequest(path, opts);
            } catch (e) {
                const method = (opts.method || "GET").toUpperCase();
                // Queue writes when offline
                if (!navigator.onLine && method !== "GET") {
                    await enqueue({ path, method, body: opts.body });
                    throw new Error("Offline — request queued");
                }
                throw e;
            }
        };
    }

    return { init, cacheCalc, listCalcs, clearCalcs,
             enqueue, flushQueue, setPref, getPref,
             supported, updateBadge };
})();
