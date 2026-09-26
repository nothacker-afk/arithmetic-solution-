// SSE client — mirrors WebSocket events via /api/events/stream (Phase 63)
const SSEClient = (() => {
    const conns = {};  // channel -> EventSource

    function subscribe(channel, handlers) {
        if (conns[channel]) return conns[channel];
        const url = `/api/events/stream?channel=${encodeURIComponent(channel)}`;
        const es = new EventSource(url);
        es.onopen = () => console.log("[SSE] connected:", channel);
        es.onerror = () => console.warn("[SSE] error on", channel);
        for (const [eventName, fn] of Object.entries(handlers || {})) {
            es.addEventListener(eventName, (evt) => {
                try { fn(JSON.parse(evt.data)); }
                catch (e) { console.warn("[SSE] bad payload", e); }
            });
        }
        conns[channel] = es;
        return es;
    }

    function unsubscribe(channel) {
        const es = conns[channel];
        if (es) { es.close(); delete conns[channel]; }
    }

    function supported() { return typeof EventSource !== "undefined"; }

    // If WebSocket fails, fall back
    function installFallback() {
        if (!supported()) return;
        window.addEventListener("load", () => {
            // After 5s, if socket.io is not connected, subscribe via SSE
            setTimeout(() => {
                try {
                    if (window.io) {
                        // Check if we have an active socket in the live module
                        const liveSocket = window.Live && Live.socket;
                        if (!liveSocket || !liveSocket.connected) {
                            console.log("[SSE] WebSocket not connected, engaging fallback");
                            const room = document.getElementById("rt-room")?.value.trim();
                            if (room) {
                                subscribe(`room:${room}`, {
                                    chat_message: (d) => {
                                        if (window.Live && Live._sseAppend) Live._sseAppend(d);
                                    },
                                });
                            }
                        }
                    }
                } catch (e) { /* ignore */ }
            }, 5000);
        });
    }

    return { subscribe, unsubscribe, supported, installFallback };
})();
