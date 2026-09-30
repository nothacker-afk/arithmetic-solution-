// API wrapper — auth, JSON, error handling
const API = {
    base: window.location.origin.startsWith("http") ? window.location.origin : "",
    token: localStorage.getItem("token") || null,
    username: localStorage.getItem("username") || null,

    headers(extra = {}) {
        const h = { "Content-Type": "application/json", ...extra };
        if (this.token) h["Authorization"] = "Bearer " + this.token;
        return h;
    },

    async request(path, { method = "GET", body, raw = false, headers = {} } = {}) {
        const res = await fetch(this.base + path, {
            method,
            headers: this.headers(headers),
            body: body !== undefined ? JSON.stringify(body) : undefined,
        });
        if (raw) {
            if (!res.ok) throw new Error("HTTP " + res.status);
            return res;
        }
        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data.error || data.detail || "HTTP " + res.status);
        return data;
    },

    get(p) { return this.request(p); },
    post(p, body) { return this.request(p, { method: "POST", body }); },
    put(p, body) { return this.request(p, { method: "PUT", body }); },
    del(p, body) { return this.request(p, { method: "DELETE", body }); },

    setAuth(token, username) {
        this.token = token;
        this.username = username;
        if (token) {
            localStorage.setItem("token", token);
            localStorage.setItem("username", username || "");
        } else {
            localStorage.removeItem("token");
            localStorage.removeItem("username");
        }
    },
    isLoggedIn() { return !!this.token; },
};
