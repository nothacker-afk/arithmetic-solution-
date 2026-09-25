"""Tests for the plugin registry."""
import pytest
from arithmetic import plugins
from arithmetic.plugins import (
    call, register_binary, register_unary, unregister,
    list_plugins, PluginError,
)


def test_builtin_gcd():
    assert call("gcd", 12, 18) == 6
    assert call("gcd", 17, 5) == 1


def test_builtin_lcm():
    assert call("lcm", 4, 6) == 12
    assert call("lcm", 0, 5) == 0


def test_builtin_sign():
    assert call("sign", -42) == -1
    assert call("sign", 0) == 0
    assert call("sign", 3.14) == 1


def test_builtin_average():
    assert call("average", 10, 20) == 15.0


def test_unknown_plugin():
    with pytest.raises(PluginError):
        call("does_not_exist", 1, 2)


def test_wrong_arity():
    with pytest.raises(PluginError):
        call("gcd", 5)  # gcd needs 2 args
    with pytest.raises(PluginError):
        call("sign", 1, 2)  # sign needs 1 arg


def test_register_custom_binary():
    @register_binary("double_sum_test")
    def double_sum(a, b):
        return (a + b) * 2

    try:
        assert call("double_sum_test", 3, 4) == 14
    finally:
        unregister("double_sum_test")


def test_register_custom_unary():
    @register_unary("square_test")
    def square(x):
        return x * x

    try:
        assert call("square_test", 5) == 25
    finally:
        unregister("square_test")


def test_duplicate_registration():
    with pytest.raises(PluginError):
        @register_binary("gcd")
        def another_gcd(a, b):
            return 0


def test_list_plugins():
    plugins_list = list_plugins()
    names = [p["name"] for p in plugins_list]
    assert "gcd" in names
    assert "lcm" in names
    assert "sign" in names
    assert "average" in names
