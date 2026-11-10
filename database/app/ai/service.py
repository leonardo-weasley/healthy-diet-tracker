"""AI provider boundary.

Member 2 replaces this module with the real provider call.  The contract is
intentionally tiny so the rest of the system (and the tests) can stub it:

``analyze_food(image_bytes, content_type) -> dict``
    ``{"provider": "mock", "detected": [
        {"food_name": "cooked_white_rice", "display_name": "White rice",
         "weight_g": 180.0, "confidence": 0.92},
        ...
    ]}``

Raise :class:`~app.utils.errors.AIProviderError` for provider/network
failures and :class:`~app.utils.errors.InvalidAIResponse` for malformed
outputs.
"""

from __future__ import annotations

from ..utils.errors import AIProviderError


def analyze_food(image_bytes: bytes, content_type: str) -> dict:
    raise AIProviderError(
        "No AI provider is configured. Set one up before using image analysis."
    )
