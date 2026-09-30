const Solver = (() => {
  function open() {
    const b = document.createElement("div");
    b.innerHTML = "<input id=sv-eq class=input placeholder=2x+5=15><button id=sv-run class=\"btn btn-primary\">Solve</button><div id=sv-out></div>";
    UI.modal({title:"Solve equation",body:b,actions:[{label:"Close"}]});
    b.querySelector("#sv-run").onclick = async () => {
      const d = await API.post("/api/calc/solve",{equation:b.querySelector("#sv-eq").value,variable:"x"});
      b.querySelector("#sv-out").textContent = d.solution===null?d.message:("x = "+d.solution);
    };
  }
  return {open};
})();
