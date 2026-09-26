// Emoji autocomplete (Phase 36)
// Trigger: type ":" followed by 1-3 letters in any input with data-emoji-picker.
const EmojiAutocomplete = (() => {
    const SHORTCODES = {
        "smile": "😄", "joy": "😂", "heart": "❤️", "thumbsup": "👍", "thumbsdown": "👎",
        "fire": "🔥", "tada": "🎉", "eyes": "👀", "rocket": "🚀", "100": "💯",
        "wave": "👋", "clap": "👏", "pray": "🙏", "ok": "👌", "check": "✅",
        "x": "❌", "warning": "⚠️", "info": "ℹ️", "question": "❓", "star": "⭐",
        "sparkles": "✨", "sun": "☀️", "moon": "🌙", "cloud": "☁️", "rain": "🌧️",
        "snow": "❄️", "cat": "🐱", "dog": "🐶", "pizza": "🍕", "coffee": "☕",
        "cake": "🍰", "gift": "🎁", "bulb": "💡", "book": "📚", "lock": "🔒",
        "key": "🔑", "bell": "🔔", "link": "🔗", "pin": "📌", "calendar": "📅",
        "clock": "🕐", "chart": "📊", "memo": "📝", "folder": "📁", "gear": "⚙️",
        "bug": "🐛", "zap": "⚡", "boom": "💥", "speech": "💬", "thinking": "🤔",
    };
    let _active = null;

    function palette() {
        // Merge Reactions palette with shortcodes
        const reactions = window.Reactions ? Reactions.PALETTE : [];
        const all = new Map();
        for (const e of reactions) all.set(e, e);
        for (const [k, v] of Object.entries(SHORTCODES)) {
            if (!all.has(v)) all.set(v, v);
        }
        return all;
    }

    function findMatch(input, caretPos) {
        const before = input.slice(0, caretPos);
        const m = before.match(/:([a-zA-Z0-9_+-]{1,15})$/);
        return m ? { start: caretPos - m[0].length, token: m[1].toLowerCase(), query: m[1] } : null;
    }

    function suggestions(query) {
        const all = palette();
        const out = [];
        for (const [key, emoji] of all.entries()) {
            if (key.startsWith(query)) out.push({ key, emoji });
            if (out.length >= 8) break;
        }
        return out;
    }

    function showPicker(input, items, match) {
        hidePicker();
        const box = document.createElement("div");
        box.className = "emoji-autocomplete";
        box.innerHTML = items.map((it, i) =>
            `<button class="emoji-auto-item ${i === 0 ? "selected" : ""}" data-emoji="${it.emoji}">
                <span class="emoji">${it.emoji}</span>
                <span class="shortcode">:${it.key}:</span>
            </button>`
        ).join("") || `<div class="emoji-auto-empty">No matches</div>`;

        const rect = input.getBoundingClientRect();
        box.style.cssText = `
            position:fixed;left:${rect.left}px;top:${rect.bottom + 4}px;
            z-index:9999;width:${Math.max(220, rect.width)}px;`;

        document.body.appendChild(box);
        _active = { box, input, match };

        box.querySelectorAll(".emoji-auto-item").forEach(btn => {
            btn.addEventListener("mousedown", (e) => {
                e.preventDefault();
                insertEmoji(input, match, btn.dataset.emoji);
            });
        });
    }

    function insertEmoji(input, match, emoji) {
        const before = input.value.slice(0, match.start);
        const after = input.value.slice(input.selectionStart);
        const next = before + emoji + " " + after;
        input.value = next;
        const pos = before.length + emoji.length + 1;
        input.setSelectionRange(pos, pos);
        input.dispatchEvent(new Event("input", { bubbles: true }));
        hidePicker();
    }

    function hidePicker() {
        if (_active) {
            _active.box.remove();
            _active = null;
        }
    }

    function attach(input) {
        if (input.dataset.emojiAttached === "1") return;
        input.dataset.emojiAttached = "1";

        input.addEventListener("input", () => {
            const match = findMatch(input.value, input.selectionStart);
            if (!match) return hidePicker();
            const items = suggestions(match.token);
            if (!items.length) return hidePicker();
            showPicker(input, items, match);
        });

        input.addEventListener("keydown", (e) => {
            if (!_active) return;
            const items = _active.box.querySelectorAll(".emoji-auto-item");
            if (!items.length) return;
            const current = [...items].findIndex(i => i.classList.contains("selected"));

            if (e.key === "ArrowDown") {
                e.preventDefault();
                items[current]?.classList.remove("selected");
                items[(current + 1) % items.length].classList.add("selected");
            } else if (e.key === "ArrowUp") {
                e.preventDefault();
                items[current]?.classList.remove("selected");
                items[(current - 1 + items.length) % items.length].classList.add("selected");
            } else if (e.key === "Enter" || e.key === "Tab") {
                e.preventDefault();
                const sel = _active.box.querySelector(".emoji-auto-item.selected");
                if (sel) insertEmoji(input, _active.match, sel.dataset.emoji);
            } else if (e.key === "Escape") {
                e.preventDefault();
                hidePicker();
            }
        });

        input.addEventListener("blur", () => setTimeout(hidePicker, 150));
    }

    function init() {
        // Attach to all inputs marked with data-emoji-picker
        document.querySelectorAll("input[data-emoji-picker], textarea[data-emoji-picker]")
            .forEach(attach);
        // Auto-attach to known chat/DM inputs
        ["rt-chat-input", "dm-input"].forEach(id => {
            const el = document.getElementById(id);
            if (el) attach(el);
        });
    }

    return { init, attach, SHORTCODES, palette };
})();
