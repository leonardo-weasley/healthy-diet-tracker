"""Application error types and the JSON error envelope.

The error codes and HTTP statuses follow ``05_DATABASE_AND_TESTING`` §9.4 and
the shared contract in ``00_MAIN_TECHNICAL_ROUTE`` §G.2.  Member 1 owns the
service layer but this module is the single source of truth every layer
raises from, so tests can assert on ``error.code`` instead of strings.
"""

from __future__ import annotations


class ApiError(Exception):
    """Base class for errors that are safe to expose to API clients."""

    code = "INTERNAL_ERROR"
    http_status = 500
    default_message = "An unexpected error occurred."

    def __init__(self, message: str | None = None, details: dict | None = None):
        self.message = message or self.default_message
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


class InvalidRequest(ApiError):
    code = "INVALID_REQUEST"
    http_status = 400
    default_message = "The request is invalid."


class InvalidImage(ApiError):
    code = "INVALID_IMAGE"
    http_status = 400
    default_message = "The uploaded image could not be read."


class ImageTooLarge(ApiError):
    code = "IMAGE_TOO_LARGE"
    http_status = 413
    default_message = "The uploaded image is too large."


class UnsupportedMediaType(ApiError):
    code = "UNSUPPORTED_MEDIA_TYPE"
    http_status = 415
    default_message = "Only JPEG, PNG and WebP images are supported."


class InvalidWeight(ApiError):
    code = "INVALID_WEIGHT"
    http_status = 400
    default_message = "Item weight must be greater than 0 g and at most 5000 g."


class FoodNotFound(ApiError):
    code = "FOOD_NOT_FOUND"
    http_status = 422
    default_message = "None of the detected foods exists in the food database."


class MealNotFound(ApiError):
    code = "MEAL_NOT_FOUND"
    http_status = 404
    default_message = "The requested meal does not exist."


class AIProviderError(ApiError):
    code = "AI_PROVIDER_ERROR"
    http_status = 502
    default_message = "The AI provider failed to process the image."


class InvalidAIResponse(ApiError):
    code = "INVALID_AI_RESPONSE"
    http_status = 502
    default_message = "The AI provider returned an unusable response."


class DatabaseError(ApiError):
    code = "DATABASE_ERROR"
    http_status = 500
    default_message = "A database operation failed."


class InternalError(ApiError):
    code = "INTERNAL_ERROR"
    http_status = 500
    default_message = "An unexpected error occurred."
