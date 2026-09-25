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
