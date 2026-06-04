"""Centralized Flask error handlers."""

import logging

logger = logging.getLogger(__name__)


def register_error_handlers(app) -> None:
    """Register centralized error handlers on a Flask app."""

    @app.errorhandler(400)
    def bad_request(error):
        return _error_response("Bad request", 400)

    @app.errorhandler(404)
    def not_found(error):
        return _error_response("Resource not found", 404)

    @app.errorhandler(413)
    def file_too_large(error):
        return _error_response("File too large", 413)

    @app.errorhandler(500)
    def internal_error(error):
        logger.exception("Unhandled server error")
        return _error_response("Internal server error", 500)

    def _error_response(message: str, status: int):
        from flask import jsonify

        resp = jsonify({"error": message})
        resp.status_code = status
        return resp
