"""Plugin registry for Arithmetic Super App.

Allows third parties to register custom operations without modifying
the core package. Plugins can be binary (2 args) or unary (1 arg).

Example:
    from arithmetic.plugins import register_binary

    @register_binary("gcd")
    def gcd(a, b):
        while b:
            a, b = b, a % b
        return a

    from arithmetic.plugins import call
    call("gcd", 12, 18)  # -> 6
"""
from typing import Any, Callable, Dict

# name -> (func, arity)  arity = 1 for unary, 2 for binary
REGISTRY: Dict[str, tuple[Callable, int]] = {}


class PluginError(ValueError):
    pass


def register_binary(name: str):
    """Decorator: register a two-argument operation."""
    def decorator(fn: Callable) -> Callable:
        if name in REGISTRY:
            raise PluginError(f"Plugin name already registered: {name}")
        REGISTRY[name] = (fn, 2)
        return fn
    return decorator


def register_unary(name: str):
    """Decorator: register a one-argument operation."""
    def decorator(fn: Callable) -> Callable:
        if name in REGISTRY:
            raise PluginError(f"Plugin name already registered: {name}")
        REGISTRY[name] = (fn, 1)
        return fn
    return decorator


def unregister(name: str) -> None:
    """Remove a plugin (mostly for tests)."""
    REGISTRY.pop(name, None)


def list_plugins() -> list[dict]:
    """Return metadata for all registered plugins."""
    return [
        {"name": name, "arity": arity, "doc": (fn.__doc__ or "").strip()}
        for name, (fn, arity) in REGISTRY.items()
    ]


def call(name: str, *args) -> Any:
    """Invoke a registered plugin. Raises PluginError if unknown or wrong arity."""
    if name not in REGISTRY:
        raise PluginError(f"Unknown plugin: {name}")
    fn, arity = REGISTRY[name]
    if len(args) != arity:
        raise PluginError(
            f"Plugin '{name}' expects {arity} argument(s), got {len(args)}"
        )
    return fn(*args)


# ---------------------------------------------------------------------
# Built-in example plugins (auto-registered on import)
# ---------------------------------------------------------------------
@register_binary("gcd")
def _gcd(a, b):
    """Greatest common divisor of two integers."""
    a, b = abs(int(a)), abs(int(b))
    while b:
        a, b = b, a % b
    return a


@register_binary("lcm")
def _lcm(a, b):
    """Least common multiple of two integers."""
    a, b = abs(int(a)), abs(int(b))
    if a == 0 or b == 0:
        return 0
    return a * b // _gcd(a, b)


@register_unary("sign")
def _sign(x):
    """Return -1, 0, or 1 depending on the sign of x."""
    return (x > 0) - (x < 0)


@register_binary("average")
def _average(a, b):
    """Arithmetic mean of two numbers."""
    return (a + b) / 2
