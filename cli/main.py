"""Interactive CLI calculator for Arithmetic Super App.

Provides a menu-driven interface for basic, scientific, and matrix
operations with a persistent history log.
"""
import json
import sys
from pathlib import Path

from arithmetic import (
    add, subtract, multiply, divide, power, modulo, floor_divide,
    sqrt, cbrt, log, ln, log10, sin, cos, tan, factorial, absolute,
    matrix_add, matrix_subtract, matrix_multiply, matrix_transpose,
)

HISTORY_FILE = Path.home() / ".arithmetic_history.json"


def _log(entry: dict) -> None:
    """Append an entry to the history file."""
    history = []
    if HISTORY_FILE.exists():
        try:
            history = json.loads(HISTORY_FILE.read_text())
        except json.JSONDecodeError:
            history = []
    history.append(entry)
    HISTORY_FILE.write_text(json.dumps(history, indent=2))


def _show_history() -> None:
    """Display the full calculation history."""
    if not HISTORY_FILE.exists():
        sys.stderr.write("No history yet.\n")
        return
    try:
        history = json.loads(HISTORY_FILE.read_text())
    except json.JSONDecodeError:
        sys.stderr.write("History file is corrupted.\n")
        return
    if not history:
        sys.stderr.write("No history yet.\n")
        return
    sys.stderr.write("\n--- Calculation History ---\n")
    for i, entry in enumerate(history, 1):
        sys.stderr.write(f"{i:3}. {entry['expression']} = {entry['result']}\n")
    sys.stderr.write("---------------------------\n\n")


def _clear_history() -> None:
    """Delete the history file."""
    if HISTORY_FILE.exists():
        HISTORY_FILE.unlink()
    sys.stderr.write("History cleared.\n")


def _get_float(prompt: str) -> float:
    """Prompt for a numeric value."""
    while True:
        try:
            return float(input(prompt))
        except ValueError:
            sys.stderr.write("Invalid number. Try again.\n")


def _get_matrix(prompt: str) -> list:
    """Prompt for a matrix using 'a,b;c,d' syntax."""
    while True:
        raw = input(prompt).strip()
        try:
            rows = raw.split(";")
            matrix = [[float(x) for x in row.split(",")] for row in rows]
            return matrix
        except ValueError:
            sys.stderr.write("Invalid matrix. Use format: 1,2;3,4\n")


def _basic_menu() -> None:
    sys.stderr.write("\n--- Basic Operations ---\n")
    sys.stderr.write("1. Add\n2. Subtract\n3. Multiply\n4. Divide\n")
    sys.stderr.write("5. Power\n6. Modulo\n7. Floor Divide\n")
    choice = input("Select (1-7): ").strip()

    ops = {
        "1": ("+", add), "2": ("-", subtract), "3": ("*", multiply),
        "4": ("/", divide), "5": ("**", power), "6": ("%", modulo),
        "7": ("//", floor_divide),
    }
    if choice not in ops:
        sys.stderr.write("Invalid choice.\n")
        return

    symbol, func = ops[choice]
    a = _get_float("Enter a: ")
    b = _get_float("Enter b: ")
    try:
        result = func(a, b)
        expression = f"{a} {symbol} {b}"
        sys.stderr.write(f"\n  {expression} = {result}\n")
        _log({"expression": expression, "result": result})
    except ValueError as e:
        sys.stderr.write(f"Error: {e}\n")


def _scientific_menu() -> None:
    sys.stderr.write("\n--- Scientific Operations ---\n")
    sys.stderr.write("1. sqrt\n2. cbrt\n3. log (base 10)\n4. ln\n")
    sys.stderr.write("5. sin\n6. cos\n7. tan\n8. factorial\n9. absolute\n")
    choice = input("Select (1-9): ").strip()

    single_arg = {
        "1": ("sqrt", sqrt), "2": ("cbrt", cbrt), "3": ("log10", log10),
        "4": ("ln", ln), "5": ("sin", sin), "6": ("cos", cos),
        "7": ("tan", tan), "8": ("factorial", factorial), "9": ("abs", absolute),
    }
    if choice not in single_arg:
        sys.stderr.write("Invalid choice.\n")
        return

    name, func = single_arg[choice]
    if name == "factorial":
        raw = input("Enter n (integer): ")
        try:
            n = int(raw)
        except ValueError:
            sys.stderr.write("Must be an integer.\n")
            return
        try:
            result = func(n)
            expression = f"factorial({n})"
            sys.stderr.write(f"\n  {expression} = {result}\n")
            _log({"expression": expression, "result": result})
        except ValueError as e:
            sys.stderr.write(f"Error: {e}\n")
        return

    x = _get_float("Enter x: ")
    try:
        result = func(x)
        expression = f"{name}({x})"
        sys.stderr.write(f"\n  {expression} = {result}\n")
        _log({"expression": expression, "result": result})
    except ValueError as e:
        sys.stderr.write(f"Error: {e}\n")


def _matrix_menu() -> None:
    sys.stderr.write("\n--- Matrix Operations ---\n")
    sys.stderr.write("1. Add\n2. Subtract\n3. Multiply\n4. Transpose\n")
    choice = input("Select (1-4): ").strip()

    if choice == "4":
        a = _get_matrix("Matrix A (e.g. 1,2;3,4): ")
        try:
            result = matrix_transpose(a)
            sys.stderr.write(f"\n  transpose(A) = {result}\n")
            _log({"expression": f"transpose({a})", "result": result})
        except ValueError as e:
            sys.stderr.write(f"Error: {e}\n")
        return

    ops = {
        "1": ("matrix_add", matrix_add), "2": ("matrix_subtract", matrix_subtract),
        "3": ("matrix_multiply", matrix_multiply),
    }
    if choice not in ops:
        sys.stderr.write("Invalid choice.\n")
        return

    name, func = ops[choice]
    a = _get_matrix("Matrix A (e.g. 1,2;3,4): ")
    b = _get_matrix("Matrix B (e.g. 5,6;7,8): ")
    try:
        result = func(a, b)
        expression = f"{name}({a}, {b})"
        sys.stderr.write(f"\n  {name}(A, B) = {result}\n")
        _log({"expression": expression, "result": result})
    except ValueError as e:
        sys.stderr.write(f"Error: {e}\n")


def main() -> None:
    """Main interactive loop."""
    sys.stderr.write("\n=== Arithmetic Super App — CLI ===\n")
    while True:
        sys.stderr.write("\nMain Menu\n")
        sys.stderr.write("1. Basic operations\n")
        sys.stderr.write("2. Scientific operations\n")
        sys.stderr.write("3. Matrix operations\n")
        sys.stderr.write("4. View history\n")
        sys.stderr.write("5. Clear history\n")
        sys.stderr.write("q. Quit\n")
        choice = input("Choose: ").strip().lower()

        if choice == "1":
            _basic_menu()
        elif choice == "2":
            _scientific_menu()
        elif choice == "3":
            _matrix_menu()
        elif choice == "4":
            _show_history()
        elif choice == "5":
            _clear_history()
        elif choice == "q":
            sys.stderr.write("Goodbye!\n")
            break
        else:
            sys.stderr.write("Invalid option.\n")


if __name__ == "__main__":
    main()
