// Message translation (Phase 83)
const Translate = (() => {
    const LANGS = [
        { code: "en", label: "English" },
        { code: "sw", label: "Kiswahili" },
        { code: "fr", label: "Français" },
        { code: "es", label: "Español" },
        { code: "ru", label: "Русский" },
        { code: "zh", label: "中文" },
        { code: "hi", label: "हिन्दी" },
        { code: "ar", label: "العربية" },
        { code: "pt", label: "Português" },
        { code: "de", label: "Deutsch" },
        { code: "ja", label: "日本語" },
    ];

    function picker(kind, messageId, text) {
        const body = document.createElement("div");
        body.innerHTML = `
            <div class="field"><label>Translate to</label>
                <select id="tr-lang" class="select">
                    ${LANGS.map(l => `<option value="${l.code}">${l.label}</option>`).join("")}
                </select>
            </div>
            <button class="btn btn-primary" id="tr-go">Translate</button>
            <div id="tr-output" class="mt-4"></div>`;
        UI.modal({
            title: "Translate",
            body,
            actions: [{ label: "Close" }],
        });
        body.querySelector("#tr-go").addEventListener("click", async () => {
            const lang = body.querySelector("#tr-lang").value;
            const out = body.querySelector("#tr-output");
            out.innerHTML = `<div class="skeleton" style="height:40px;"></div>`;
            try {
                const data = await API.post("/api/translate/message", {
                    kind, message_id: messageId, target_lang: lang, text,
                });
                out.innerHTML = `
                    <div class="result-panel" style="font-family:var(--font-sans);">
                        ${escapeHtml(data.translation)}
                    </div>
                    <p class="muted mt-2" style="font-size:var(--fs-xs);">
                        Source: ${data.detected_source_lang || "?"}
                        ${data.cached ? " · cached" : ""}
                    </p>`;
            } catch (e) {
                out.innerHTML = `<div class="empty">Error: ${escapeHtml(e.message)}</div>`;
            }
        });
    }

    function escapeHtml(s) {
        return (s ?? "").toString().replace(/[&<>"']/g, c =>
            ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
    }

    return { picker };
})();
