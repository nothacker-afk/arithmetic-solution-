const AI = (() => {
    async function solve() {
        const text = document.getElementById("ai-input").value.trim();
        if (!text) return;
        try {
            const data = await API.post("/api/ai", { text });
            UI.setResult(`${data.expression} = ${data.result}`, "success");
        } catch (e) {
            UI.setResult("Error: " + e.message, "error");
        }
    }
    function init() {
        document.getElementById("ai-solve")?.addEventListener("click", solve);
        document.getElementById("ai-input")?.addEventListener("keydown", (e) => {
            if (e.key === "Enter") { e.preventDefault(); solve(); }
        });
    }
    return { init, solve };
})();
