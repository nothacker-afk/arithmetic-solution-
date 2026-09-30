const PWA = (() => {
    let deferredPrompt = null;

    function init() {
        if ("serviceWorker" in navigator) {
            window.addEventListener("load", () => {
                navigator.serviceWorker.register("/sw.js", { scope: "/" })
                    .catch(err => console.warn("[PWA] SW failed:", err));
            });
        }
        window.addEventListener("beforeinstallprompt", (e) => {
            e.preventDefault();
            deferredPrompt = e;
            document.getElementById("install-btn")?.classList.remove("hidden");
        });
        window.addEventListener("appinstalled", () => { deferredPrompt = null; });
        document.getElementById("install-btn")?.addEventListener("click", async () => {
            if (!deferredPrompt) return;
            deferredPrompt.prompt();
            await deferredPrompt.userChoice;
            deferredPrompt = null;
            document.getElementById("install-btn")?.classList.add("hidden");
        });
    }

    return { init };
})();
