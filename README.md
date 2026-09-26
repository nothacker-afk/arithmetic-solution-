# Arithmetic Super App

A modular arithmetic engine supporting basic, scientific, and matrix operations.

## Installation

    pip install -e .

## Usage

    from arithmetic import add, sqrt, matrix_multiply
    print(add(2, 3))
    print(sqrt(16))
    print(matrix_multiply([[1, 2]], [[3], [4]]))

## Development

    pip install -e ".[dev]"
    pytest

---

## Multi-Room Chat + End-to-End Encryption

Each real-time collaboration room has an optional text chat channel.

### Plain mode

Messages are stored as-is in SQLite and broadcast live to everyone in
the room. Useful for quick coordination.

### E2E mode

Toggle **Encrypt (E2E)** and set a shared room passphrase. Messages are
encrypted in the browser using AES-GCM 256-bit with a key derived via
PBKDF2(SHA-256, 100k iterations). The server only ever sees and stores
base64 ciphertext — it cannot read messages even if the database leaks.

| Feature | Plain | E2E |
|---------|-------|-----|
| Server can read messages | yes | **no** |
| Persisted in DB | plaintext | ciphertext |
| New members need passphrase | no | yes |
| Works with any browser | yes | modern browsers (WebCrypto) |

### Chat REST API

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/chat/<room>?limit=50` | List recent messages (oldest first) |
| POST | `/api/chat/<room>` | Post a message |
| DELETE | `/api/chat/<room>` | Clear room history |

### Chat WebSocket events

| Event | Direction | Payload |
|-------|-----------|---------|
| `chat_send` | client → server | `{room, username, body, encrypted, id}` |
| `chat_message` | server → room | `{username, body, encrypted, id}` |
| `typing_start` | client → server | `{room, username}` |
| `typing_stop` | client → server | `{room, username}` |
| `typing` | server → room | `{username, state: "start"\|"stop"}` |

## Admin Dashboard

Visit `/admin` after logging in as the admin user (default: the first
registered user, id=1). Set `ADMIN_USER_ID` env var to override.

The dashboard shows:

- Aggregate stats (users, rooms, memberships, messages, files, calcs, audit)
- Server info (version, Python, platform, DB backend, uptime)
- Recent users with room + calc counts
- Registered rooms with owner, member/msg/file counts
- Full audit log with filters (actor, action, status)
- Danger zone: clear audit log

All endpoints under `/api/admin/*` require an admin Bearer token.

## Data Ownership & Privacy

Phase 17 gives users full control of their data.

### Data summary

    GET /api/account/data-summary

Returns aggregate counts of what the server holds for the authenticated
user, plus the documented retention policy for each data class.

### Full export

    GET /api/account/export?format=json
    GET /api/account/export?format=zip

Downloads every row we have for that user. The ZIP includes the JSON
plus the raw encrypted blobs of any file they uploaded to rooms.

### Account deletion

    DELETE /api/account  {"password": "...", "confirm": "DELETE"}

Irreversible. Cascade behavior:

| Data | Action |
|------|--------|
| Calculations, memberships, preferences | deleted (FK cascade) |
| Owned rooms with other members | ownership transfers to oldest member |
| Owned rooms with no other members | room + messages + files deleted |
| Chat messages authored by user | anonymized to `[deleted]` |
| File uploads | `uploaded_by` set to `[deleted]` |
| Audit entries | `actor_id`, `ip`, `user_agent` cleared |
| Backups | deleted from DB and disk |

### Encrypted backups

Create, list, download, and delete client-side-encrypted backups:

    python -m cli.account backup --token=$JWT --file=notes.db --password=pw
    python -m cli.account list-backups --token=$JWT
    python -m cli.account download-backup --token=$JWT --id=<id>
    python -m cli.account restore --file=backup-<id>.enc --password=pw

Uses AES-GCM with PBKDF2(SHA-256, 100k iterations). The server stores
only ciphertext.

## `arith` CLI

One command for everything:

    arith serve                    # start web server at :8000
    arith serve --port 9000        # custom port
    arith cli                      # interactive calculator
    arith ai                       # AI natural-language CLI
    arith demo                     # AI batch demo
    arith account summary --token=$JWT
    arith account export --token=$JWT --format=zip --out=me.zip
    arith version
    arith doctor                   # environment diagnostics
    arith help

The old `arithmetic-cli` and `arithmetic-ai` console scripts still work.

## Push Notifications

Register an FCM device token (mobile or web) and receive server pushes
for room invites and mentions.

    POST /api/notifications/register    {"token": "...", "platform": "android"}
    POST /api/notifications/unregister  {"token": "..."}
    GET  /api/notifications/tokens
    POST /api/notifications/test

Configure FCM:

    export FCM_PROJECT_ID=my-firebase-project
    export FCM_ACCESS_TOKEN=<short-lived access token>
    # or point to a service-account JSON for project_id discovery:
    export FCM_SERVICE_ACCOUNT_JSON=/path/to/service-account.json

Without credentials, `send_push()` logs a dry-run line and returns
`False`. Nothing crashes, nothing requires Firebase SDK.

## Kubernetes + Helm

    # Raw manifests
    kubectl apply -f k8s/

    # Helm chart
    helm install arith ./helm/arithmetic -n arithmetic --create-namespace

See `helm/README.md` for full options.

## OpenTelemetry Tracing

Tracing is opt-in and degrades to a no-op without OTel packages.

    pip install -e ".[observability]"
    export OTEL_ENABLED=1
    export OTEL_SERVICE_NAME=arithmetic-super-app
    export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318/v1/traces
    arith serve

Without `OTEL_EXPORTER_OTLP_ENDPOINT`, spans print to the console.
Every response gets an `X-Trace-ID` header when a span is active.

The `@trace("name")` decorator wraps any function:

    from web.backend.tracing import trace

    @trace("arithmetic.add")
    def add(a, b):
        return a + b

## Full-Text Search

    GET /api/search?q=<query>&scope=all|calculations|chat&limit=20

Uses SQLite FTS5 with `bm25` ranking when available, else falls back
to LIKE. The response includes an `engine` field so clients know which
backend served the query.

## Component Gallery

Visit `/gallery` for a live, self-contained visual reference of every
UI primitive: buttons, forms, tabs, cards, toasts, modals, badges,
chat lines, feed items, skeletons, and empty states.

## Offline-First UI

The frontend caches recent calculations in IndexedDB and queues
non-GET requests when the connection drops. A badge in the header
shows pending count. On reconnect, the queue is flushed automatically.

No configuration required — it activates on the first load.

## Presence Avatars

Every room shows colored initial avatars for the people present.
Colors are deterministic per username (same algorithm client + server).

## Encrypted DMs

User-to-user direct messages with end-to-end encryption.

    POST   /api/dms/threads                    {username}     start a thread
    GET    /api/dms/threads                                   list threads
    GET    /api/dms/threads/<id>?limit=50                     messages
    POST   /api/dms/threads/<id>               {body, encrypted}
    DELETE /api/dms/threads/<id>                              delete thread

**E2E design**: sender and recipient exchange a shared passphrase
out-of-band. The key is derived client-side via
PBKDF2(SHA-256, 100k) over `passphrase + sorted(usernames)`. The
server stores only ciphertext.

Best-effort push notification on new messages (Phase 19 FCM).
