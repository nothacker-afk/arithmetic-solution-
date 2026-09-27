# Service contracts

Every subproject exposes one of these interfaces:

## `arithmetic/`

Pure functions. No I/O, no network, no disk. Safe to import anywhere.

    from arithmetic import add, sqrt, matrix_multiply, plugins

## `ai_engine/`

Pure functions + optional outbound HTTP (OpenAI). Never blocks on
network for the rule-based path.

    from ai_engine import parse_and_solve

## `cli/`, `arith/`

Read from stdin / argv. Write to stdout / stderr. Exit codes:
0 = success, 1 = runtime error, 2 = usage error.

## `web/backend/`

Flask app + SocketIO. All state in SQLite (or PostgreSQL). Endpoints:
- `/api/*` for JSON
- `/graphql` for GraphQL
- `/metrics` for Prometheus
- `/api/events/stream` for SSE fallback
- `/socket.io/` for WebSocket

## `web/frontend/`

Static assets. No build step. Loaded from `/static/...`.

## `mobile/`

Flet app. Talks to `web/backend` over HTTP + WebSocket. Configure
`API_BASE` at the top of `mobile/app.py`.
