"""Wiki page comments (Phase 68).

Threaded (single-level) discussion on wiki pages.

Endpoints:
    GET    /api/wiki/<page_id>/comments
    POST   /api/wiki/<page_id>/comments       {body, parent_id?}
    PATCH  /api/wiki/<page_id>/comments/<id>  {body}
    DELETE /api/wiki/<page_id>/comments/<id>  (soft-delete)
"""
import re

from flask import Blueprint, request, jsonify, g

from .database import get_db
from .auth import require_auth
from .rate_limit import rate_limit

wc_bp = Blueprint("wiki_comments", __name__, url_prefix="/api/wiki")

PAGE_ID_RE = re.compile(r"^[0-9a-f]{32}$")
MAX_BODY = 4000


def _row_to_dict(row):
    d = dict(row)
    d.setdefault("parent_id", None)
    d.setdefault("deleted", 0)
    d.setdefault("edited_at", None)
    return d


@wc_bp.route("/<page_id>/comments", methods=["GET"])
@require_auth
def list_comments(page_id):
    if not PAGE_ID_RE.match(page_id or ""):
        return jsonify({"error": "Invalid page id"}), 400

    with get_db() as conn:
        page = conn.execute("SELECT id FROM wiki_pages WHERE id = ?", (page_id,)).fetchone()
        if not page:
            return jsonify({"error": "Page not found"}), 404
        rows = conn.execute("""
            SELECT c.id, c.user_id, c.parent_id, c.body, c.edited_at, c.deleted,
                   c.created_at, u.username
            FROM wiki_comments c JOIN users u ON u.id = c.user_id
            WHERE c.page_id = ?
            ORDER BY c.created_at ASC LIMIT 500
        """, (page_id,)).fetchall()

    # Organize into top-level + replies
    top, by_parent = [], {}
    for r in rows:
        d = _row_to_dict(r)
        if d["parent_id"]:
            by_parent.setdefault(d["parent_id"], []).append(d)
        else:
            top.append(d)
    for t in top:
        t["replies"] = by_parent.get(t["id"], [])
    return jsonify({"page_id": page_id, "comments": top, "count": len(top)})


@wc_bp.route("/<page_id>/comments", methods=["POST"])
@require_auth
@rate_limit(max_calls=30, window_seconds=60)
def add_comment(page_id):
    if not PAGE_ID_RE.match(page_id or ""):
        return jsonify({"error": "Invalid page id"}), 400

    data = request.get_json(silent=True) or {}
    body = (data.get("body") or "").strip()
    parent_id = data.get("parent_id")

    if not body:
        return jsonify({"error": "body required"}), 400
    if len(body.encode("utf-8")) > MAX_BODY:
        return jsonify({"error": f"body too long (max {MAX_BODY} bytes)"}), 400

    with get_db() as conn:
        page = conn.execute("SELECT id FROM wiki_pages WHERE id = ?", (page_id,)).fetchone()
        if not page:
            return jsonify({"error": "Page not found"}), 404

        if parent_id is not None:
            if not isinstance(parent_id, int):
                return jsonify({"error": "parent_id must be an integer"}), 400
            parent = conn.execute(
                "SELECT id FROM wiki_comments WHERE id = ? AND page_id = ?",
                (parent_id, page_id),
            ).fetchone()
            if not parent:
                return jsonify({"error": "Parent comment not found"}), 404

        cur = conn.execute("""
            INSERT INTO wiki_comments (page_id, user_id, parent_id, body)
            VALUES (?, ?, ?, ?)
        """, (page_id, g.user_id, parent_id, body))
        cid = cur.lastrowid
        row = conn.execute("""
            SELECT c.id, c.user_id, c.parent_id, c.body, c.edited_at, c.deleted,
                   c.created_at, u.username
            FROM wiki_comments c JOIN users u ON u.id = c.user_id
            WHERE c.id = ?
        """, (cid,)).fetchone()

    return jsonify(_row_to_dict(row)), 201


@wc_bp.route("/<page_id>/comments/<int:comment_id>", methods=["PATCH"])
@require_auth
def edit_comment(page_id, comment_id):
    if not PAGE_ID_RE.match(page_id or ""):
        return jsonify({"error": "Invalid page id"}), 400

    data = request.get_json(silent=True) or {}
    body = (data.get("body") or "").strip()
    if not body:
        return jsonify({"error": "body required"}), 400
    if len(body.encode("utf-8")) > MAX_BODY:
        return jsonify({"error": "body too long"}), 400

    with get_db() as conn:
        row = conn.execute(
            "SELECT user_id FROM wiki_comments WHERE id = ? AND page_id = ?",
            (comment_id, page_id),
        ).fetchone()
        if not row:
            return jsonify({"error": "Comment not found"}), 404
        if row["user_id"] != g.user_id:
            return jsonify({"error": "Only the author can edit"}), 403
        conn.execute(
            "UPDATE wiki_comments SET body = ?, edited_at = CURRENT_TIMESTAMP WHERE id = ?",
            (body, comment_id),
        )
        updated = conn.execute("""
            SELECT c.id, c.user_id, c.parent_id, c.body, c.edited_at, c.deleted,
                   c.created_at, u.username
            FROM wiki_comments c JOIN users u ON u.id = c.user_id
            WHERE c.id = ?
        """, (comment_id,)).fetchone()
    return jsonify(_row_to_dict(updated))


@wc_bp.route("/<page_id>/comments/<int:comment_id>", methods=["DELETE"])
@require_auth
def delete_comment(page_id, comment_id):
    if not PAGE_ID_RE.match(page_id or ""):
        return jsonify({"error": "Invalid page id"}), 400
    with get_db() as conn:
        row = conn.execute(
            "SELECT user_id FROM wiki_comments WHERE id = ? AND page_id = ?",
            (comment_id, page_id),
        ).fetchone()
        if not row:
            return jsonify({"error": "Comment not found"}), 404
        if row["user_id"] != g.user_id:
            return jsonify({"error": "Only the author can delete"}), 403
        conn.execute(
            "UPDATE wiki_comments SET deleted = 1, body = '', "
            "edited_at = CURRENT_TIMESTAMP WHERE id = ?",
            (comment_id,),
        )
    return jsonify({"deleted": comment_id, "tombstone": True})
