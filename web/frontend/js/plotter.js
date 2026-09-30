const Plotter = (() => {
  function open() {
    const b = document.createElement("div");
    b.innerHTML = '<div class="field"><label>f(x)</label><input id="plot-expr" class="input mono" value="sin(x)"/></div><div class="field-row"><div class="field"><label>x min</label><input id="plot-xmin" class="input" type="number" value="-10"/></div><div class="field"><label>x max</label><input id="plot-xmax" class="input" type="number" value="10"/></div></div><button id="plot-run" class="btn btn-primary btn-block">Plot</button><canvas id="plot-canvas" width="600" height="360" style="width:100%;margin-top:12px;background:var(--bg-0);border-radius:6px;"></canvas>';
    UI.modal({title:"Plot f(x)",body:b,actions:[{label:"Close"}]});
    b.querySelector("#plot-run").addEventListener("click", () => plot(b));
    setTimeout(() => plot(b), 100);
  }
  async function plot(root) {
    const expr = root.querySelector("#plot-expr").value.trim();
    const xmin = +root.querySelector("#plot-xmin").value;
    const xmax = +root.querySelector("#plot-xmax").value;
    const n = 100;
    const xs = [], ys = [];
    for (let i = 0; i < n; i++) xs.push(xmin + i * (xmax - xmin) / (n - 1));
    for (const x of xs) {
      try {
        const r = await API.post("/api/calc/expression", {expression: expr, variables: {x}});
        ys.push(parseFloat(r.result));
      } catch (_) { ys.push(NaN); }
    }
    draw(root.querySelector("#plot-canvas"), xs, ys);
  }
  function draw(canvas, xs, ys) {
    const ctx = canvas.getContext("2d");
    const W = canvas.width, H = canvas.height, pad = 30;
    ctx.clearRect(0, 0, W, H);
    const valid = ys.filter(v => !isNaN(v));
    if (!valid.length) return;
    let ymin = Math.min(...valid), ymax = Math.max(...valid);
    if (ymin === ymax) { ymin -= 1; ymax += 1; }
    const toX = (x) => pad + (x - xs[0]) / (xs[xs.length-1] - xs[0]) * (W - 2*pad);
    const toY = (y) => H - pad - (y - ymin) / (ymax - ymin) * (H - 2*pad);
    ctx.strokeStyle = "#334155";
    ctx.lineWidth = 0.5;
    for (let i = 0; i <= 4; i++) {
      const y = pad + i * (H - 2*pad) / 4;
      ctx.beginPath(); ctx.moveTo(pad, y); ctx.lineTo(W - pad, y); ctx.stroke();
    }
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 2;
    ctx.beginPath();
    let started = false;
    for (let i = 0; i < xs.length; i++) {
      if (isNaN(ys[i])) { started = false; continue; }
      const px = toX(xs[i]), py = toY(ys[i]);
      if (!started) { ctx.moveTo(px, py); started = true; }
      else { ctx.lineTo(px, py); }
    }
    ctx.stroke();
  }
  return {open};
})();
