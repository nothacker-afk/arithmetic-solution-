const Matrix = (() => {
    function parseMatrix(str) {
        return str.split(";").map(r => r.split(",").map(Number));
    }
    async function calculate() {
        const op = document.getElementById("matrix-op").value;
        const a = parseMatrix(document.getElementById("matrix-a").value);
        const body = { operation: op, a };
        if (op !== "matrix_transpose") body.b = parseMatrix(document.getElementById("matrix-b").value);
        try {
            const data = await API.post("/api/matrix", body);
            UI.setResult(`${data.expression} = ${JSON.stringify(data.result)}`, "success");
        } catch (e) {
            UI.setResult("Error: " + e.message, "error");
        }
    }
    function init() {
        document.getElementById("matrix-calc")?.addEventListener("click", calculate);
    }
    return { init, calculate };
})();
