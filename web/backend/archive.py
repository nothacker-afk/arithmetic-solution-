"""Room archive / static site export (Phase 66).

Creates a ZIP with a static, self-contained snapshot of a room:
    index.html         static rendered view
    messages.json      all chat messages (with metadata)
    wiki/<slug>.md     wiki pages as markdown
    media.json         file + voice references (metadata only)
    README.txt         what's inside
"""
import html as html_mod
import io
import json
import uuid
import zipfile
from datetime import datetime, timezone

from flask import Blueprint, request, jsonify, Response, g

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit
from .audit import log_event

archive_bp = Blueprint("archive", __name__, url_prefix="/api/rooms")


def _collect(conn, room):
    room_row = conn.execute(
        "SELECT name, owner_id, created_at FROM rooms WHERE name = ?", (room,),
    ).fetchone()
    meta = conn.execute(
        "SELECT description, tags FROM room_meta WHERE room_id = ?", (room,),
    ).fetchone()
    messages = conn.execute("""
        SELECT id, username, body, encrypted, kind, attachment_id,
               edited_at, deleted, created_at
        FROM chat_messages WHERE room_id = ?
        ORDER BY id ASC LIMIT 5000
    """, (room,)).fetchall()
    wiki = conn.execute("""
        SELECT title, slug, body, updated_at
        FROM wiki_pages WHERE room_id = ? ORDER BY slug LIMIT 500
    """, (room,)).fetchall()
    files = conn.execute("""
        SELECT id, filename, size_bytes, encrypted, uploaded_by, created_at
        FROM room_files WHERE room_id = ? ORDER BY created_at LIMIT 500
    """, (room,)).fetchall()
    try:
        voices = conn.execute("""
            SELECT v.id, v.duration_ms, v.size_bytes, v.uploader AS username,
                   v.created_at
            FROM voice_clips v
            JOIN chat_messages c ON c.attachment_id = v.id
            WHERE c.room_id = ? ORDER BY v.created_at LIMIT 500
        """, (room,)).fetchall()
    except Exception:
        voices = []

    return {
        "room": dict(room_row) if room_row else {"name": room},
        "meta": dict(meta) if meta else {},
        "messages": [dict(m) for m in messages],
        "wiki": [dict(w) for w in wiki],
        "files": [dict(f) for f in files],
        "voices": [dict(v) for v in voices],
    }


def _render_html(data):
    esc = html_mod.escape
    rows = []
    for m in data["messages"]:
        who = esc(str(m["username"]))
        body = esc(str(m["body"] or ""))
        if m.get("deleted"):
            body = "<em class='deleted'>(deleted)</em>"
        elif m.get("encrypted"):
            body = "🔒 " + body
        rows.append(
            f'<div class="msg"><strong>{who}</strong> '
            f'<span class="ts">{esc(str(m["created_at"]))}</span>'
            f'<div class="body">{body}</div></div>'
        )

    wiki_links = "".join(
        f'<li><a href="#wiki-{esc(w["slug"])}">{esc(w["title"])}</a></li>'
        for w in data["wiki"]
    ) or "<li class='muted'>(no wiki pages)</li>"

    wiki_bodies = "".join(
        f'<h3 id="wiki-{esc(w["slug"])}">{esc(w["title"])}</h3>'
        f'<pre>{esc(w["body"])}</pre>'
        for w in data["wiki"]
    ) or "<p class='muted'>No wiki pages.</p>"

    meta = data["meta"]
    desc = esc(meta.get("description", "") or "")
    tags = esc(meta.get("tags", "") or "")

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"/>
<title>{esc(data["room"].get("name", "room"))} — Archive</title>
<style>
body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 720px;
        margin: 40px auto; padding: 0 20px; color: #0f172a; line-height: 1.5; }}
