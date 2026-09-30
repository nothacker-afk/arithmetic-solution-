

# =====================================================================
# Phase 89 — Linear equation solver
# =====================================================================
def solve_linear(equation: str, variable: str = "x") -> dict:
    """Solve a simple linear equation of the form a*x + b = c*x + d.

    Supports:
        "2x + 5 = 15"
        "3x - 7 = 2x + 3"
        "x/2 + 3 = 7"
        "-4x = 8"
    """
    if "=" not in equation:
        raise CalcError("Equation must contain '='")

    left, right = equation.split("=", 1)
    left = left.strip()
    right = right.strip()
    var = variable.strip()

    # Move everything to LHS - RHS = 0
    # Track coefficient of `var` and the constant term
    def parse_side(s):
        """Return (coef, const) for the given side."""
        # Normalize: insert explicit '*' between number and variable
        s = _re.sub(r"(\d)([a-zA-Z])", r"\1*\2", s)
        # Insert '*' between variable and number (e.g. x2 → x*2)
        s = _re.sub(r"([a-zA-Z])(\d)", r"\1*\2", s)
        # Remove spaces
        s = s.replace(" ", "")
        if not s:
            return 0.0, 0.0

        # Split into terms preserving sign
        terms = []
        buf = ""
        for i, ch in enumerate(s):
            if ch in "+-" and i > 0:
                terms.append(buf)
                buf = ch
            else:
                buf += ch
        if buf:
            terms.append(buf)

        coef, const = 0.0, 0.0
        for t in terms:
            t = t.strip()
            if not t:
                continue
            if var in t:
                # extract coefficient
                coef_str = t.replace(var, "")
                if coef_str in ("", "+"):
                    coef += 1.0
                elif coef_str == "-":
                    coef -= 1.0
                else:
                    try:
                        coef += float(coef_str)
                    except ValueError:
                        # complex term like x/2
                        numerator = coef_str.strip("*/")
                        if coef_str.startswith("/"):
                            coef += 1.0 / float(numerator)
                        elif coef_str.endswith("/"):
                            coef += float(numerator)
                        else:
                            raise CalcError(f"Cannot parse term: {t}")
            else:
                try:
                    const += float(t)
                except ValueError:
                    raise CalcError(f"Cannot parse term: {t}")
        return coef, const

    left_coef, left_const = parse_side(left)
    right_coef, right_const = parse_side(right)

    a = left_coef - right_coef
    b = right_const - left_const

    if abs(a) < 1e-15:
        if abs(b) < 1e-15:
            return {
                "solution": None, "variable": var,
                "message": "Infinite solutions (equation is an identity)",
                "steps": [_step("LHS - RHS = 0", "0 = 0", 0)],
            }
        return {
            "solution": None, "variable": var,
            "message": "No solution (contradiction)",
            "steps": [_step("LHS - RHS = 0", f"{b} = 0", b)],
        }

    solution = b / a

    steps = [
        _step("Move all variable terms to LHS, constants to RHS",
              f"{_fmt(a)}{var} = {_fmt(b)}", None),
        _step(f"Divide both sides by {_fmt(a)}",
              f"{var} = {_fmt(b)} / {_fmt(a)}", solution),
        _step("Solution", f"{var} = {_fmt(solution)}", solution),
    ]
    return {
        "solution": solution, "variable": var,
        "message": "Unique solution",
        "steps": steps,
        "coefficients": {"a": a, "b": b},
    }
