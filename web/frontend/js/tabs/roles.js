// Advanced RBAC (Phase 76)
const Roles = (() => {
    const ALL_PERMISSIONS = [
        "can_post", "can_pin", "can_delete_others",
        "can_manage_wiki", "can_kick", "can_ban",
        "can_manage_roles", "can_archive",
    ];

    async function load() {
        const list = document.getElementById("roles-list");
        const room = document.getElementById("room-tab-room")?.value.trim();
        if (!list) return;
        if (!API.isLoggedIn() || !room) {
            list.innerHTML = `<div class="empty">Enter a room name and log in.</div>`;
            return;
        }
        try {
            const data = await API.get(`/api/rooms/${room}/roles`);
            if (!data.roles.length) {
                list.innerHTML = `<div class="empty">No custom roles yet.</div>`;
                return;
            }
            list.innerHTML = data.roles.map(r => `
                <div class="contact-row">
                    <div>
                        <strong>${r.name}</strong>
                        <div class="muted" style="font-size:var(--fs-xs);">
                            ${r.member_count} member(s)
                        </div>
                        <div style="margin-top:4px;">
                            ${r.permissions.map(p =>
                                `<span class="badge" style="margin-right:4px;">${p}</span>`
                            ).join("") || '<span class="muted">no permissions</span>'}
                        </div>
                    </div>
                    ${data.is_owner ? `
                        <div style="display:flex;gap:4px;">
                            <button class="btn btn-ghost btn-icon"
                                    onclick="Roles.assign('${r.name}')" title="Assign">+</button>
                            <button class="btn btn-ghost btn-icon"
                                    onclick="Roles.remove('${r.name}')" title="Delete">×</button>
                        </div>` : ""}
                </div>
            `).join("");
        } catch (e) {
            list.innerHTML = `<div class="empty">Error: ${e.message}</div>`;
        }
    }

    function create() {
        const room = document.getElementById("room-tab-room")?.value.trim();
        if (!room) { UI.toast("Enter a room name first", "warning"); return; }
        const body = document.createElement("div");
        body.innerHTML = `
            <div class="field"><label>Role name (a-z, 0-9, -, _)</label>
                <input id="role-name" class="input" placeholder="moderator" /></div>
            <div class="field"><label>Permissions</label>
                <div style="display:flex;flex-direction:column;gap:4px;">
                    ${ALL_PERMISSIONS.map(p => `
                        <label style="display:flex;align-items:center;gap:6px;">
                            <input type="checkbox" data-perm="${p}" />
                            <code>${p}</code>
                        </label>`).join("")}
                </div>
            </div>`;
        UI.modal({
            title: "New role",
            body,
            actions: [
                { label: "Save", kind: "primary", close: false, onClick: async (bd) => {
                    const name = bd.querySelector("#role-name").value.trim().toLowerCase();
                    const perms = [...bd.querySelectorAll("input[data-perm]")]
                        .filter(i => i.checked).map(i => i.dataset.perm);
                    if (!name) return;
                    try {
                        await API.post(`/api/rooms/${room}/roles`, { name, permissions: perms });
                        UI.toast("Role saved", "success");
                        bd.remove();
                        load();
                    } catch (e) { UI.toast("Save failed: " + e.message, "error"); }
                }},
                { label: "Cancel" },
            ],
        });
    }

    async function remove(roleName) {
        const room = document.getElementById("room-tab-room")?.value.trim();
        if (!confirm(`Delete role "${roleName}"?`)) return;
        try {
            await API.del(`/api/rooms/${room}/roles/${roleName}`);
            UI.toast("Role deleted");
            load();
        } catch (e) { UI.toast("Delete failed: " + e.message, "error"); }
    }

    async function assign(roleName) {
        const room = document.getElementById("room-tab-room")?.value.trim();
        const username = prompt("Assign to username:");
        if (!username) return;
        try {
            await API.post(`/api/rooms/${room}/roles/${roleName}/assign`, { username });
            UI.toast("Assigned", "success");
            load();
        } catch (e) { UI.toast("Assign failed: " + e.message, "error"); }
    }

    function init() {
        document.getElementById("roles-new")?.addEventListener("click", create);
        document.getElementById("roles-refresh")?.addEventListener("click", load);
    }

    function onShow() { load(); }

    return { init, onShow, load, create, remove, assign };
})();
