"""Chat/DM export (Phase 34).

Formats: json, md, html
- json: structured dump
- md:   markdown transcript
- html: styled page with "Print to PDF" button (browser handles PDF)

Endpoints:
    GET /api/export/room/<room>?format=md|json|html
    GET /api/export/dm/<thread_id>?format=md|json|html
"""
import html as html_mod
import json
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, g, Response

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit

export_bp = Blueprint("export", __name__, url_prefix="/api/export")

VALID_FORMATS = {"json", "md", "html"}


def _fmt_ts(s):
    if not s:
        return ""
    try:
        return s.replace("T", " ").split(".")[0]
    except Exception:
        return s


def _render_md(meta, messages):
    lines = [f"# {meta['title']}", ""]
    for k, v in meta.get("meta", {}).items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")
    lines.append(f"_Exported: {datetime.now(timezone.utc).isoformat(timespec='seconds')}Z_")
    lines.append("")
    lines.append("---")
    lines.append("")
    for m in messages:
        who = m.get("username") or m.get("sender") or "?"
        ts = _fmt_ts(m.get("created_at"))
        body = m.get("body") or ""
        kind = m.get("kind") or "text"
        lock = "🔒 " if m.get("encrypted") else ""
        note = ""
        if kind == "voice":
            dur = m.get("duration_ms", "?")
            note = f" _(voice message, {dur} ms)_"
            body = f"[voice clip {m.get('attachment_id','?')}]"
        lines.append(f"**{who}** · {ts}")
        lines.append("")
        lines.append(f"> {lock}{body}{note}")
        lines.append("")
    return "\n".join(lines)


