const Scientific = (() => {
    async function calculate() {
        const op = document.getElementById("sci-op").value;
        const x = parseFloat(document.getElementById("sci-x").value);
        try {
            const data = await API.post("/api/scientific", { operation: op, x });
            UI.setResult(`${data.expression} = ${data.result}`, "success");
        } catch (e) {
            UI.setResult("Error: " + e.message, "error");
        }
    }
    function init() {
        document.getElementById("sci-calc")?.addEventListener("click", calculate);
    }
    return { init, calculate };
})();
