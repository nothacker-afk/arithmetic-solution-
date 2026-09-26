// Export trigger (Phase 34)
const ExportUI = (() => {
    async function download(kind, id, format, label) {
        const path = kind === "room"
            ? `/api/export/room/${encodeURIComponent(id)}?format=${format}`
            : `/api/export/dm/${id}?format=${format}`;
        try {
            const res = await fetch(`${API.base}${path}`, {
                headers: API.token ? { "Authorization": "Bearer " + API.token } : {},
            });
            if (!res.ok) throw new Error("HTTP " + res.status);
            if (format === "html") {
                // Open inline (user can print-to-PDF)
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                window.open(url, "_blank");
                UI.toast("Opened HTML export in new tab — use Print → Save as PDF", "success");
                setTimeout(() => URL.revokeObjectURL(url), 30000);
            } else {
                const blob = await res.blob();
                const url = URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `${label || kind}-${id}.${format}`;
                document.body.appendChild(a);
                a.click();
                a.remove();
                setTimeout(() => URL.revokeObjectURL(url), 2000);
                UI.toast(`Downloaded ${format.toUpperCase()}`, "success");
            }
        } catch (e) {
            UI.toast("Export failed: " + e.message, "error");
        }
    }
    return { download };
})();
