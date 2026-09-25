"""AI engine for Arithmetic Super App.

Provides natural-language parsing of math problems and dispatches them
to the core arithmetic package.
"""
from .parser import parse_and_solve, ParseError
from .llm import llm_solve, is_llm_available

__all__ = ["parse_and_solve", "ParseError", "llm_solve", "is_llm_available"]
