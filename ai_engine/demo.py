"""Non-interactive demo of the AI engine.

Run with:
    python -m ai_engine.demo
"""
import sys
from .parser import parse_and_solve, ParseError

SAMPLES = [
    "add 5 and 3",
    "subtract 3 from 10",
    "multiply 4 by 7",
    "10 divided by 4",
    "what is 15% of 240",
    "square root of 81",
    "cube root of 27",
    "factorial of 6",
    "2 to the power of 10",
    "sin of 0",
    "cos of 0",
    "tan of 0",
    "absolute value of -42",
    "17 mod 5",
]


def main() -> None:
    sys.stderr.write("\n=== AI Engine Demo — %d samples ===\n\n" % len(SAMPLES))
    ok = 0
    for phrase in SAMPLES:
        try:
            r = parse_and_solve(phrase)
            sys.stderr.write(f"  {phrase:35s}  ->  {r['expression']} = {r['result']}\n")
            ok += 1
        except ParseError as e:
            sys.stderr.write(f"  {phrase:35s}  ->  ERROR: {e}\n")
    sys.stderr.write(f"\n  {ok}/{len(SAMPLES)} parsed successfully.\n\n")


if __name__ == "__main__":
    main()
