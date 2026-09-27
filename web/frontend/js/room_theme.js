// Room custom theme (Phase 81)
const RoomTheme = (() => {
    let activeTheme = null;
    let activeRoom = null;

    function _applyToDom(theme) {
        if (!theme || !theme.is_custom) {
            // Remove any custom styling
            document.documentElement.style.removeProperty("--accent");
            document.documentElement.style.removeProperty("--accent-2");
            document.documentElement.style.removeProperty("--accent-soft");
            document.getElementById("room-banner")?.remove();
            document.getElementById("room-emoji")?.remove();
            return;
        }

        if (theme.accent) {
            document.documentElement.style.setProperty("--accent", theme.accent);
            document.documentElement.style.setProperty(
                "--accent-soft", _hexToRgba(theme.accent, 0.15));
        }
        if (theme.accent_2) {
            document.documentElement.style.setProperty("--accent-2", theme.accent_2);
        }

        // Banner
        if (theme.banner_url) {
            let banner = document.getElementById("room-banner");
            if (!banner) {
                banner = document.createElement("div");
                banner.id = "room-banner";
                banner.className = "room-banner";
                const shell = document.querySelector(".app-shell");
                shell?.insertBefore(banner, shell.firstChild.nextSibling);
            }
            banner.style.backgroundImage = `url(${theme.banner_url})`;
        }

        // Emoji badge next to the title
        if (theme.emoji) {
            let emoji = document.getElementById("room-emoji");
            if (!emoji) {
                emoji = document.createElement("span");
                emoji.id = "room-emoji";
                emoji.className = "room-emoji";
                const title = document.querySelector(".app-title");
                title?.insertAdjacentElement("afterend", emoji);
            }
            emoji.textContent = theme.emoji;
        }
    }

    function _hexToRgba(hex, alpha) {
        const h = hex.replace("#", "");
        const n = parseInt(h.length === 3
            ? h.split("").map(c => c + c).join("")
            : h, 16);
        const r = (n >> 16) & 255;
        const g = (n >> 8) & 255;
        const b = n & 255;
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }

    async function load(room) {
        if (!room) return null;
        try {
            const data = await API.get(`/api/rooms/${room}/theme`);
            activeRoom = room;
            activeTheme = data;
            _applyToDom(data);
            return data;
        } catch (e) {
            console.warn("[theme] load failed:", e.message);
            return null;
        }
    }

    function clear() {
        activeRoom = null;
        activeTheme = null;
        _applyToDom(null);
    }

    function editor() {
        const room = document.getElementById("room-tab-room")?.value.trim();
        if (!room) { UI.toast("Enter a room name first", "warning"); return; }

        const t = activeTheme || {};
        const body = document.createElement("div");
        body.innerHTML = `
            <div class="field"><label>Accent color</label>
                <input id="rt-accent" class="input" value="${t.accent || "#38bdf8"}" />
            </div>
            <div class="field"><label>Secondary accent</label>
                <input id="rt-accent2" class="input" value="${t.accent_2 || "#818cf8"}" />
            </div>
            <div class="field"><label>Banner image URL</label>
                <input id="rt-banner" class="input" value="${t.banner_url || ""}" placeholder="https://…" />
            </div>
            <div class="field"><label>Room emoji</label>
                <input id="rt-emoji" class="input" maxlength="8" value="${t.emoji || "🎨"}" />
            </div>
            <p class="muted" style="font-size:var(--fs-xs);">Only the room owner can save.</p>`;
        UI.modal({
            title: `Theme for ${room}`,
            body,
            actions: [
                { label: "Preview", kind: "ghost", close: false, onClick: (bd) => {
                    _applyToDom({
                        is_custom: true,
                        accent: bd.querySelector("#rt-accent").value.trim() || null,
                        accent_2: bd.querySelector("#rt-accent2").value.trim() || null,
                        banner_url: bd.querySelector("#rt-banner").value.trim() || null,
                        emoji: bd.querySelector("#rt-emoji").value.trim() || null,
                    });
                }},
                { label: "Save", kind: "primary", close: false, onClick: async (bd) => {
                    try {
                        const data = await API.put(`/api/rooms/${room}/theme`, {
                            accent: bd.querySelector("#rt-accent").value.trim() || null,
                            accent_2: bd.querySelector("#rt-accent2").value.trim() || null,
                            banner_url: bd.querySelector("#rt-banner").value.trim() || null,
                            emoji: bd.querySelector("#rt-emoji").value.trim() || null,
                        });
                        activeTheme = data;
                        _applyToDom(data);
                        UI.toast("Theme saved", "success");
                        bd.remove();
                    } catch (e) { UI.toast("Save failed: " + e.message, "error"); }
                }},
                { label: "Reset", kind: "danger", close: false, onClick: async (bd) => {
                    if (!confirm("Reset room theme to default?")) return;
                    try {
                        await API.del(`/api/rooms/${room}/theme`);
                        clear();
                        UI.toast("Theme reset");
                        bd.remove();
                    } catch (e) { UI.toast("Reset failed: " + e.message, "error"); }
                }},
                { label: "Close" },
            ],
        });
    }

    function init() {
        document.getElementById("room-theme-edit")?.addEventListener("click", editor);

        // Auto-load theme when the Live tab joins a room
        document.addEventListener("live:joined", (e) => {
            load(e.detail?.room);
        });
    }

    return { init, load, clear, editor };
})();
