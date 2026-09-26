const Basic = (() => {
    async function calculate() {
        const op = document.getElementById("basic-op").value;
        const a = parseFloat(document.getElementById("basic-a").value);
        const b = parseFloat(document.getElementById("basic-b").value);
        try {
            const data = await API.post("/api/basic", { operation: op, a, b });
            UI.setResult(`${data.expression} = ${data.result}`, "success");
            if (window.Offline) Offline.cacheCalc({
                expression: data.expression,
                result: String(data.result),
                operation: op,
            });
        } catch (e) {
            UI.setResult("Error: " + e.message, "error");
        }
    }
    function init() {
        document.getElementById("basic-calc")?.addEventListener("click", calculate);
    }
    return { init, calculate };
})();
