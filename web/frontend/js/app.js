// Main app controller — tabs, auth, init
const Tab = (() => {
    function go(name) {
        document.querySelectorAll(".tab").forEach(t => {
            const active = t.dataset.tab === name;
            t.classList.toggle("active", active);
            t.setAttribute("aria-selected", active ? "true" : "false");
        });
        document.querySelectorAll(".tab-panel").forEach(p => {
            p.classList.toggle("active", p.id === "panel-" + name);
        });
        location.hash = "#" + name;
        // Lazy loads
        if (name === "history" && window.History) History.load();
        if (name === "history" && window.Scheduled) Scheduled.listPending();
        if (name === "dms" && window.DMs) DMs.onShow();
        if (name === "discover" && window.Discover) Discover.onShow();
        if (name === "contacts" && window.Contacts) Contacts.onShow();
        if (name === "bots" && window.Bots) Bots.onShow();

        if (name === "realtime" && window.Live) Live.onShow();
        if (name === "realtime" && window.MediaGallery) MediaGallery.onShow();
    }

    function init() {
        document.querySelectorAll(".tab").forEach(t => {
            t.addEventListener("click", () => go(t.dataset.tab));
        });
        const initial = (location.hash || "#basic").slice(1);
        go(["basic", "scientific", "matrix", "ai", "realtime", "history", "search", "dms"].includes(initial) ? initial : "basic");
    }

    return { go, init };
})();

const Auth = (() => {
    let mode = "login";

    function openLogin() {
        mode = "login";
        render();
    }
    function openRegister() {
        mode = "register";
        render();
    }

    function render() {
        const isRegister = mode === "register";
        const form = document.createElement("div");
        form.innerHTML = `
            <div class="field">
                <label for="auth-username">Username</label>
                <input class="input" id="auth-username" autocomplete="username" />
            </div>
            ${isRegister ? `
            <div class="field">
                <label for="auth-email">Email</label>
                <input class="input" id="auth-email" type="email" autocomplete="email" />
            </div>` : ""}
            <div class="field">
                <label for="auth-password">Password</label>
                <input class="input" id="auth-password" type="password" autocomplete="current-password" />
            </div>
            <div class="field">
                <label for="auth-error" class="hidden"></label>
                <div id="auth-error" class="muted" style="min-height:1.2em;color:var(--danger);"></div>
            </div>
            <button class="btn btn-ghost" id="auth-switch" type="button">
                ${isRegister ? "Have an account? Login" : "Need an account? Register"}
            </button>
        `;

        const { close } = UI.modal({
            title: isRegister ? "Create account" : "Login",
            body: form,
            actions: [
                { label: isRegister ? "Create account" : "Login", kind: "primary", close: false, onClick: async (backdrop) => {
                    const username = backdrop.querySelector("#auth-username").value.trim();
                    const password = backdrop.querySelector("#auth-password").value;
                    const email = backdrop.querySelector("#auth-email")?.value.trim();
                    const errEl = backdrop.querySelector("#auth-error");
                    errEl.textContent = "";
                    try {
                        const body = isRegister ? { username, email, password } : { username, password };
                        const path = isRegister ? "/api/auth/register" : "/api/auth/login";
                        const data = await API.post(path, body);
                        API.setAuth(data.token, data.username);
                        updateUI();
                        close();
                        UI.toast("Welcome, " + data.username, "success");
                    } catch (e) {
                        errEl.textContent = e.message;
                    }
                }},
                { label: "Cancel", onClick: () => {} },
            ],
        });

        form.querySelector("#auth-switch").addEventListener("click", () => {
            close();
            setTimeout(() => isRegister ? openLogin() : openRegister(), 60);
        });
    }

    async function tryPasskey() {
        if (!window.Passkey || !Passkey.supported()) {
            UI.toast("Passkeys not supported on this device", "warning");
            return;
        }
        try {
            const result = await Passkey.login();
            API.setAuth(result.token, result.username);
            updateUI();
            UI.toast("Welcome back, " + result.username, "success");
        } catch (e) {
            UI.toast("Passkey login failed: " + e.message, "error");
        }
    }

    function updateUI() {
        const label = document.getElementById("user-label");
        const btn = document.getElementById("auth-btn");
        const pkBtn = document.getElementById("passkey-btn");
        if (API.isLoggedIn()) {
            label.textContent = API.username || "User";
            btn.textContent = "Logout";
            if (pkBtn) pkBtn.classList.add("hidden");
        } else {
            label.textContent = "Guest";
            btn.textContent = "Login";
            if (pkBtn && window.Passkey && Passkey.supported()) pkBtn.classList.remove("hidden");
        }
    }

    function init() {
        document.getElementById("auth-btn").addEventListener("click", () => {
            if (API.isLoggedIn()) {
                API.setAuth(null);
                updateUI();
                UI.toast("Logged out");
            } else {
                openLogin();
            }
        });
        document.getElementById("passkey-btn")?.addEventListener("click", tryPasskey);
        updateUI();
    }

    return { init, openLogin, openRegister, updateUI };
})();

// Boot
document.addEventListener("DOMContentLoaded", () => {
    Theme.init();
    Tab.init();
    Auth.init();
    Commands.init();
    if (window.EmojiAutocomplete) EmojiAutocomplete.init();
    if (window.Offline) Offline.init();
    if (window.History) History.init();
    if (window.Basic) Basic.init();
    if (window.Scientific) Scientific.init();
    if (window.Matrix) Matrix.init();
    if (window.AI) AI.init();
    if (window.Search) Search.init();
    if (window.Contacts) Contacts.init();
    if (window.Discover) Discover.init();
    if (window.Bots) Bots.init();
    if (window.MediaGallery) MediaGallery.init();
    if (window.Scheduled) Scheduled.init();
    if (window.DMs) DMs.init();
    if (window.Live) Live.init();
    if (window.PWA) PWA.init();
});
