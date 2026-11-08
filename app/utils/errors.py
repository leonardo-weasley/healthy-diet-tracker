class ApiError(Exception):
    def __init__(self, code, message, http_status=400, details=None):
        super().__init__(message)
        self.code, self.message = code, message
        self.http_status, self.details = http_status, details


class _TypedError(ApiError):
    code = ''
    http_status = 400

    def __init__(self, message=None, details=None):
        if message is None:
            message = self.code.replace('_', ' ').capitalize() + '.'
        super().__init__(self.code, message, self.http_status, details)


class InvalidRequest(_TypedError):
    code = 'INVALID_REQUEST'


class InvalidImage(_TypedError):
    code = 'INVALID_IMAGE'


class ImageTooLarge(_TypedError):
    code, http_status = 'IMAGE_TOO_LARGE', 413


class UnsupportedMediaType(_TypedError):
    code, http_status = 'UNSUPPORTED_MEDIA_TYPE', 415


class InvalidWeight(_TypedError):
    code, http_status = 'INVALID_WEIGHT', 422


class FoodNotFound(_TypedError):
    code, http_status = 'FOOD_NOT_FOUND', 422


class MealNotFound(_TypedError):
    code, http_status = 'MEAL_NOT_FOUND', 404


class AiProviderError(_TypedError):
    code, http_status = 'AI_PROVIDER_ERROR', 502


class InvalidAiResponse(_TypedError):
    code, http_status = 'INVALID_AI_RESPONSE', 502


class DatabaseError(_TypedError):
    code, http_status = 'DATABASE_ERROR', 500