h1 {{ border-bottom: 2px solid #38bdf8; padding-bottom: 8px; }}
h2 {{ margin-top: 40px; padding-bottom: 4px; border-bottom: 1px solid #cbd5e1; }}
.meta {{ background: #f1f5f9; padding: 12px 16px; border-radius: 8px;
         font-size: 0.9em; margin: 16px 0; }}
.msg {{ border-bottom: 1px solid #e2e8f0; padding: 10px 0; }}
.msg .ts {{ font-size: 0.8em; color: #64748b; margin-left: 8px; }}
.msg .body {{ margin-top: 4px; white-space: pre-wrap; word-break: break-word; }}
.deleted {{ color: #94a3b8; font-style: italic; }}
.muted {{ color: #64748b; }}
pre {{ background: #f8fafc; padding: 12px; border-radius: 6px;
       white-space: pre-wrap; font-family: ui-monospace, monospace; font-size: 0.85em; }}
</style></head><body>
<h1>{esc(data["room"].get("name", "room"))}</h1>
<div class="meta">
    <p>{desc or "<em>No description</em>"}</p>
    <p><strong>Tags:</strong> {tags or "(none)"} ·
       <strong>Messages:</strong> {len(data["messages"])} ·
       <strong>Files:</strong> {len(data["files"])} ·
       <strong>Voice clips:</strong> {len(data["voices"])}</p>
    <p><strong>Archived:</strong> {datetime.now(timezone.utc).isoformat(timespec="seconds")}Z</p>
</div>

<h2>Wiki</h2>
<ul>{wiki_links}</ul>
{wiki_bodies}

<h2>Messages</h2>
{''.join(rows) or '<p class="muted">No messages.</p>'}

<h2>Files (metadata only)</h2>
<pre>{esc(json.dumps(data["files"], indent=2, default=str))}</pre>

<h2>Voice clips (metadata only)</h2>
<pre>{esc(json.dumps(data["voices"], indent=2, default=str))}</pre>
</body></html>
"""


@archive_bp.route("/<room>/archive", methods=["POST"])
@require_auth
@rate_limit(max_calls=5, window_seconds=300)
def create_archive(room):
    import re
    if not re.match(r"^[a-zA-Z0-9_-]{1,64}$", room or ""):
        return jsonify({"error": "Invalid room name"}), 400

    with get_db() as conn:
        room_row = conn.execute(
            "SELECT owner_id FROM rooms WHERE name = ?", (room,),
        ).fetchone()
        if not room_row:
            return jsonify({"error": "Room not registered"}), 404
        if room_row["owner_id"] != g.user_id:
            return jsonify({"error": "Only the room owner can archive"}), 403

        data = _collect(conn, room)

        # Build ZIP in memory
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("README.txt",
                f"Archive of room '{room}'\\n"
                f"Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}Z\\n"
                f"\\n"
                f"Contents:\\n"
                f"  index.html     — static view of the room\\n"
                f"  messages.json  — all chat messages\\n"
                f"  media.json     — file + voice clip metadata\\n"
                f"  wiki/<slug>.md — wiki pages as markdown\\n"
            )
            zf.writestr("index.html", _render_html(data))
            zf.writestr("messages.json",
                        json.dumps(data["messages"], indent=2, default=str))
            zf.writestr("media.json", json.dumps({
                "files": data["files"],
                "voices": data["voices"],
            }, indent=2, default=str))
            for w in data["wiki"]:
                zf.writestr(f"wiki/{w['slug']}.md",
                            f"# {w['title']}\\n\\n{w['body']}\\n")

        blob = buf.getvalue()

        archive_id = uuid.uuid4().hex
        conn.execute("""
            INSERT INTO room_archives
            (id, room_id, created_by, size_bytes, message_count, wiki_count, file_count)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (archive_id, room, g.user_id, len(blob),
              len(data["messages"]), len(data["wiki"]), len(data["files"])))

    log_event("room.archive", actor_id=g.user_id, resource="room",
              resource_id=room, details={"archive_id": archive_id, "size": len(blob)})

    resp = Response(blob, mimetype="application/zip")
    resp.headers["Content-Disposition"] = (
        f'attachment; filename="room-{room}-{archive_id[:8]}.zip"'
    )
    resp.headers["X-Archive-ID"] = archive_id
    return resp


@archive_bp.route("/<room>/archives", methods=["GET"])
@require_auth
def list_archives(room):
    import re
    if not re.match(r"^[a-zA-Z0-9_-]{1,64}$", room or ""):
        return jsonify({"error": "Invalid room name"}), 400
    with get_db() as conn:
        room_row = conn.execute(
            "SELECT owner_id FROM rooms WHERE name = ?", (room,),
        ).fetchone()
        if not room_row or room_row["owner_id"] != g.user_id:
            return jsonify({"error": "Only the room owner can list archives"}), 403
        rows = conn.execute("""
            SELECT id, size_bytes, message_count, wiki_count, file_count, created_at
            FROM room_archives WHERE room_id = ?
            ORDER BY created_at DESC LIMIT 50
        """, (room,)).fetchall()
    return jsonify({"archives": [dict(r) for r in rows]})
