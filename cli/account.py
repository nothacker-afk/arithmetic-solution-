"""Account data CLI (Phase 17).

Usage:
    python -m cli.account export --token=<JWT> [--out=<file>] [--format=json|zip]
    python -m cli.account summary --token=<JWT>
    python -m cli.account delete --token=<JWT> --password=<pw> --yes
    python -m cli.account backup --token=<JWT> --out=<file> [--label=<label>]
    python -m cli.account list-backups --token=<JWT>
    python -m cli.account download-backup --token=<JWT> --id=<backup_id> [--out=<file>]
    python -m cli.account delete-backup --token=<JWT> --id=<backup_id>
"""
import argparse
import base64
import json
import os
import sys
import urllib.request
import urllib.error


def _api(method, path, token=None, body=None, raw=False):
    url = os.environ.get("ARITH_API", "http://localhost:8000") + path
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            payload = resp.read()
            if raw:
                return payload, resp.headers
            if not payload:
                return None
            return json.loads(payload), resp.headers
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        try:
            err = json.loads(body)
            msg = err.get("error", body)
        except json.JSONDecodeError:
            msg = body
        sys.stderr.write(f"HTTP {e.code}: {msg}\n")
        sys.exit(1)


def cmd_summary(args):
    data, _ = _api("GET", "/api/account/data-summary", token=args.token)
    sys.stderr.write(json.dumps(data, indent=2) + "\n")


def cmd_export(args):
    path = f"/api/account/export?format={args.format}"
    payload, headers = _api("GET", path, token=args.token, raw=True)

    out = args.out
    if not out:
        ext = "zip" if args.format == "zip" else "json"
        out = f"account-export.{ext}"

    with open(out, "wb") as f:
        f.write(payload)
    sys.stderr.write(f"Wrote {len(payload)} bytes to {out}\n")


def cmd_delete(args):
    if not args.yes:
        sys.stderr.write("Refusing to delete without --yes\n")
        sys.exit(1)
    data, _ = _api("DELETE", "/api/account", token=args.token, body={
        "password": args.password, "confirm": "DELETE",
    })
    sys.stderr.write(f"Deleted account: {data}\n")


def cmd_backup(args):
    with open(args.file, "rb") as f:
        plain = f.read()

    # Local AES-GCM encryption with PBKDF2(SHA-256) key derivation
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
    except ImportError:
        sys.stderr.write("Install 'cryptography' for encrypted backups:\n")
        sys.stderr.write("    pip install cryptography\n")
        sys.exit(1)

    import secrets
    salt = secrets.token_bytes(16)
    iv = secrets.token_bytes(12)
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                     salt=salt, iterations=100_000)
    key = kdf.derive(args.password.encode("utf-8"))
    ciphertext = AESGCM(key).encrypt(iv, plain, None)

    # File format: magic | version | salt | iv | ciphertext
    blob = b"ARB1" + salt + iv + ciphertext
    b64 = base64.b64encode(blob).decode("ascii")

    resp, _ = _api("POST", "/api/account/backups", token=args.token, body={
        "label": args.label or args.file, "ciphertext_b64": b64,
    })
    sys.stderr.write(f"Backup stored: id={resp['id']} size={resp['size_bytes']}\n")
    sys.stderr.write(f"Save the passphrase — it is required to restore.\n")


def cmd_list_backups(args):
    data, _ = _api("GET", "/api/account/backups", token=args.token)
    for b in data["backups"]:
        sys.stderr.write(f"  {b['id']}  {b['size_bytes']:>8} B  {b['created_at']}  {b['label'] or ''}\n")


def cmd_download_backup(args):
    payload, _ = _api("GET", f"/api/account/backups/{args.id}",
                      token=args.token, raw=True)
    out = args.out or f"backup-{args.id}.enc"
    with open(out, "wb") as f:
        f.write(payload)
    sys.stderr.write(f"Wrote {len(payload)} bytes to {out}\n")


def cmd_restore(args):
    with open(args.file, "rb") as f:
        blob = f.read()

    if not blob.startswith(b"ARB1"):
        sys.stderr.write("Not a valid backup file (missing magic)\n")
        sys.exit(1)

    salt = blob[4:20]
    iv = blob[20:32]
    ciphertext = blob[32:]

    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives import hashes
    except ImportError:
        sys.stderr.write("Install 'cryptography': pip install cryptography\n")
        sys.exit(1)

    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32,
                     salt=salt, iterations=100_000)
    key = kdf.derive(args.password.encode("utf-8"))
    plain = AESGCM(key).decrypt(iv, ciphertext, None)

    out = args.out or (args.file + ".plain")
    with open(out, "wb") as f:
        f.write(plain)
    sys.stderr.write(f"Restored {len(plain)} bytes to {out}\n")


def cmd_delete_backup(args):
    _api("DELETE", f"/api/account/backups/{args.id}", token=args.token)
    sys.stderr.write(f"Deleted backup {args.id}\n")


def main():
    parser = argparse.ArgumentParser(
        prog="python -m cli.account",
        description="Account data management (Phase 17)",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("summary", help="Show data summary")
    p.add_argument("--token", required=True)
    p.set_defaults(fn=cmd_summary)

    p = sub.add_parser("export", help="Download your data")
    p.add_argument("--token", required=True)
    p.add_argument("--format", choices=["json", "zip"], default="json")
    p.add_argument("--out")
    p.set_defaults(fn=cmd_export)

    p = sub.add_parser("delete", help="Delete your account (irreversible)")
    p.add_argument("--token", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--yes", action="store_true")
    p.set_defaults(fn=cmd_delete)

    p = sub.add_parser("backup", help="Encrypt and upload a local file as a backup")
    p.add_argument("--token", required=True)
    p.add_argument("--file", required=True)
    p.add_argument("--password", required=True, help="Encryption passphrase")
    p.add_argument("--label")
    p.set_defaults(fn=cmd_backup)

    p = sub.add_parser("list-backups", help="List your encrypted backups")
    p.add_argument("--token", required=True)
    p.set_defaults(fn=cmd_list_backups)

    p = sub.add_parser("download-backup", help="Download a backup blob")
    p.add_argument("--token", required=True)
    p.add_argument("--id", required=True)
    p.add_argument("--out")
    p.set_defaults(fn=cmd_download_backup)

    p = sub.add_parser("restore", help="Decrypt a downloaded backup locally")
    p.add_argument("--file", required=True)
    p.add_argument("--password", required=True)
    p.add_argument("--out")
    p.set_defaults(fn=cmd_restore)

    p = sub.add_parser("delete-backup", help="Delete a backup")
    p.add_argument("--token", required=True)
    p.add_argument("--id", required=True)
    p.set_defaults(fn=cmd_delete_backup)

    args = parser.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
