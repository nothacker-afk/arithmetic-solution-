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
