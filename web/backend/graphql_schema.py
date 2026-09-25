"""GraphQL schema for Arithmetic Super App (Strawberry).

Mounted at POST/GET /graphql (playground at /graphql in browser).

REST remains the primary API. GraphQL is offered as an alternative for
clients that prefer typed queries and single-endpoint fetches.
"""
from datetime import datetime
from typing import List, Optional

import strawberry
from strawberry.types import Info

from arithmetic import (
    add, subtract, multiply, divide, power, modulo, floor_divide,
    sqrt, cbrt, log10, sin, cos, tan, factorial, absolute,
    matrix_add, matrix_subtract, matrix_multiply, matrix_transpose,
    plugins,
)

BASIC = {
    "add": add, "subtract": subtract, "multiply": multiply, "divide": divide,
    "power": power, "modulo": modulo, "floor_divide": floor_divide,
}
UNARY = {
    "sqrt": sqrt, "cbrt": cbrt, "log10": log10, "sin": sin, "cos": cos,
    "tan": tan, "factorial": factorial, "absolute": absolute,
}
def _fmt_num(x):
    """Format a number, dropping .0 for whole floats."""
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    return str(x)


def _fmt_matrix(m):
    """Format a matrix so whole floats display as ints."""
    return "[" + ", ".join(
        "[" + ", ".join(_fmt_num(c) for c in row) + "]"
        for row in m
    ) + "]"


def _fmt_value(x):
    """Format a numeric or matrix result for display."""
    if isinstance(x, list):
        return _fmt_matrix(x)
    return _fmt_num(x)


MATRIX = {
    "matrix_add": matrix_add, "matrix_subtract": matrix_subtract,
    "matrix_multiply": matrix_multiply, "matrix_transpose": matrix_transpose,
}


# ---------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------
@strawberry.type
class CalcResult:
    expression: str
    result: str
    operation: Optional[str] = None


@strawberry.type
class PluginInfo:
    name: str
    arity: int
    doc: str


# ---------------------------------------------------------------------
# Query
# ---------------------------------------------------------------------
@strawberry.type
class Query:
    @strawberry.field
    def health(self) -> str:
        return "ok"

    @strawberry.field
    def version(self) -> str:
        return "0.8.0"

    @strawberry.field
    def plugins(self) -> List[PluginInfo]:
        return [
            PluginInfo(name=p["name"], arity=p["arity"], doc=p["doc"])
            for p in plugins.list_plugins()
        ]

    @strawberry.field
    def basic(self, operation: str, a: float, b: float) -> CalcResult:
        """Stateless basic arithmetic — exposed as a query for convenience."""
        if operation not in BASIC:
            raise ValueError(f"Unknown operation: {operation}")
        try:
            result = BASIC[operation](a, b)
        except ValueError as e:
            raise ValueError(str(e))
        return CalcResult(
            expression=f"{a} {operation} {b}",
            result=_fmt_value(result),
            operation=operation,
        )


# ---------------------------------------------------------------------
# Mutation
# ---------------------------------------------------------------------
@strawberry.type
class Mutation:
    @strawberry.mutation
    def basic(self, operation: str, a: float, b: float) -> CalcResult:
        if operation not in BASIC:
            raise ValueError(f"Unknown operation: {operation}")
        try:
            result = BASIC[operation](a, b)
        except ValueError as e:
            raise ValueError(str(e))
        return CalcResult(
            expression=f"{a} {operation} {b}",
            result=_fmt_value(result),
            operation=operation,
        )

    @strawberry.mutation
    def scientific(self, operation: str, x: float) -> CalcResult:
        if operation not in UNARY:
            raise ValueError(f"Unknown operation: {operation}")
        try:
            result = UNARY[operation](x)
        except ValueError as e:
            raise ValueError(str(e))
        return CalcResult(
            expression=f"{operation}({x})",
            result=_fmt_value(result),
            operation=operation,
        )

    @strawberry.mutation
    def matrix(
        self,
        operation: str,
        a: List[List[float]],
        b: Optional[List[List[float]]] = None,
    ) -> CalcResult:
        try:
            if operation == "matrix_transpose":
                result = matrix_transpose(a)
            elif operation in MATRIX:
                if b is None:
                    raise ValueError("matrix b is required")
                result = MATRIX[operation](a, b)
            else:
                raise ValueError(f"Unknown operation: {operation}")
        except ValueError as e:
            raise ValueError(str(e))
        return CalcResult(
            expression=operation,
            result=_fmt_value(result),
            operation=operation,
        )

    @strawberry.mutation
    def call_plugin(self, name: str, args: List[float]) -> CalcResult:
        try:
            result = plugins.call(name, *args)
        except plugins.PluginError as e:
            raise ValueError(str(e))
        return CalcResult(
            expression=f"{name}({', '.join(str(x) for x in args)})",
            result=_fmt_value(result),
            operation=name,
        )

    @strawberry.mutation
    def ai_solve(self, text: str) -> CalcResult:
        try:
            from ai_engine import parse_and_solve, ParseError
        except ImportError:
            raise ValueError("AI engine not available")
        try:
            r = parse_and_solve(text)
        except ParseError as e:
            raise ValueError(str(e))
        return CalcResult(
            expression=r["expression"],
            result=str(r["result"]),
            operation=r["operation"],
        )


schema = strawberry.Schema(query=Query, mutation=Mutation)
