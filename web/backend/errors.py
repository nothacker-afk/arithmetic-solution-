"""Global error handlers."""
from flask import jsonify

from .logging_config import get_logger

log = get_logger("web.errors")


def install_error_handlers(app) -> None:
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": "Bad request", "detail": str(e)}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({"error": "Unauthorized"}), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({"error": "Forbidden"}), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(429)
    def rate_limited(e):
        return jsonify({"error": "Rate limit exceeded"}), 429

    @app.errorhandler(500)
    def internal_error(e):
        log.error("unhandled 500", exc_info=True)
        return jsonify({"error": "Internal server error"}), 500

    @app.errorhandler(Exception)
    def unhandled(e):
        log.error("unhandled exception", exc_info=True)
        return jsonify({"error": "Internal server error", "detail": str(e)}), 500
