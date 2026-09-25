"""Interactive natural-language arithmetic CLI.

Usage:
    python -m ai_engine.cli
"""
import sys

from .llm import llm_solve, is_llm_available
from .parser import parse_and_solve, ParseError


def main() -> None:
    engine = "LLM + rule-based" if is_llm_available() else "rule-based (offline)"
    sys.stderr.write("\n=== Arithmetic Super App — AI Mode ===\n")
    sys.stderr.write(f"Engine: {engine}\n")
    sys.stderr.write("Type math in plain English. Examples:\n")
    sys.stderr.write("  add 5 and 3\n")
    sys.stderr.write("  what is 15% of 240\n")
    sys.stderr.write("  square root of 81\n")
    sys.stderr.write("  factorial of 6\n")
    sys.stderr.write("Type 'q' to quit.\n\n")

    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            sys.stderr.write("\nGoodbye!\n")
            break

        if not line:
            continue
        if line.lower() in ("q", "quit", "exit"):
            sys.stderr.write("Goodbye!\n")
            break

        try:
            result = llm_solve(line)
            sys.stderr.write(f"  {result['expression']} = {result['result']}\n\n")
        except ParseError as e:
            sys.stderr.write(f"  Could not parse: {e}\n\n")
        except Exception as e:
            sys.stderr.write(f"  Error: {e}\n\n")


if __name__ == "__main__":
    main()
