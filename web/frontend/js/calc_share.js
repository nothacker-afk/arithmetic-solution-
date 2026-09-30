const CalcShare = (() => {
  async function save() {
    if (!API.isLoggedIn()) { UI.toast("Sign in first", "warning"); return; }
    const expr = document.getElementById("calc-expr");
    const res = document.getElementById("result");
    if (!expr || !expr.value.trim()) { UI.toast("Nothing to save", "warning"); return; }
    try {
      const d = await API.post("/api/calc/save", {
        expression: expr.value.trim(),
        result: res ? res.textContent : "",
        is_public: true,
      });
      try { await navigator.clipboard.writeText(location.origin + d.url); } catch (_) {}
      UI.toast("Saved: " + d.url, "success", 5000);
    } catch (e) { UI.toast("Save failed: " + e.message, "error"); }
  }
  async function list() {
    if (!API.isLoggedIn()) { UI.toast("Sign in first", "warning"); return; }
    try {
      const d = await API.get("/api/calc/saved");
      const html = d.calculations.length
        ? d.calculations.map(c => '<div class="feed-item"><code>' + c.expression + '</code> = <strong>' + c.result + '</strong></div>').join("")
        : "<div class='empty'>No saved calculations.</div>";
      UI.modal({title: "My saved", body: html, actions: [{label:"Close",kind:"primary"}]});
    } catch (e) { UI.toast("Load failed: " + e.message, "error"); }
  }
  function init() {
    const solve = document.getElementById("calc-solve-btn");
    const plot = document.getElementById("calc-plot-btn");
    const saveBtn = document.getElementById("calc-save-btn");
    const listBtn = document.getElementById("calc-share-list");
    if (solve) solve.addEventListener("click", () => window.Solver && Solver.open());
    if (plot) plot.addEventListener("click", () => window.Plotter && Plotter.open());
    if (saveBtn) saveBtn.addEventListener("click", save);
    if (listBtn) listBtn.addEventListener("click", list);
  }
  return {init};
})();
