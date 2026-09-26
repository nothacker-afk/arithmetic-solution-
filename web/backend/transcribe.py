"""Voice transcription (Phase 40).

Uses OpenAI's Whisper API when OPENAI_API_KEY is set. Otherwise returns
a clear "not configured" error so the frontend can hide the feature.

Because the client uploads E2E-encrypted audio, transcription only
works when the client also uploads the plaintext blob to /api/transcribe
(in a one-shot request, no storage). If the client prefers to keep the
audio E2E-only, transcription is impossible — that's the tradeoff.

Endpoints:
    POST /api/transcribe             {voice_id}        transcribe existing clip
    POST /api/transcribe/upload      multipart file    transcribe without storing
    GET  /api/transcribe/available                     is the feature enabled?
"""
import base64
import io
import os

from flask import Blueprint, request, jsonify, g

from .auth import require_auth
from .database import get_db
from .rate_limit import rate_limit
from .logging_config import get_logger

log = get_logger("web.transcribe")

transcribe_bp = Blueprint("transcribe", __name__, url_prefix="/api/transcribe")

MAX_AUDIO_BYTES = int(os.environ.get("MAX_TRANSCRIBE_BYTES", str(5 * 1024 * 1024)))
_MODEL = os.environ.get("WHISPER_MODEL", "whisper-1")


def _openai_available() -> bool:
    if not os.environ.get("OPENAI_API_KEY"):
        return False
    try:
        import openai  # noqa: F401
        return True
    except ImportError:
        return False


@transcribe_bp.route("/available", methods=["GET"])
def available():
    return jsonify({
        "available": _openai_available(),
        "model": _MODEL if _openai_available() else None,
    })


def _transcribe_bytes(audio_bytes: bytes, mime: str, lang: str | None = None):
    """Call the Whisper API. Returns (text, language)."""
    from openai import OpenAI
    client = OpenAI()
    # Whisper expects a file-like with a name; format hints help
    ext = "webm" if "webm" in (mime or "") else "ogg" if "ogg" in (mime or "") else "wav"
    buf = io.BytesIO(audio_bytes)
    buf.name = f"clip.{ext}"
    kwargs = {"model": _MODEL, "file": buf}
    if lang:
        kwargs["language"] = lang
    resp = client.audio.transcriptions.create(**kwargs)
    # resp.text in recent SDKs; older: dict
    text = getattr(resp, "text", None) or (resp.get("text") if isinstance(resp, dict) else "")
    return (text or "").strip(), lang or ""


@transcribe_bp.route("", methods=["POST"])
@require_auth
@rate_limit(max_calls=10, window_seconds=60)
def transcribe_existing():
    if not _openai_available():
        return jsonify({"error": "Transcription not configured on this server"}), 503

    data = request.get_json(silent=True) or {}
    voice_id = (data.get("voice_id") or "").strip()
    if not voice_id:
        return jsonify({"error": "voice_id required"}), 400

    # Load blob from disk (only works for non-encrypted clips)
    from .voice import _voice_dir
    with get_db() as conn:
        row = conn.execute(
            "SELECT encrypted FROM voice_clips WHERE id = ?", (voice_id,),
        ).fetchone()
    if not row:
        return jsonify({"error": "Voice clip not found"}), 404
    if row["encrypted"]:
        return jsonify({
            "error": "Clip is E2E-encrypted — send plaintext via /api/transcribe/upload instead"
        }), 400

    path = _voice_dir() / f"{voice_id}.bin"
    if not path.exists():
        return jsonify({"error": "Blob missing"}), 410
    audio = path.read_bytes()

    try:
        text, lang = _transcribe_bytes(audio, "audio/webm")
    except Exception as e:
        log.warning("transcribe failed: %s", e)
        return jsonify({"error": f"Transcription failed: {e}"}), 500

    # Cache transcript on the clip
    with get_db() as conn:
        conn.execute(
            "UPDATE voice_clips SET transcript = ?, transcript_lang = ? WHERE id = ?",
            (text, lang, voice_id),
        )

    return jsonify({"voice_id": voice_id, "text": text, "language": lang})


@transcribe_bp.route("/upload", methods=["POST"])
@require_auth
@rate_limit(max_calls=10, window_seconds=60)
def transcribe_upload():
    """Transcribe without persisting. Client sends plaintext audio bytes."""
    if not _openai_available():
        return jsonify({"error": "Transcription not configured on this server"}), 503

    data = request.get_json(silent=True) or {}
    audio_b64 = data.get("audio_b64")
    mime = (data.get("mime") or "audio/webm")[:64]
    lang = data.get("language") or None

    if not isinstance(audio_b64, str) or not audio_b64:
        return jsonify({"error": "audio_b64 required"}), 400
    try:
        audio = base64.b64decode(audio_b64, validate=True)
    except Exception:
        return jsonify({"error": "audio_b64 must be base64"}), 400
    if len(audio) > MAX_AUDIO_BYTES:
        return jsonify({"error": f"Audio exceeds {MAX_AUDIO_BYTES} byte limit"}), 413

    try:
        text, out_lang = _transcribe_bytes(audio, mime, lang)
    except Exception as e:
        log.warning("transcribe/upload failed: %s", e)
        return jsonify({"error": f"Transcription failed: {e}"}), 500

    return jsonify({"text": text, "language": out_lang})
