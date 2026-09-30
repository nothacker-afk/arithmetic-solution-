// Presence avatars (Phase 29)
const Presence = (() => {
    // Deterministic color from username
    function colorOf(name) {
        let h = 0;
        for (let i = 0; i < name.length; i++) h = ((h << 5) - h + name.charCodeAt(i)) | 0;
        const hue = Math.abs(h) % 360;
        return `hsl(${hue} 65% 50%)`;
    }

    function initials(name) {
        const parts = name.trim().split(/\s+/);
        if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
        return name.slice(0, 2).toUpperCase();
    }

    function avatarEl(name, size = 24) {
        const el = document.createElement("span");
        el.title = name;
        el.style.cssText = `
            display:inline-flex;align-items:center;justify-content:center;
            width:${size}px;height:${size}px;border-radius:50%;
            background:${colorOf(name)};color:white;
            font-size:${Math.round(size * 0.42)}px;font-weight:700;
            border:2px solid var(--bg-1);margin-left:-6px;`;
        el.textContent = initials(name);
        return el;
    }

    function renderStrip(containerId, users) {
        const el = document.getElementById(containerId);
        if (!el) return;
        el.innerHTML = "";
        el.style.cssText = "display:flex;align-items:center;padding-left:6px;min-height:28px;";
        for (const u of users) el.appendChild(avatarEl(u));
        if (users.length) {
            const count = document.createElement("span");
            count.style.cssText = "margin-left:8px;font-size:var(--fs-xs);color:var(--fg-2);";
            count.textContent = users.length === 1 ? "1 person here" : users.length + " people here";
            el.appendChild(count);
        } else {
            el.innerHTML = `<span class="muted" style="font-size:var(--fs-xs);">No one here yet</span>`;
        }
    }

    function init() {
        // Expose for Live module
        window.Presence = { colorOf, initials, avatarEl, renderStrip };
    }

    return { init, colorOf, initials, avatarEl, renderStrip };
})();