def _render_html(meta, messages):
    esc = html_mod.escape
    rows = []
    for m in messages:
        who = esc(str(m.get("username") or m.get("sender") or "?"))
        ts = esc(_fmt_ts(m.get("created_at")))
        body = esc(m.get("body") or "")
        kind = m.get("kind") or "text"
        lock = "🔒 " if m.get("encrypted") else ""
        note = ""
        if kind == "voice":
            note = f' <em>(voice · {m.get("duration_ms","?")} ms)</em>'
            body = f'[voice clip {esc(str(m.get("attachment_id","?")))}]'
        rows.append(f'''
        <div class="msg">
            <div class="head"><strong>{who}</strong> <span class="ts">{ts}</span></div>
            <div class="body">{lock}{body}{note}</div>
        </div>''')
    meta_lines = "".join(
        f'<li><strong>{esc(str(k))}</strong>: {esc(str(v))}</li>'
        for k, v in meta.get("meta", {}).items()
    )
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<title>{esc(meta["title"])}</title>
<style>
    body {{ font-family: -apple-system, sans-serif; max-width: 720px; margin: 40px auto; padding: 0 20px; color: #0f172a; }}
    h1 {{ border-bottom: 2px solid #38bdf8; padding-bottom: 8px; }}
    .meta {{ background: #f1f5f9; padding: 12px 16px; border-radius: 8px; margin: 16px 0; font-size: 0.9em; }}
    .meta ul {{ margin: 0; padding-left: 20px; }}
    .msg {{ border-bottom: 1px solid #e2e8f0; padding: 12px 0; }}
    .head {{ font-size: 0.85em; color: #64748b; }}
    .ts {{ margin-left: 8px; }}
    .body {{ margin-top: 6px; white-space: pre-wrap; word-break: break-word; }}
    .toolbar {{ position: fixed; top: 12px; right: 12px; }}
    .toolbar button {{ padding: 8px 14px; border-radius: 6px; border: none;
        background: #38bdf8; color: #0f172a; font-weight: 600; cursor: pointer; }}
    @media print {{ .toolbar {{ display: none; }} }}
</style>
</head>
<body>
<div class="toolbar"><button onclick="window.print()">🖨 Print / Save as PDF</button></div>
<h1>{esc(meta["title"])}</h1>
<div class="meta"><ul>{meta_lines}<li><strong>Exported</strong>: {datetime.now(timezone.utc).isoformat(timespec="seconds")}Z</li></ul></div>
{"".join(rows)}
</body>
</html>'''


def _fetch_room(room, limit=1000):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, username, body, encrypted, parent_id, kind, "
            "       attachment_id, created_at "
            "FROM chat_messages WHERE room_id = ? ORDER BY id ASC LIMIT ?",
            (room, limit),
        ).fetchall()
        # enrich with voice duration
        out = []
        for r in rows:
            d = dict(r)
            if d.get("kind") == "voice" and d.get("attachment_id"):
                clip = conn.execute(
                    "SELECT duration_ms FROM voice_clips WHERE id = ?",
                    (d["attachment_id"],),
                ).fetchone()
                if clip:
                    d["duration_ms"] = clip["duration_ms"]
            out.append(d)
    return out


def _fetch_dm(thread_id, limit=1000):
    with get_db() as conn:
        t = conn.execute(
            "SELECT user_a, user_b FROM dm_threads WHERE id = ?", (thread_id,)
        ).fetchone()
        if not t or g.user_id not in (t["user_a"], t["user_b"]):
            return None
        rows = conn.execute(
            "SELECT m.id, u.username AS username, m.body, m.encrypted, "
            "       m.kind, m.attachment_id, m.created_at "
            "FROM dm_messages m JOIN users u ON u.id = m.sender_id "
            "WHERE m.thread_id = ? ORDER BY m.id ASC LIMIT ?",
            (thread_id, limit),
        ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            if d.get("kind") == "voice" and d.get("attachment_id"):
                clip = conn.execute(
                    "SELECT duration_ms FROM voice_clips WHERE id = ?",
                    (d["attachment_id"],),
                ).fetchone()
                if clip:
                    d["duration_ms"] = clip["duration_ms"]
            out.append(d)
    return out


def _respond(fmt, meta, messages, base_name):
    if fmt == "json":
        body = json.dumps({"meta": meta, "messages": messages}, indent=2, default=str)
        return Response(body, mimetype="application/json", headers={
            "Content-Disposition": f'attachment; filename="{base_name}.json"'
        })
    if fmt == "md":
        body = _render_md(meta, messages)
        return Response(body, mimetype="text/markdown; charset=utf-8", headers={
            "Content-Disposition": f'attachment; filename="{base_name}.md"'
        })
    body = _render_html(meta, messages)
    return Response(body, mimetype="text/html; charset=utf-8", headers={
        "Content-Disposition": f'inline; filename="{base_name}.html"'
    })


@export_bp.route("/room/<room>", methods=["GET"])
@require_auth
@rate_limit(max_calls=10, window_seconds=60)
def export_room(room):
    fmt = (request.args.get("format") or "md").lower()
    if fmt not in VALID_FORMATS:
        return jsonify({"error": "format must be json/md/html"}), 400
    messages = _fetch_room(room)
    meta = {
        "title": f"Chat export — {room}",
        "meta": {"room": room, "messages": len(messages)},
    }
    return _respond(fmt, meta, messages, f"chat-{room}")


@export_bp.route("/dm/<int:thread_id>", methods=["GET"])
@require_auth
@rate_limit(max_calls=10, window_seconds=60)
def export_dm(thread_id):
    fmt = (request.args.get("format") or "md").lower()
    if fmt not in VALID_FORMATS:
        return jsonify({"error": "format must be json/md/html"}), 400
    messages = _fetch_dm(thread_id)
    if messages is None:
        return jsonify({"error": "Thread not found or not yours"}), 404
    meta = {
        "title": f"DM export — thread {thread_id}",
        "meta": {"thread_id": thread_id, "messages": len(messages)},
    }
    return _respond(fmt, meta, messages, f"dm-{thread_id}")
