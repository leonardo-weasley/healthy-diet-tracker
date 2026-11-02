"""统一异常体系（成员1 主责）。

⚠️ 占位实现：内容与 ``00`` §G.2 逐字一致，成员1 提交正式版本时直接覆盖本文件即可，
调用方（``app/ai``、``app/nutrition``、``app/database``）不需要任何改动。
"""


class ApiError(Exception):
    def __init__(self, code: str, message: str, http_status: int = 400, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status
        self.details = details


class InvalidImage(ApiError):
    """code=INVALID_IMAGE, http_status=400"""

    def __init__(self, message: str = "Invalid image.", details=None):
        super().__init__("INVALID_IMAGE", message, 400, details)


class ImageTooLarge(ApiError):
    """code=IMAGE_TOO_LARGE, http_status=413"""

    def __init__(self, message: str = "Image exceeds size limit.", details=None):
        super().__init__("IMAGE_TOO_LARGE", message, 413, details)


class UnsupportedMediaType(ApiError):
    """code=UNSUPPORTED_MEDIA_TYPE, http_status=415"""

    def __init__(self, message: str = "Unsupported media type.", details=None):
        super().__init__("UNSUPPORTED_MEDIA_TYPE", message, 415, details)


class InvalidRequest(ApiError):
    """code=INVALID_REQUEST, http_status=400"""

    def __init__(self, message: str = "Invalid request.", details=None):
        super().__init__("INVALID_REQUEST", message, 400, details)


class InvalidWeight(ApiError):
    """code=INVALID_WEIGHT, http_status=422"""

    def __init__(self, message: str = "Invalid weight value.", details=None):
        super().__init__("INVALID_WEIGHT", message, 422, details)


class FoodNotFound(ApiError):
    """code=FOOD_NOT_FOUND, http_status=422"""

    def __init__(self, message: str = "Food not found in database.", details=None):
        super().__init__("FOOD_NOT_FOUND", message, 422, details)


class MealNotFound(ApiError):
    """code=MEAL_NOT_FOUND, http_status=404"""

    def __init__(self, message: str = "Meal not found.", details=None):
        super().__init__("MEAL_NOT_FOUND", message, 404, details)


class AiProviderError(ApiError):
    """code=AI_PROVIDER_ERROR, http_status=502"""

    def __init__(self, message: str = "AI provider error.", details=None):
        super().__init__("AI_PROVIDER_ERROR", message, 502, details)


class InvalidAiResponse(ApiError):
    """code=INVALID_AI_RESPONSE, http_status=502"""

    def __init__(self, message: str = "Invalid AI response.", details=None):
        super().__init__("INVALID_AI_RESPONSE", message, 502, details)


class DatabaseError(ApiError):
    """code=DATABASE_ERROR, http_status=500"""

    def __init__(self, message: str = "Database error.", details=None):
        super().__init__("DATABASE_ERROR", message, 500, details)
