"""Calculation API (physics / engineering / cosmic support)."""
from __future__ import annotations
import inspect

from flask import Blueprint, request, jsonify

from .calc_engine import evaluate, solve_linear, CalcError
from .physics_constants import CONSTANTS, FORMULAS
from .rate_limit import rate_limit

calc_bp = Blueprint("calc", __name__, url_prefix="/api/calc")


@calc_bp.route("/expression", methods=["POST"])
@rate_limit(max_calls=120, window_seconds=60)
def expression():
    data = request.get_json(silent=True) or {}
    expr = (data.get("expression") or "").strip()
    extra = data.get("variables") or {}
    if not expr:
        return jsonify({"error": "expression is required"}), 400
    if len(expr) > 500:
        return jsonify({"error": "expression too long"}), 400
    try:
        clean_vars = {str(k): float(v) for k, v in extra.items()}
    except (TypeError, ValueError):
        return jsonify({"error": "variables must be numeric"}), 400
    try:
        result = evaluate(expr, extra_vars=clean_vars)
    except CalcError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Calculation error: {e}"}), 500
    return jsonify(result)


@calc_bp.route("/constants", methods=["GET"])
def constants():
    return jsonify({"constants": [
        {"name": k, "value": v, "value_str": f"{v:.6g}"}
        for k, v in sorted(CONSTANTS.items())
    ]})


@calc_bp.route("/formulas", methods=["GET"])
def formulas():
    out = []
    for name, fn in sorted(FORMULAS.items()):
        sig = inspect.signature(fn)
        args = [{"name": p.name,
                 "default": (p.default if p.default is not inspect.Parameter.empty else None),
                 "required": p.default is inspect.Parameter.empty}
                for p in sig.parameters.values()]
        doc = (fn.__doc__ or "").strip().splitlines()[0] if fn.__doc__ else ""
        out.append({"name": name, "signature": str(sig), "args": args, "doc": doc})
    return jsonify({"formulas": out})


@calc_bp.route("/formula", methods=["POST"])
@rate_limit(max_calls=120, window_seconds=60)
def formula():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    args = data.get("args") or {}
    if name not in FORMULAS:
        return jsonify({"error": f"Unknown formula: {name}"}), 404
    try:
        clean_args = {k: float(v) for k, v in args.items()}
    except (TypeError, ValueError):
        return jsonify({"error": "all args must be numeric"}), 400
    try:
        result = FORMULAS[name](**clean_args)
    except TypeError as e:
        return jsonify({"error": f"Wrong arguments: {e}"}), 400
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    result["name"] = name
    return jsonify(result)


@calc_bp.route("/solve", methods=["POST"])
@rate_limit(max_calls=60, window_seconds=60)
def solve():
    data = request.get_json(silent=True) or {}
    equation = (data.get("equation") or "").strip()
    variable = (data.get("variable") or "x").strip() or "x"
    if not equation:
        return jsonify({"error": "equation is required"}), 400
    if len(equation) > 500:
        return jsonify({"error": "equation too long"}), 400
    if len(variable) > 4:
        return jsonify({"error": "variable name too long"}), 400
    try:
        result = solve_linear(equation, variable)
    except CalcError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Solver error: {e}"}), 500
    result["equation"] = equation
    return jsonify(result)
