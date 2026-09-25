# Contributing

Thanks for your interest in Arithmetic Super App!

## Development Setup

    git clone https://github.com/nothacker-afk/arithmetic-solution-.git
    cd arithmetic-solution-
    pip install -e ".[dev,web]"
    pytest

## Adding a New Plugin

    from arithmetic.plugins import register_binary

    @register_binary("my_op")
    def my_op(a, b):
        """Describe what it does."""
        return a + b

Plugins are auto-listed at `GET /api/plugins` and callable at
`POST /api/plugins/my_op`.

## Adding a New Core Operation

1. Add the function to `arithmetic/basic.py`, `scientific.py`, or `matrix.py`.
2. Export it from `arithmetic/__init__.py`.
3. Add tests to the appropriate `tests/test_*.py`.
4. If it should be reachable via HTTP, wire it into `web/backend/main.py`.

## Running Tests

    pytest -v                    # all tests
    pytest --cov                 # with coverage
    pytest tests/test_basic.py   # single file

## Pull Request Checklist

- [ ] Tests pass locally (`pytest`)
- [ ] New features have tests
- [ ] Version bumped in `pyproject.toml` if releasing
- [ ] README updated if user-facing behavior changed
