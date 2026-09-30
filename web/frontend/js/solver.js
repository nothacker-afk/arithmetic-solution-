const Solver = (() => {
  function open() {
    const b = document.createElement("div");
    b.innerHTML = '<div class="field"><label>Equation</label><input id="sv-eq" class="input mono" placeholder="2x+5=15"/></div><button id="sv-run" class="btn btn-primary btn-block">Solve</button><div id="sv-out" class="mt-4"></div>';
    UI.modal({title:"Solve equation",body:b,actions:[{label:"Close"}]});
    b.querySelector("#sv-run").addEventListener("click", async () => {
      const eq = b.querySelector("#sv-eq").value.trim();
      const out = b.querySelector("#sv-out");
      out.textContent = "Solving…";
      try {
        const d = await API.post("/api/calc/solve",{equation:eq,variable:"x"});
        out.textContent = d.solution === null ? d.message : `x = ${d.solution}`;
      } catch(e) { out.textContent = "Error: " + e.message; }
    });
  }
  return {open};
})();
