"""Arithmetic Super App — Flet cross-platform client.

Covers all major features of the web app: basic/scientific/matrix
math, AI, auth, DMs, groups, room chat, live collaboration, search,
contacts, and settings.

Requires the Flask backend to be running. Point API_BASE at it.
"""
import flet as ft
import requests

API_BASE = "http://localhost:8000"


class State:
    def __init__(self):
        self.token = None
        self.username = None
        self.active_tab = "calc"


def _api(state, method, path, body=None):
    headers = {"Content-Type": "application/json"}
    if state.token:
        headers["Authorization"] = f"Bearer {state.token}"
    url = API_BASE + path
    r = requests.request(method, url, json=body, headers=headers, timeout=6)
    if r.status_code >= 400:
        try:
            msg = r.json().get("error", r.text)
        except Exception:
            msg = r.text
        raise RuntimeError(msg)
    if r.content:
        return r.json()
    return {}


def main(page: ft.Page):
    state = State()
    page.title = "Arithmetic Super App"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 12
    page.window_width = 420
    page.window_height = 780

    status = ft.Text("Ready.", size=13, color=ft.Colors.GREY)
    result = ft.Text("", size=18, selectable=True)

    def show(msg, is_error=False):
        status.value = msg
        status.color = ft.Colors.RED if is_error else ft.Colors.GREY
        page.update()

    def show_result(msg):
        result.value = msg
        page.update()

    # ---------------------------------------------------------------
    # Auth
    # ---------------------------------------------------------------
    auth_username = ft.TextField(label="Username", dense=True)
    auth_email = ft.TextField(label="Email", dense=True, visible=False)
    auth_password = ft.TextField(label="Password", password=True, dense=True)

    def do_register(e=None):
        try:
            r = _api(state, "POST", "/api/auth/register", {
                "username": auth_username.value,
                "email": auth_email.value,
                "password": auth_password.value,
            })
            state.token = r["token"]
            state.username = r["username"]
            show(f"Registered as {state.username}")
            refresh_ui()
        except Exception as ex:
            show(str(ex), True)

    def do_login(e=None):
        try:
            r = _api(state, "POST", "/api/auth/login", {
                "username": auth_username.value,
                "password": auth_password.value,
            })
            state.token = r["token"]
            state.username = r["username"]
            show(f"Welcome, {state.username}")
            refresh_ui()
        except Exception as ex:
            show(str(ex), True)

    def do_logout(e=None):
        state.token = None
        state.username = None
        show("Logged out")
        refresh_ui()

    def toggle_register(e=None):
        auth_email.visible = not auth_email.visible
        page.update()

    # ---------------------------------------------------------------
    # Math tabs
    # ---------------------------------------------------------------
    calc_a = ft.TextField(label="a", value="10", dense=True, keyboard_type=ft.KeyboardType.NUMBER)
    calc_b = ft.TextField(label="b", value="5", dense=True, keyboard_type=ft.KeyboardType.NUMBER)
    calc_op = ft.Dropdown(
        label="Operation", value="add", dense=True,
        options=[ft.dropdown.Option(x) for x in
                 ("add", "subtract", "multiply", "divide", "power", "modulo")],
    )

    def run_calc(e=None):
        try:
            r = _api(state, "POST", "/api/basic", {
                "operation": calc_op.value,
                "a": float(calc_a.value),
                "b": float(calc_b.value),
            })
            show_result(f"{r['expression']} = {r['result']}")
        except Exception as ex:
            show_result(f"Error: {ex}")

    sci_x = ft.TextField(label="x", value="16", dense=True, keyboard_type=ft.KeyboardType.NUMBER)
    sci_op = ft.Dropdown(
        label="Operation", value="sqrt", dense=True,
        options=[ft.dropdown.Option(x) for x in
                 ("sqrt", "cbrt", "log10", "sin", "cos", "tan", "factorial", "absolute")],
    )

    def run_sci(e=None):
        try:
            r = _api(state, "POST", "/api/scientific", {
                "operation": sci_op.value, "x": float(sci_x.value),
            })
            show_result(f"{r['expression']} = {r['result']}")
        except Exception as ex:
            show_result(f"Error: {ex}")

    ai_input = ft.TextField(label="Ask in plain English", hint_text="what is 15% of 240", dense=True)

    def run_ai(e=None):
        try:
            r = _api(state, "POST", "/api/ai", {"text": ai_input.value})
            show_result(f"{r['expression']} = {r['result']}")
        except Exception as ex:
            show_result(f"Error: {ex}")

    # ---------------------------------------------------------------
    # Live collaboration
    # ---------------------------------------------------------------
    room_name = ft.TextField(label="Room", value="demo-room", dense=True)
    room_user = ft.TextField(label="Display name", value="guest", dense=True)
    room_chat = ft.TextField(label="Message", dense=True)
    room_log = ft.ListView(expand=True, spacing=4, height=180, auto_scroll=True)

    def join_room(e=None):
        show(f"Joining {room_name.value}… (use web app for full live features)")
        try:
            # Send a hello via REST so the room sees us
            _api(state, "POST", f"/api/chat/{room_name.value}", {
                "username": room_user.value, "body": "joined via mobile", "encrypted": False,
            })
            load_room_log()
        except Exception as ex:
            show(str(ex), True)

    def load_room_log(e=None):
        try:
            data = _api(state, "GET", f"/api/chat/{room_name.value}?limit=30")
            room_log.controls.clear()
            for m in data["messages"]:
                room_log.controls.append(
                    ft.Text(f"{m['username']}: {m['body'] or '(attachment)'}", size=12)
                )
            page.update()
        except Exception as ex:
            show(str(ex), True)

    def send_room_msg(e=None):
        if not room_chat.value.strip():
            return
        try:
            _api(state, "POST", f"/api/chat/{room_name.value}", {
                "username": room_user.value,
                "body": room_chat.value,
                "encrypted": False,
            })
            room_chat.value = ""
            load_room_log()
        except Exception as ex:
            show(str(ex), True)

    # ---------------------------------------------------------------
    # DMs
    # ---------------------------------------------------------------
    dm_to = ft.TextField(label="Username to DM", dense=True)
    dm_body = ft.TextField(label="Message", dense=True)
    dm_log = ft.ListView(expand=True, spacing=4, height=180, auto_scroll=True)
    dm_thread_id = [None]

    def start_dm(e=None):
        try:
            r = _api(state, "POST", "/api/dms/threads", {"username": dm_to.value})
            dm_thread_id[0] = r["thread_id"]
            show(f"Thread with {r['other_username']}")
            load_dm()
        except Exception as ex:
            show(str(ex), True)

    def load_dm(e=None):
        if not dm_thread_id[0]:
            return
        try:
            data = _api(state, "GET", f"/api/dms/threads/{dm_thread_id[0]}?limit=30")
            dm_log.controls.clear()
            for m in data["messages"]:
                dm_log.controls.append(
                    ft.Text(f"{m['sender']}: {m['body'] or '(encrypted)'}", size=12)
                )
            page.update()
        except Exception as ex:
            show(str(ex), True)

    def send_dm(e=None):
        if not dm_thread_id[0] or not dm_body.value.strip():
            return
        try:
            _api(state, "POST", f"/api/dms/threads/{dm_thread_id[0]}", {
                "body": dm_body.value, "encrypted": False,
            })
            dm_body.value = ""
            load_dm()
        except Exception as ex:
            show(str(ex), True)

    # ---------------------------------------------------------------
    # Groups
    # ---------------------------------------------------------------
    groups_log = ft.ListView(expand=True, spacing=4, height=200)
    groups_active_id = [None]

    def load_groups(e=None):
        try:
            data = _api(state, "GET", "/api/groups")
            groups_log.controls.clear()
            for g in data["groups"]:
                groups_log.controls.append(
                    ft.ListTile(
                        title=ft.Text(g["name"]),
                        subtitle=ft.Text(f"{g['member_count']} members"),
                        on_click=lambda _, gid=g["id"]: open_group(gid),
                    )
                )
            page.update()
        except Exception as ex:
            show(str(ex), True)

    def open_group(gid):
        groups_active_id[0] = gid
        try:
            data = _api(state, "GET", f"/api/groups/{gid}/messages?limit=30")
            groups_log.controls.clear()
            for m in data["messages"]:
                groups_log.controls.append(ft.Text(f"{m['sender']}: {m['body'] or '(encrypted)'}"))
            page.update()
        except Exception as ex:
            show(str(ex), True)

    # ---------------------------------------------------------------
    # Search
    # ---------------------------------------------------------------
    search_q = ft.TextField(label="Search", dense=True)
    search_log = ft.ListView(expand=True, spacing=4, height=200)

    def run_search(e=None):
        try:
            data = _api(state, "GET", f"/api/search?q={search_query()}")
            search_log.controls.clear()
            for r in data["results"]:
                if r["kind"] == "calculation":
                    line = f"[calc] {r['expression']} = {r['result']}"
                else:
                    line = f"[chat] {r['username']}: {r['body']}"
                search_log.controls.append(ft.Text(line, size=12))
            page.update()
        except Exception as ex:
            show(str(ex), True)

    def search_query():
        import urllib.parse
        return urllib.parse.quote(search_q.value or "")

    # ---------------------------------------------------------------
    # Contacts
    # ---------------------------------------------------------------
    contacts_log = ft.ListView(expand=True, spacing=4, height=200)

    def load_contacts(e=None):
        try:
            data = _api(state, "GET", "/api/contacts")
            contacts_log.controls.clear()
            for c in data["contacts"]:
                contacts_log.controls.append(
                    ft.Text(("⭐ " if c["favourite"] else "") + c["username"])
                )
            page.update()
        except Exception as ex:
            show(str(ex), True)

    # ---------------------------------------------------------------
    # Tabs
    # ---------------------------------------------------------------
    body = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)

    def render_calc():
        body.controls = [
            ft.Text("Basic", size=16, weight=ft.FontWeight.BOLD),
            calc_op, calc_a, calc_b,
            ft.ElevatedButton("Calculate", on_click=run_calc),
            ft.Divider(),
            ft.Text("Scientific", size=16, weight=ft.FontWeight.BOLD),
            sci_op, sci_x,
            ft.ElevatedButton("Solve", on_click=run_sci),
            ft.Divider(),
            ft.Text("AI", size=16, weight=ft.FontWeight.BOLD),
            ai_input,
            ft.ElevatedButton("Ask", on_click=run_ai),
        ]

    def render_live():
        body.controls = [
            ft.Text("Live room", size=16, weight=ft.FontWeight.BOLD),
            room_name, room_user,
            ft.Row([
                ft.ElevatedButton("Join", on_click=join_room),
                ft.ElevatedButton("Reload", on_click=load_room_log),
            ]),
            ft.Container(room_log, bgcolor=ft.Colors.BLACK26, border_radius=6, padding=8),
            ft.Row([
                ft.Container(room_chat, expand=True),
                ft.ElevatedButton("Send", on_click=send_room_msg),
            ]),
        ]

    def render_dms():
        body.controls = [
            ft.Text("Direct messages", size=16, weight=ft.FontWeight.BOLD),
            ft.Row([
                ft.Container(dm_to, expand=True),
                ft.ElevatedButton("Start", on_click=start_dm),
            ]),
            ft.Container(dm_log, bgcolor=ft.Colors.BLACK26, border_radius=6, padding=8),
            ft.Row([
                ft.Container(dm_body, expand=True),
                ft.ElevatedButton("Send", on_click=send_dm),
            ]),
        ]

    def render_groups():
        body.controls = [
            ft.Text("Groups", size=16, weight=ft.FontWeight.BOLD),
            ft.ElevatedButton("Refresh", on_click=load_groups),
            ft.Container(groups_log, bgcolor=ft.Colors.BLACK26, border_radius=6, padding=8),
        ]
        load_groups()

    def render_search():
        body.controls = [
            ft.Text("Search", size=16, weight=ft.FontWeight.BOLD),
            ft.Row([
                ft.Container(search_q, expand=True),
                ft.ElevatedButton("Search", on_click=run_search),
            ]),
            ft.Container(search_log, bgcolor=ft.Colors.BLACK26, border_radius=6, padding=8),
        ]

    def render_contacts():
        body.controls = [
            ft.Text("Contacts", size=16, weight=ft.FontWeight.BOLD),
            ft.ElevatedButton("Refresh", on_click=load_contacts),
            ft.Container(contacts_log, bgcolor=ft.Colors.BLACK26, border_radius=6, padding=8),
        ]
        load_contacts()

    def render_auth():
        body.controls = [
            ft.Text("Account", size=16, weight=ft.FontWeight.BOLD),
            auth_username, auth_email, auth_password,
            ft.Row([
                ft.ElevatedButton("Login", on_click=do_login),
                ft.OutlinedButton("Register", on_click=do_register),
            ]),
            ft.TextButton("Toggle email field", on_click=toggle_register),
            ft.ElevatedButton("Logout", on_click=do_logout),
        ]

    renderers = {
        "calc": render_calc,
        "live": render_live,
        "dms": render_dms,
        "groups": render_groups,
        "search": render_search,
        "contacts": render_contacts,
        "auth": render_auth,
    }

    def switch_tab(name):
        state.active_tab = name
        renderers[name]()
        page.update()

    def refresh_ui():
        renderers[state.active_tab]()
        page.update()

    page.navigation_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationDestination(icon=ft.Icons.CALCULATE, label="Calc"),
            ft.NavigationDestination(icon=ft.Icons.FORUM, label="Live"),
            ft.NavigationDestination(icon=ft.Icons.MAIL, label="DMs"),
            ft.NavigationDestination(icon=ft.Icons.GROUPS, label="Groups"),
            ft.NavigationDestination(icon=ft.Icons.SEARCH, label="Search"),
            ft.NavigationDestination(icon=ft.Icons.PEOPLE, label="Contacts"),
            ft.NavigationDestination(icon=ft.Icons.PERSON, label="Account"),
        ],
        selected_index=0,
        on_change=lambda e: switch_tab(
            ["calc", "live", "dms", "groups", "search", "contacts", "auth"][e.control.selected_index]
        ),
    )

    page.add(
        ft.Text("Arithmetic Super App", size=20, weight=ft.FontWeight.BOLD),
        ft.Text(API_BASE, size=11, color=ft.Colors.GREY),
        ft.Divider(),
        body,
        ft.Divider(),
        status,
        result,
    )

    renderers["calc"]()
    page.update()


if __name__ == "__main__":
    ft.app(target=main)
