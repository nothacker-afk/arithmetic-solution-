"""Unified `arith` CLI (Phase 18).

Usage:
    arith serve [--host HOST] [--port PORT]   Start the web server
    arith cli                                  Interactive calculator
    arith ai                                   AI natural-language CLI
    arith demo                                 AI batch demo
    arith account <subcommand> ...             Data ownership ops
    arith version                              Print version
    arith doctor                               Environment diagnostics
    arith help                                 This help
"""
import os
import platform
import shutil
import sys


USAGE = """Arithmetic Super App — arith CLI

Usage:
    arith serve [--host HOST] [--port PORT]    Start the Flask + WebSocket server
    arith cli                                   Interactive calculator (menu-driven)
    arith ai                                    AI natural-language CLI
    arith demo                                  AI batch demo (14 sample phrases)
    arith account <sub> [args]                  GDPR: summary | export | delete |
                                                backup | list-backups |
                                                download-backup | restore
    arith version                               Print the package version
    arith doctor                                Print environment diagnostics
    arith help                                  Show this message
"""


def _cmd_serve(argv):
    """Start the Flask + WebSocket server."""
    from web.backend.main import app, socketio  # type: ignore

    host = "0.0.0.0"
    port = 8000
    debug = False

    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--host", "-H") and i + 1 < len(argv):
            host = argv[i + 1]; i += 2; continue
        if a in ("--port", "-p") and i + 1 < len(argv):
            port = int(argv[i + 1]); i += 2; continue
        if a in ("--debug", "-d"):
            debug = True; i += 1; continue
        sys.stderr.write(f"Unknown arg for serve: {a}\n")
        i += 1

    sys.stderr.write(f"\n  Arithmetic Super App running at http://{host}:{port}\n")
    sys.stderr.write(f"  WebSocket: ws://{host}:{port}/socket.io/\n\n")

    socketio.run(app, host=host, port=port,
                 debug=debug, allow_unsafe_werkzeug=True)


def _cmd_cli(argv):
    from cli.main import main
    main()


def _cmd_ai(argv):
    from ai_engine.cli import main
    main()


def _cmd_demo(argv):
    from ai_engine.demo import main
    main()


def _cmd_account(argv):
    sys.argv = [sys.argv[0]] + argv
    from cli.account import main
    main()


def _cmd_version(argv):
    import arithmetic
    print(arithmetic.__version__)


def _cmd_doctor(argv):
    import importlib
    print("Arithmetic Super App — doctor")
    print("=" * 40)
    print(f"  Python:        {sys.version.split()[0]}")
    print(f"  Platform:      {platform.platform()}")
    print(f"  Executable:    {sys.executable}")
    print(f"  cwd:           {os.getcwd()}")
    print(f"  git available: {'yes' if shutil.which('git') else 'no'}")
    print()
    print("Required packages:")
    for pkg in ("flask", "flask_cors", "flask_socketio", "jwt",
                "werkzeug", "sqlalchemy", "alembic"):
        try:
            importlib.import_module(pkg)
            status = "✅"
        except ImportError:
            status = "❌"
        print(f"  {status} {pkg}")
    print()
    print("Optional packages:")
    for pkg in ("strawberry", "openai", "flet", "cryptography",
                "opentelemetry", "opentelemetry.sdk", "yaml"):
        try:
            importlib.import_module(pkg)
            status = "✅"
        except ImportError:
            status = "—"
        print(f"  {status} {pkg}")
    print()
    print("Environment:")
    for var in ("JWT_SECRET", "SECRET_KEY", "DB_PATH", "DB_BACKEND",
                "DATABASE_URL", "OPENAI_API_KEY", "FCM_SERVICE_ACCOUNT_JSON",
                "OTEL_ENABLED", "OTEL_EXPORTER_OTLP_ENDPOINT"):
        val = os.environ.get(var)
        if val:
            shown = val if len(val) < 30 else val[:20] + "…"
            print(f"  {var} = {shown}")
        else:
            print(f"  {var} = (unset)")
    print()
    print("Project layout:")
    for path in ("arithmetic", "cli", "ai_engine", "web/backend",
                 "web/frontend", "k8s", "helm/arithmetic", "alembic",
                 "tests"):
        exists = os.path.isdir(path)
        print(f"  {'✅' if exists else '❌'} {path}/")


def main():
    argv = sys.argv[1:]
    if not argv:
        print(USAGE)
        return
    cmd, rest = argv[0], argv[1:]

    dispatch = {
        "serve": _cmd_serve,
        "web": _cmd_serve,        # alias
        "cli": _cmd_cli,
        "ai": _cmd_ai,
        "demo": _cmd_demo,
        "account": _cmd_account,
        "version": _cmd_version,
        "--version": _cmd_version,
        "-v": _cmd_version,
        "doctor": _cmd_doctor,
        "help": lambda _: print(USAGE),
        "--help": lambda _: print(USAGE),
        "-h": lambda _: print(USAGE),
    }

    if cmd not in dispatch:
        sys.stderr.write(f"Unknown command: {cmd}\n\n{USAGE}")
        sys.exit(2)

    dispatch[cmd](rest)


if __name__ == "__main__":
    main()
