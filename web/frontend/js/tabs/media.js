const MediaGallery = (() => {
    let currentRoom = null;

    function setRoom(room) { currentRoom = room; }

    async function load(filter = "all") {
        const grid = document.getElementById("media-grid");
        const room = currentRoom || document.getElementById("rt-room")?.value.trim();
        if (!room) {
            grid.innerHTML = `<div class="empty">Join a room first.</div>`;
            return;
        }
        currentRoom = room;
        grid.innerHTML = `<div class="skeleton" style="height:80px;"></div>
                          <div class="skeleton" style="height:80px;"></div>`;
        try {
            const data = await API.get(`/api/rooms/${room}/media?kind=${filter}`);
            if (!data.items.length) {
                grid.innerHTML = `<div class="empty">Nothing shared in this room yet.</div>`;
                return;
            }
            grid.innerHTML = data.items.map(it => renderTile(it)).join("");
        } catch (e) {
            grid.innerHTML = `<div class="empty">Error: ${e.message}</div>`;
        }
    }

    function fmtBytes(n) {
        if (n < 1024) return n + " B";
        if (n < 1024 * 1024) return (n / 1024).toFixed(1) + " KB";
        return (n / 1024 / 1024).toFixed(2) + " MB";
    }

    function renderTile(it) {
        const icon = it.kind === "voice" ? "🎤" : fileIcon(it.filename);
        const label = it.kind === "voice"
            ? `${(it.duration_ms / 1000).toFixed(1)}s voice`
            : it.filename;
        const meta = `${fmtBytes(it.size_bytes)} · ${it.username || "?"}`;
        return `
            <div class="media-tile" data-kind="${it.kind}" data-id="${it.id}">
                <div class="media-icon">${icon}</div>
                <div class="media-label mono">${label}</div>
                <div class="media-meta muted">${meta}</div>
            </div>`;
    }

    function fileIcon(name) {
        const n = (name || "").toLowerCase();
        if (/\.(png|jpe?g|gif|webp|svg)$/.test(n)) return "🖼️";
        if (/\.(mp4|mov|webm)$/.test(n)) return "🎬";
        if (/\.(mp3|ogg|wav)$/.test(n)) return "🎵";
        if (/\.(pdf)$/.test(n)) return "📄";
        if (/\.(zip|tar|gz)$/.test(n)) return "🗜️";
        return "📎";
    }

    function init() {
        document.querySelectorAll("[data-media-filter]").forEach(btn => {
            btn.addEventListener("click", () => {
                document.querySelectorAll("[data-media-filter]").forEach(b =>
                    b.classList.remove("active"));
                btn.classList.add("active");
                load(btn.dataset.mediaFilter);
            });
        });
        document.getElementById("media-refresh")?.addEventListener("click", () => load("all"));
    }

    function onShow() { load("all"); }

    return { init, onShow, load, setRoom };
})();
