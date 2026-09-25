"""Interactive natural-language arithmetic CLI with persistent history.

Usage:
    python -m ai_engine.cli
"""
import json
import sys
from pathlib import Path

from .llm import llm_solve, is_llm_available
from .parser import parse_and_solve, ParseError

HISTORY_FILE = Path.home() / ".arithmetic_ai_history.json"


def _log(entry: dict) -> None:
    history = []
    if HISTORY_FILE.exists():
        try:
            history = json.loads(HISTORY_FILE.read_text())
        except json.JSONDecodeError:
            history = []
    history.append(entry)
    HISTORY_FILE.write_text(json.dumps(history, indent=2))


def _show_history() -> None:
    if not HISTORY_FILE.exists():
        sys.stderr.write("  No history yet.\n\n")
        return
    try:
        history = json.loads(HISTORY_FILE.read_text())
    except json.JSONDecodeError:
        sys.stderr.write("  History file corrupted.\n\n")
        return
    if not history:
        sys.stderr.write("  No history yet.\n\n")
        return
    sys.stderr.write("\n  --- AI History ---\n")
    for i, e in enumerate(history, 1):
        sys.stderr.write(f"  {i:3}. {e['input']}\n")
        sys.stderr.write(f"       -> {e['expression']} = {e['result']}\n")
    sys.stderr.write("  ------------------\n\n")


def _clear_history() -> None:
    if HISTORY_FILE.exists():
        HISTORY_FILE.unlink()
    sys.stderr.write("  History cleared.\n\n")


def main() -> None:
    engine = "LLM + rule-based" if is_llm_available() else "rule-based (offline)"
    sys.stderr.write("\n=== Arithmetic Super App — AI Mode ===\n")
    sys.stderr.write(f"Engine: {engine}\n")
    sys.stderr.write("Commands: 'history' · 'clear' · 'q' to quit\n")
    sys.stderr.write("Examples:\n")
    sys.stderr.write("  add 5 and 3\n")
    sys.stderr.write("  what is 15% of 240\n")
    sys.stderr.write("  square root of 81\n")
    sys.stderr.write("  factorial of 6\n")
    sys.stderr.write("  2 to the power of 10\n\n")

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            sys.stderr.write("\nGoodbye!\n")
            break

        if not line:
            continue

        low = line.lower()
        if low in ("q", "quit", "exit"):
            sys.stderr.write("Goodbye!\n")
            break
        if low == "history":
            _show_history()
            continue
        if low == "clear":
            _clear_history()
            continue

        try:
            result = llm_solve(line)
            sys.stderr.write(f"  {result['expression']} = {result['result']}\n\n")
            _log({
                "input": line,
                "expression": result["expression"],
                "result": result["result"],
                "operation": result["operation"],
            })
        except ParseError as e:
            sys.stderr.write(f"  Could not parse: {e}\n\n")
        except Exception as e:
            sys.stderr.write(f"  Error: {e}\n\n")


if __name__ == "__main__":
    main()
