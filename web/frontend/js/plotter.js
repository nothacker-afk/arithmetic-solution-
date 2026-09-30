/* Function plotter on canvas (Phase 90) */
const Plotter = (() => {
    function open() {
        const body = document.createElement("div");
        body.innerHTML = `
            <div class="field">
                <label for="plot-expr">f(x)</label>
                <input id="plot-expr" class="input mono" placeholder="e.g. sin(x) * x" value="sin(x)" autofocus />
            </div>
            <div class="field-row">
                <div class="field"><label>x min</label>
                    <input id="plot-xmin" class="input" type="number" value="-10" step="any" /></div>
                <div class="field"><label>x max</label>
                    <input id="plot-xmax" class="input" type="number" value="10" step="any" /></div>
            </div>
            <button id="plot-run" class="btn btn-primary btn-block">Plot</button>
            <div class="plot-wrap mt-3">
                <canvas id="plot-canvas" width="600" height="360"
                        style="width:100%;height:auto;background:var(--bg-0);border-radius:var(--radius);"></canvas>
            </div>
            <div id="plot-info" class="muted mt-2" style="font-size:var(--fs-xs);"></div>`;
        UI.modal({ title: "Plot function", body, actions: [{ label: "Close" }] });
        body.querySelector("#plot-run").addEventListener("click", () => plot(body));
        body.querySelector("#plot-expr").addEventListener("keydown", (e) => {
            if (e.key === "Enter") { e.preventDefault(); plot(body); }
        });
        setTimeout(() => plot(body), 100);
    }
    async function plot(root) {
        const expr = root.querySelector("#plot-expr").value.trim();
        const xmin = parseFloat(root.querySelector("#plot-xmin").value);
        const xmax = parseFloat(root.querySelector("#plot-xmax").value);
        const info = root.querySelector("#plot-info");
        if (!expr || !Number.isFinite(xmin) || !Number.isFinite(xmax) || xmin >= xmax) {
            info.textContent = "Enter a valid expression and range.";
            return;
        }
        info.textContent = "Computing…";
        const n = 100;
        const xs = [];
        const step = (xmax - xmin) / (n - 1);
        for (let i = 0; i < n; i++) xs.push(xmin + i * step);
        const ys = new Array(n).fill(null);
        let next = 0;
        async function worker() {
            while (true) {
                const i = next++;
                if (i >= n) return;
                try {
                    const r = await API.post("/api/calc/expression", {
                        expression: expr, variables: { x: xs[i] },
                    });
                    const v = parseFloat(r.result);
                    ys[i] = Number.isFinite(v) ? v : null;
                } catch (_) { ys[i] = null; }
            }
        }
        await Promise.all([worker(), worker(), worker(), worker(), worker()]);
        draw(root.querySelector("#plot-canvas"), xs, ys);
        const valid = ys.filter(v => v !== null);
        info.textContent = valid.length
            ? `Sampled ${valid.length}/${n} points · y ∈ [${Math.min(...valid).toFixed(3)}, ${Math.max(...valid).toFixed(3)}]`
            : "No valid samples.";
    }
    function draw(canvas, xs, ys) {
        const ctx = canvas.getContext("2d");
        const W = canvas.width, H = canvas.height, pad = 30;
        ctx.clearRect(0, 0, W, H);
        const valid = ys.filter(v => v !== null);
        if (!valid.length) return;
        let ymin = Math.min(...valid), ymax = Math.max(...valid);
        if (ymin === ymax) { ymin -= 1; ymax += 1; }
        const yPad = (ymax - ymin) * 0.1;
        ymin -= yPad; ymax += yPad;
        const x0 = xs[0], x1 = xs[xs.length - 1];
        const toX = (x) => pad + (x - x0) / (x1 - x0) * (W - 2 * pad);
        const toY = (y) => H - pad - (y - ymin) / (ymax - ymin) * (H - 2 * pad);
        const css = getComputedStyle(document.documentElement);
        const accent = css.getPropertyValue("--accent").trim() || "#38bdf8";
        const border = css.getPropertyValue("--border-strong").trim() || "#334155";
        const fg3 = css.getPropertyValue("--fg-3").trim() || "#64748b";
        ctx.strokeStyle = border; ctx.lineWidth = 0.5;
        for (let i = 0; i <= 4; i++) {
            const y = pad + i * (H - 2 * pad) / 4;
            ctx.beginPath(); ctx.moveTo(pad, y); ctx.lineTo(W - pad, y); ctx.stroke();
            const x = pad + i * (W - 2 * pad) / 4;
            ctx.beginPath(); ctx.moveTo(x, pad); ctx.lineTo(x, H - pad); ctx.stroke();
        }
        ctx.strokeStyle = fg3; ctx.lineWidth = 1;
        if (x0 <= 0 && x1 >= 0) {
            const xz = toX(0);
            ctx.beginPath(); ctx.moveTo(xz, pad); ctx.lineTo(xz, H - pad); ctx.stroke();
        }
        if (ymin <= 0 && ymax >= 0) {
            const yz = toY(0);
            ctx.beginPath(); ctx.moveTo(pad, yz); ctx.lineTo(W - pad, yz); ctx.stroke();
        }
        ctx.strokeStyle = accent; ctx.lineWidth = 2; ctx.lineJoin = "round";
        ctx.beginPath();
        let started = false;
        for (let i = 0; i < xs.length; i++) {
            if (ys[i] === null) { started = false; continue; }
            const px = toX(xs[i]), py = toY(ys[i]);
            if (!started) { ctx.moveTo(px, py); started = true; }
            else { ctx.lineTo(px, py); }
        }
        ctx.stroke();
        ctx.fillStyle = fg3; ctx.font = "11px monospace";
        ctx.fillText(x0.toFixed(2), pad, H - 10);
        ctx.fillText(x1.toFixed(2), W - pad - 40, H - 10);
        ctx.fillText(ymax.toFixed(2), 4, pad + 10);
        ctx.fillText(ymin.toFixed(2), 4, H - pad - 4);
    }
    return { open };
})();
