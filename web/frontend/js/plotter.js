const Plotter = (() => {
  function open() {
    const b = document.createElement("div");
    b.innerHTML = "<input id=pl-expr class=input value=sin(x)><button id=pl-run class=\"btn btn-primary\">Plot</button><canvas id=pl-canvas width=600 height=360 style=\"width:100%;margin-top:8px\"></canvas>";
    UI.modal({title:"Plot f(x)",body:b,actions:[{label:"Close"}]});
    b.querySelector("#pl-run").onclick = () => run(b);
  }
  async function run(root) {
    const expr = root.querySelector("#pl-expr").value;
    const c = root.querySelector("#pl-canvas");
    const ctx = c.getContext("2d");
    ctx.clearRect(0,0,c.width,c.height);
    ctx.strokeStyle = "#38bdf8"; ctx.beginPath();
    for (let i=0;i<=100;i++) {
      const x = -10 + i*0.2;
      let y = 0;
      try { const r = await API.post("/api/calc/expression",{expression:expr,variables:{x}}); y = +r.result; } catch(_) {}
      const px = i*(c.width/100);
      const py = c.height/2 - y*20;
      if (i===0) ctx.moveTo(px,py); else ctx.lineTo(px,py);
    }
    ctx.stroke();
  }
  return {open};
})();
