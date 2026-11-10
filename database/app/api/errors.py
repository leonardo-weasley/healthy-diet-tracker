"""JSON error envelopes for the API layer."""

from __future__ import annotations

import logging

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge

from ..utils.errors import ApiError, ImageTooLarge, InternalError

log = logging.getLogger(__name__)

_HTTP_CODES = {
    400: "INVALID_REQUEST",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    415: "UNSUPPORTED_MEDIA_TYPE",
    413: "IMAGE_TOO_LARGE",
}


def _envelope(error: ApiError):
    return jsonify({"error": error.to_dict()}), error.http_status


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ApiError)
    def handle_api_error(exc: ApiError):
        return _envelope(exc)

    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_too_large(_exc):
        return _envelope(ImageTooLarge())

    @app.errorhandler(HTTPException)
    def handle_http_exception(exc: HTTPException):
        code = _HTTP_CODES.get(exc.code, "HTTP_ERROR")
        return (
            jsonify(
                {
                    "error": {
                        "code": code,
                        "message": exc.description or exc.name,
                        "details": {},
                    }
                }
            ),
            exc.code or 500,
        )

    @app.errorhandler(Exception)
    def handle_unexpected(exc: Exception):
        log.exception("unhandled exception", exc_info=exc)
        return _envelope(InternalError())
