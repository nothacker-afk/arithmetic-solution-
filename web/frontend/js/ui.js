// UI primitives — toast, modal, loading, result
const UI = (() => {
    // Toast container
    let _toastRoot = null;
    function _ensureToastRoot() {
        if (_toastRoot) return _toastRoot;
        _toastRoot = document.createElement("div");
        _toastRoot.className = "toast-container";
        _toastRoot.setAttribute("role", "status");
        _toastRoot.setAttribute("aria-live", "polite");
        document.body.appendChild(_toastRoot);
        return _toastRoot;
    }

    function toast(msg, kind = "info", ttl = 3200) {
        const el = document.createElement("div");
        el.className = "toast " + kind;
        el.textContent = msg;
        _ensureToastRoot().appendChild(el);
        setTimeout(() => {
            el.style.animation = "slideIn 220ms reverse";
            setTimeout(() => el.remove(), 220);
        }, ttl);
    }

    // Modal
    function modal({ title, body, actions = [], onClose }) {
        const backdrop = document.createElement("div");
        backdrop.className = "modal-backdrop";
        backdrop.innerHTML = `
            <div class="modal" role="dialog" aria-modal="true" aria-label="${title}">
                <h2>${title}</h2>
                <div class="modal-body"></div>
                <div class="modal-actions field-row mt-4"></div>
            </div>`;
        const bodyEl = backdrop.querySelector(".modal-body");
        if (typeof body === "string") bodyEl.innerHTML = body;
        else if (body instanceof Node) bodyEl.appendChild(body);

        const actionsEl = backdrop.querySelector(".modal-actions");
        for (const a of actions) {
            const btn = document.createElement("button");
            btn.className = "btn " + (a.kind === "primary" ? "btn-primary" : a.kind === "danger" ? "btn-danger" : "");
            btn.textContent = a.label;
            btn.onclick = async () => {
                if (a.onClick) await a.onClick(backdrop);
                if (a.close !== false) close();
            };
            actionsEl.appendChild(btn);
        }

        function close() {
            backdrop.remove();
            if (onClose) onClose();
        }

        backdrop.addEventListener("click", (e) => { if (e.target === backdrop) close(); });
        backdrop.addEventListener("keydown", (e) => { if (e.key === "Escape") close(); });

        document.body.appendChild(backdrop);
        const firstInput = backdrop.querySelector("input, button");
        if (firstInput) firstInput.focus();
        return { close, backdrop };
    }

    // Result panel
    function setResult(text, kind = "") {
        const el = document.getElementById("result");
        if (!el) return;
        el.textContent = text;
        el.classList.remove("error", "success");
        if (kind) el.classList.add(kind);
    }

    // Loading state for a button
    function busy(btn, fn) {
        return async (...args) => {
            if (btn.disabled) return;
            const original = btn.textContent;
            btn.disabled = true;
            btn.textContent = "…";
            try { return await fn(...args); }
            finally { btn.disabled = false; btn.textContent = original; }
        };
    }

    return { toast, modal, setResult, busy };
})();
