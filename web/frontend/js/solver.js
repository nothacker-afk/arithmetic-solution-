/* Equation solver UI (Phase 89) */
const Solver = (() => {
    function open() {
        const body = document.createElement("div");
        body.innerHTML = `
            <div class="field">
                <label for="sv-eq">Equation</label>
                <input id="sv-eq" class="input mono" placeholder="e.g. 2x + 5 = 15" autofocus />
            </div>
            <div class="field">
                <label for="sv-var">Variable</label>
                <input id="sv-var" class="input mono" value="x" maxlength="4" />
            </div>
            <button id="sv-run" class="btn btn-primary btn-block">Solve</button>
            <div id="sv-out" class="mt-4"></div>`;
        UI.modal({ title: "Solve equation", body, actions: [{ label: "Close" }] });
        body.querySelector("#sv-eq").addEventListener("keydown", (e) => {
            if (e.key === "Enter") { e.preventDefault(); run(body); }
        });
        body.querySelector("#sv-run").addEventListener("click", () => run(body));
    }
    async function run(root) {
        const eq = root.querySelector("#sv-eq").value.trim();
        const variable = root.querySelector("#sv-var").value.trim() || "x";
        const out = root.querySelector("#sv-out");
        if (!eq) return;
        out.innerHTML = `<div class="skeleton" style="height:60px;"></div>`;
        try {
            const data = await API.post("/api/calc/solve", { equation: eq, variable });
            if (data.solution === null) {
                out.innerHTML = `<div class="empty">${escapeHtml(data.message)}</div>`;
                return;
            }
            out.innerHTML = `
                <div class="calc-result-line">
                    <span class="calc-result-label">=</span>
                    <span class="calc-result-value mono">${escapeHtml(data.variable)} = ${escapeHtml(String(data.solution))}</span>
                </div>
                <p class="muted mt-2">${escapeHtml(data.message)}</p>
                <ol class="calc-step-list mt-3">
                    ${(data.steps || []).map((s, i) => `
                        <li class="calc-step">
                            <div class="calc-step-num">${i + 1}</div>
                            <div class="calc-step-body">
                                <code class="calc-step-expr">${escapeHtml(s.expr)}</code>
                                ${s.value !== undefined && s.value !== null
                                    ? `<span class="calc-step-arrow">→</span>
                                       <span class="calc-step-result mono">${escapeHtml(String(s.value))}</span>`
                                    : ""}
                                ${s.note ? `<div class="calc-step-note">${escapeHtml(s.note)}</div>` : ""}
                            </div>
                        </li>
                    `).join("")}
                </ol>`;
        } catch (e) {
            out.innerHTML = `<div class="empty" style="color:var(--danger);">Error: ${escapeHtml(e.message)}</div>`;
        }
    }
    function escapeHtml(s) {
        return String(s ?? "").replace(/[&<>"']/g, c =>
            ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
    }
    return { open };
})();
