const CalcShare = (() => {
  async function save() {
    const e = document.getElementById("calc-expr");
    if (!e || !API.isLoggedIn()) { UI.toast("Sign in first","warning"); return; }
    const d = await API.post("/api/calc/save",{expression:e.value,result:document.getElementById("result").textContent,is_public:true});
    UI.toast("Saved: "+d.url,"success");
  }
  function init() {
    ["calc-solve-btn:solver","calc-plot-btn:plotter"].forEach(p=>{
      const [id,mod]=p.split(":");
      const el=document.getElementById(id);
      if (el) el.onclick = () => window[mod==="solver"?"Solver":"Plotter"].open();
    });
    const s=document.getElementById("calc-save-btn"); if (s) s.onclick = save;
  }
  return {init,save};
})();
