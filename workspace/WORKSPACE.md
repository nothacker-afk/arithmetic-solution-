# Workspace

This repo ships as a monorepo. Each top-level subproject is independently
runnable, testable, and packageable. `workspace/` contains the tooling
that ties them together.

## Subprojects

| Path | Purpose | Entry |
|------|---------|-------|
| `arithmetic/` | Core math engine + plugins | `python -c "from arithmetic import add"` |
| `ai_engine/`   | Rule-based NLP + optional LLM | `python -m ai_engine.cli` |
| `cli/`         | Interactive CLI + account tools | `python -m cli.main` |
| `web/`         | Flask + WebSocket server + frontend | `python -m web.backend.main` |
| `mobile/`      | Flet cross-platform client | `flet run mobile/app.py` |
| `arith/`       | Unified CLI (`arith`) | `arith <cmd>` |
| `alembic/`     | Schema migrations | `alembic upgrade head` |
| `k8s/`, `helm/` | Deployment manifests | `kubectl apply -f k8s/` |
| `docker/`      | Container images | `docker compose up` |

## Task runner

The `arith` CLI (from `arith/`) is the primary front door:

    arith serve          # start the web server
    arith cli            # interactive calculator
    arith ai             # natural-language CLI
    arith account ...    # data ownership ops
    arith doctor         # environment diagnostics
    arith help           # show all commands

Additional workspace targets are available via Makefile:

    make test            # run the full test suite
    make cov             # coverage report
    make run             # alias for arith serve
    make clean           # clean caches

## Running subprojects in isolation

Every subproject has its own dependencies listed in the root
`pyproject.toml` under `[project.optional-dependencies]`:

    pip install -e ".[dev]"          # core + tests
    pip install -e ".[web]"          # + Flask stack
    pip install -e ".[ai]"           # + OpenAI SDK
    pip install -e ".[mobile]"       # + Flet
    pip install -e ".[postgres]"     # + PostgreSQL
    pip install -e ".[observability]" # + OpenTelemetry
    pip install -e ".[passkeys]"     # + WebAuthn
    pip install -e ".[notifications]" # + google-auth

Combine extras: `pip install -e ".[dev,web,ai]"`.

## CI matrix

GitHub Actions workflows in `.github/workflows/`:

- `ci.yml` — runs pytest on Python 3.10/3.11/3.12
- `coverage.yml` — collects coverage.xml
- `build-apk.yml` — builds the Flet mobile APK
- `publish-pypi.yml` — publishes on git tag
- `publish-docker.yml` — publishes the container on git tag

## Adding a subproject

1. Create a directory at repo root.
2. Add any console scripts to `[project.scripts]` in pyproject.toml.
3. Add optional dependencies under `[project.optional-dependencies]`.
4. Add a `test_*.py` in `tests/` so CI picks it up.
5. Update this file.
