"""Arithmetic Super App — Flet cross-platform client.

Run modes:
    Desktop:  flet run mobile/app.py
    Web:      flet run --web --port 8550 mobile/app.py
    Mobile:   APK built via .github/workflows/build-apk.yml

Requires the Flask backend to be running for auth/history features.
"""
import flet as ft
import requests

API_BASE = "http://localhost:8000"


class AppState:
    def __init__(self):
        self.token: str | None = None
        self.username: str | None = None


def main(page: ft.Page):
    page.title = "Arithmetic Super App"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 20
    page.window_width = 420
    page.window_height = 720

    state = AppState()

    # --- UI elements -----------------------------------------------------
    result_text = ft.Text("Ready.", size=18, selectable=True)
    a_field = ft.TextField(label="a", value="10", keyboard_type=ft.KeyboardType.NUMBER)
    b_field = ft.TextField(label="b", value="5", keyboard_type=ft.KeyboardType.NUMBER)

    op_dropdown = ft.Dropdown(
        label="Operation",
        options=[
            ft.dropdown.Option("add", "Add (+)"),
            ft.dropdown.Option("subtract", "Subtract (-)"),
            ft.dropdown.Option("multiply", "Multiply (*)"),
            ft.dropdown.Option("divide", "Divide (/)"),
            ft.dropdown.Option("power", "Power (^)"),
            ft.dropdown.Option("modulo", "Modulo (%)"),
        ],
        value="add",
    )

    def call_basic(e):
        try:
            a = float(a_field.value)
            b = float(b_field.value)
        except ValueError:
            result_text.value = "Enter valid numbers."
            page.update()
            return
        try:
            r = requests.post(f"{API_BASE}/api/basic", json={
                "operation": op_dropdown.value, "a": a, "b": b,
            }, timeout=5)
            data = r.json()
            if r.ok:
                result_text.value = f"{data['expression']} = {data['result']}"
            else:
                result_text.value = f"Error: {data.get('error')}"
        except requests.RequestException as err:
            result_text.value = f"Backend unreachable: {err}"
        page.update()

    def call_scientific(op):
        def handler(e):
            try:
                x = float(a_field.value)
            except ValueError:
                result_text.value = "Enter a valid number in 'a'."
                page.update()
                return
            try:
                r = requests.post(f"{API_BASE}/api/scientific",
                                  json={"operation": op, "x": x}, timeout=5)
                data = r.json()
                result_text.value = (
                    f"{data['expression']} = {data['result']}"
                    if r.ok else f"Error: {data.get('error')}"
                )
            except requests.RequestException as err:
                result_text.value = f"Backend unreachable: {err}"
            page.update()
        return handler

    def call_ai(e):
        text = ai_field.value.strip()
        if not text:
            return
        try:
            r = requests.post(f"{API_BASE}/api/ai", json={"text": text}, timeout=5)
            data = r.json()
            result_text.value = (
                f"{data['expression']} = {data['result']}"
                if r.ok else f"Error: {data.get('error')}"
            )
        except requests.RequestException as err:
            result_text.value = f"Backend unreachable: {err}"
        page.update()

    ai_field = ft.TextField(
        label="Ask in plain English",
        hint_text="e.g. what is 15% of 240",
    )

    # --- Layout ---------------------------------------------------------
    page.add(
        ft.Text("Arithmetic Super App", size=26, weight=ft.FontWeight.BOLD),
        ft.Text("Mobile client (Flet)", size=12, color=ft.Colors.GREY),
        ft.Divider(),
        op_dropdown,
        a_field,
        b_field,
        ft.Row([
            ft.ElevatedButton("Calculate", on_click=call_basic),
        ]),
        ft.Divider(),
        ft.Text("Scientific (uses 'a')", weight=ft.FontWeight.BOLD),
        ft.Row([
            ft.OutlinedButton("sqrt", on_click=call_scientific("sqrt")),
            ft.OutlinedButton("cbrt", on_click=call_scientific("cbrt")),
            ft.OutlinedButton("log10", on_click=call_scientific("log10")),
        ]),
        ft.Row([
            ft.OutlinedButton("sin", on_click=call_scientific("sin")),
            ft.OutlinedButton("cos", on_click=call_scientific("cos")),
            ft.OutlinedButton("tan", on_click=call_scientific("tan")),
        ]),
        ft.Row([
            ft.OutlinedButton("factorial", on_click=call_scientific("factorial")),
            ft.OutlinedButton("abs", on_click=call_scientific("absolute")),
        ]),
        ft.Divider(),
        ft.Text("Natural language (AI)", weight=ft.FontWeight.BOLD),
        ai_field,
        ft.ElevatedButton("Solve", on_click=call_ai),
        ft.Divider(),
        result_text,
    )


if __name__ == "__main__":
    ft.app(target=main)
