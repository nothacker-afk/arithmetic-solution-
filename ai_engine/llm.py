"""Optional LLM-powered parser using OpenAI.

This module is only used if the OPENAI_API_KEY environment variable is set.
If it isn't, the system falls back to the rule-based parser in parser.py.
"""
import json
import os
from typing import Any, Dict

from .parser import parse_and_solve, ParseError

# Module-level import so tests can patch `ai_engine.llm.OpenAI`.
try:
    from openai import OpenAI  # type: ignore
    _OPENAI_AVAILABLE = True
except ImportError:
    OpenAI = None  # type: ignore
    _OPENAI_AVAILABLE = False


def is_llm_available() -> bool:
    """Return True if the openai package is installed and OPENAI_API_KEY is set."""
    return _OPENAI_AVAILABLE and bool(os.environ.get("OPENAI_API_KEY"))


SYSTEM_PROMPT = (
    "You are an arithmetic parser. Convert the user's natural-language math "
    "question into a JSON object with exactly these keys:\n"
    '  "operation": one of '
    "[add, subtract, multiply, divide, power, modulo, percent_of, "
    "sqrt, cbrt, log10, sin, cos, tan, factorial, absolute]\n"
    '  "operands": array of numbers (2 for binary, 1 for unary)\n'
    "Respond with JSON only, no explanation."
)


def llm_solve(text: str) -> Dict[str, Any]:
    """Parse `text` with an LLM, then execute it locally.

    Falls back to the rule-based parser if OpenAI isn't available or
    the API call fails.
    """
    if not is_llm_available():
        return parse_and_solve(text)

    try:
        client = OpenAI()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        payload = json.loads(response.choices[0].message.content)
    except Exception:
        # Network error, bad key, rate limit, etc. — fall back
        return parse_and_solve(text)

    # Reconstruct the operation using the local engine
    op = payload.get("operation")
    operands = payload.get("operands", [])

    # Map operation name to the local parser's keyword form
    keyword_map = {
        "add": "add", "subtract": "subtract", "multiply": "multiply",
        "divide": "divide", "power": "power", "modulo": "modulo",
        "percent_of": "percent_of", "sqrt": "sqrt", "cbrt": "cbrt",
        "log10": "log10", "sin": "sin", "cos": "cos", "tan": "tan",
        "factorial": "factorial", "absolute": "absolute",
    }
    if op not in keyword_map or not operands:
        return parse_and_solve(text)

    try:
        if op == "percent_of" and len(operands) == 2:
            # Rebuild as "% of" phrase
            return parse_and_solve(f"{operands[0]}% of {operands[1]}")
        if len(operands) == 2:
            return parse_and_solve(f"{operands[0]} {op} {operands[1]}")
        if len(operands) == 1:
            return parse_and_solve(f"{op} of {operands[0]}")
    except ParseError:
        pass

    return parse_and_solve(text)
