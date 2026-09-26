"""Room templates (Phase 59).

A template is a preset: wiki pages, voice channels, description, tags.
Applying a template seeds a freshly claimed room.

Endpoints:
    GET    /api/room_templates                        list templates
    GET    /api/room_templates/<id>                   template detail
    POST   /api/rooms/<room>/apply_template           {template_id}
    GET    /api/rooms/<room>/applied_template         what was applied
"""
import re

from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit
from .audit import log_event

templates_bp = Blueprint("templates", __name__, url_prefix="/api/room_templates")
apply_bp = Blueprint("apply_template", __name__, url_prefix="/api/rooms")

ROOM_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")

# Templates are Python dicts so we can keep them version-controlled
TEMPLATES = {
    "blank": {
        "name": "Blank",
        "description": "Start from scratch",
        "tags": "",
        "wiki": [],
        "voice_channels": ["main"],
    },
    "community": {
        "name": "Community",
        "description": "A welcoming space for open discussion",
        "tags": "community,chat",
        "wiki": [
            {"title": "Welcome",
             "body": "Welcome to the room!\n\n1. Be kind\n2. Stay on topic\n3. No spam"},
            {"title": "Rules",
             "body": "## House rules\n\n- Respect others\n- Keep it SFW\n- Report issues to moderators"},
        ],
        "voice_channels": ["main", "afk", "music"],
    },
    "project": {
        "name": "Project",
        "description": "A room for a team working on something",
        "tags": "project,team",
        "wiki": [
            {"title": "Project Brief",
             "body": "## Goal\n\nDescribe the project here.\n\n## Milestones\n\n- [ ] M1\n- [ ] M2"},
            {"title": "Standups",
             "body": "Daily standup notes go here."},
            {"title": "Decisions",
             "body": "Record important decisions with dates."},
        ],
        "voice_channels": ["standup", "focus", "break"],
    },
    "study": {
        "name": "Study Group",
        "description": "Collaborative learning space",
        "tags": "study,learning",
        "wiki": [
            {"title": "Syllabus",
             "body": "## Topics\n\n1. ...\n2. ..."},
            {"title": "Resources",
             "body": "Links and references go here."},
        ],
        "voice_channels": ["study", "discussion"],
    },
}


@templates_bp.route("", methods=["GET"])
def list_templates():
    return jsonify({
        "templates": [
            {"id": tid, "name": t["name"], "description": t["description"],
             "tags": t.get("tags", ""),
             "wiki_pages": len(t.get("wiki", [])),
             "voice_channels": t.get("voice_channels", [])}
            for tid, t in TEMPLATES.items()
        ]
    })


@templates_bp.route("/<template_id>", methods=["GET"])
def get_template(template_id):
    t = TEMPLATES.get(template_id)
    if not t:
        return jsonify({"error": "Template not found"}), 404
    return jsonify({"id": template_id, **t})


def _slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:64] or "page"


@apply_bp.route("/<room>/apply_template", methods=["POST"])
@require_auth
@rate_limit(max_calls=5, window_seconds=60)
def apply_template(room):
    if not ROOM_RE.match(room or ""):
        return jsonify({"error": "Invalid room name"}), 400

    data = request.get_json(silent=True) or {}
    template_id = (data.get("template_id") or "").strip()
    t = TEMPLATES.get(template_id)
    if not t:
        return jsonify({"error": "Template not found"}), 404

    with get_db() as conn:
        # Only the room owner can apply a template
        room_row = conn.execute(
            "SELECT owner_id FROM rooms WHERE name = ?", (room,),
        ).fetchone()
        if room_row and room_row["owner_id"] != g.user_id:
            return jsonify({"error": "Only the room owner can apply a template"}), 403

        # Update room meta
        conn.execute("""
            INSERT INTO room_meta (room_id, description, tags)
            VALUES (?, ?, ?)
            ON CONFLICT(room_id) DO UPDATE SET
                description = COALESCE(room_meta.description, excluded.description),
                tags = COALESCE(room_meta.tags, excluded.tags),
                updated_at = CURRENT_TIMESTAMP
        """, (room, t.get("description", ""), t.get("tags", "")))

        # Create wiki pages (skip if slug already exists)
        pages_created = 0
        for page in t.get("wiki", []):
            slug = _slugify(page["title"])
            existing = conn.execute(
                "SELECT 1 FROM wiki_pages WHERE room_id = ? AND slug = ?",
                (room, slug),
            ).fetchone()
            if not existing:
                import uuid
                conn.execute("""
                    INSERT INTO wiki_pages
                    (id, room_id, title, slug, body, created_by, updated_by)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (uuid.uuid4().hex, room, page["title"], slug,
                      page["body"], g.user_id, g.user_id))
                pages_created += 1

        # Record which template was applied
        import json as _json
        conn.execute("""
            INSERT INTO room_template_applied (room_id, template_id, applied_by, config)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(room_id) DO UPDATE SET
                template_id = excluded.template_id,
                applied_at = CURRENT_TIMESTAMP,
                applied_by = excluded.applied_by,
                config = excluded.config
        """, (room, template_id, g.user_id, _json.dumps({
            "wiki_pages_created": pages_created,
            "voice_channels": t.get("voice_channels", []),
        })))

    log_event("room.apply_template", actor_id=g.user_id, resource="room",
              resource_id=room, details={"template": template_id})

    return jsonify({
        "room": room,
        "template_id": template_id,
        "wiki_pages_created": pages_created,
        "voice_channels": t.get("voice_channels", []),
    })


@apply_bp.route("/<room>/applied_template", methods=["GET"])
@require_auth
def get_applied(room):
    if not ROOM_RE.match(room or ""):
        return jsonify({"error": "Invalid room name"}), 400
    with get_db() as conn:
        row = conn.execute(
            "SELECT template_id, applied_at, applied_by, config "
            "FROM room_template_applied WHERE room_id = ?", (room,),
        ).fetchone()
    if not row:
        return jsonify({"room": room, "template_id": None})
    return jsonify({"room": room, **dict(row)})
