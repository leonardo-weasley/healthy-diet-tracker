"""DeepSeek 供应商适配层——全项目唯一允许 import openai 的文件（见 ``02`` §8.3）。

配置全部来自环境变量（``.env`` 由项目根目录加载）：
    AI_API_KEY           必填，DeepSeek 的 Key
    AI_BASE_URL          默认 https://api.deepseek.com
    AI_MODEL             默认 deepseek-flash（唯一支持图片的模型；v4-pro 不支持）
    AI_TIMEOUT_SECONDS   默认 30
"""

import base64
import json
import logging
import os
import time
from pathlib import Path

from openai import APIConnectionError, APIStatusError, APITimeoutError, OpenAI

from ..utils.errors import AiProviderError, InvalidAiResponse

log = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-flash"
DEFAULT_TIMEOUT_SECONDS = 30.0
MAX_OUTPUT_TOKENS = 2048
RATE_LIMIT_BACKOFF_SECONDS = 2.0

# 仓库根：app/ai/client.py -> app/ai -> app -> root
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 明确不支持图片输入的型号，配到 /analyze 上要立刻报错（见 resolve_model）
NON_VISION_MODELS = {"deepseek-v4-pro", "deepseek-reasoner"}

# 只有这些 reason 允许重试（与 02 §6.2 一一对应）
RETRYABLE_REASONS = {"timeout", "network", "rate_limited", "provider_5xx", "not_json"}

_MIME_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    """懒初始化单例。Key 缺失时立即抛出，不延到请求时。"""
    global _client
    if _client is not None:
        return _client
    api_key = os.getenv("AI_API_KEY", "").strip()
    if not api_key:
        raise AiProviderError(
            "AI_API_KEY is not configured.",
            details={"reason": "missing_api_key"},
        )
    _client = OpenAI(
        api_key=api_key,
        base_url=os.getenv("AI_BASE_URL", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL,
        timeout=float(os.getenv("AI_TIMEOUT_SECONDS") or DEFAULT_TIMEOUT_SECONDS),
        # 重试由 call_vision_api 统一实现；SDK 内建重试会破坏"最多 2 次尝试"
        max_retries=0,
    )
    return _client


def _classify(exc: Exception) -> str:
    """把 SDK 的异常翻译成契约里的 reason（见 02 §5.3）。"""
    if isinstance(exc, APITimeoutError):  # 注意：它也是 APIConnectionError 的子类
        return "timeout"
    if isinstance(exc, APIConnectionError):
        return "network"
    if isinstance(exc, APIStatusError):
        code = exc.status_code
        if code == 401:
            return "auth"
        if code == 402:
            return "insufficient_balance"
        if code == 429:
            return "rate_limited"
        if 500 <= code <= 599:
            return "provider_5xx"
        return "provider_4xx"
    return "unknown"


def resolve_model() -> str:
    """读出要用的模型名，并挡掉明确不支持图片的型号。

    `deepseek-v4-pro` 不支持图片输入，配错只会得到泛化的 400，排查成本很高；
    在这里提前拦掉，报错能直接指出是配置问题。
    """
    model = (os.getenv("AI_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    if model in NON_VISION_MODELS:
        raise AiProviderError(
            f"AI_MODEL={model!r} does not accept image input; "
            f"use {DEFAULT_MODEL!r} for /analyze.",
            details={"reason": "model_not_supported", "model": model},
        )
    return model


def resolve_image_path(image_path: str) -> Path:
    """相对路径先按当前目录找，找不到再按仓库根找。

    Flask 可能从别的目录启动，`uploads/...` 这种仓库相对路径不能只看 CWD。
    """
    path = Path(image_path)
    if path.is_absolute() or path.is_file():
        return path
    fallback = PROJECT_ROOT / path
    return fallback if fallback.is_file() else path


def _build_user_content(image_path: str, prompt: str) -> list[dict]:
    """图片必须是 base64 data URL，且只能放在 user 消息里。"""
    path = resolve_image_path(image_path)
    if not path.is_file():
        raise AiProviderError(
            "Image file not found on disk.",
            details={"reason": "file_missing", "path": str(path),
                     "cwd": str(Path.cwd())},
        )
    mime = _MIME_BY_SUFFIX.get(path.suffix.lower(), "image/jpeg")
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}},
    ]


def _call_sdk_once(image_path: str, prompt: str) -> dict:
    """发一次请求。仅 json.loads，不做业务校验。"""
    client = _get_client()
    # 配置类错误在 try 之外抛，否则会被下面的 except 收口成 provider_error
    model = resolve_model()
    content = _build_user_content(image_path, prompt)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content}],
            response_format={"type": "json_object"},
            temperature=0.0,  # 非思考模式才有效；0 让同一张图的结果尽量可复现
            max_tokens=MAX_OUTPUT_TOKENS,
            extra_body={"thinking": {"type": "disabled"}},  # 默认是开的，必须显式关
        )
    except Exception as exc:  # SDK 异常类型较杂，统一收口后再细分
        raise AiProviderError(
            "The AI provider call failed.",
            details={"reason": _classify(exc), "status_code": getattr(exc, "status_code", None)},
        ) from exc

    choice = response.choices[0] if response.choices else None
    if choice is None:
        raise InvalidAiResponse(
            "The AI provider returned no choices.",
            details={"reason": "not_json"},
        )
    if choice.finish_reason == "length":
        raise InvalidAiResponse(
            "The AI response was truncated by max_tokens.",
            details={"reason": "truncated"},
        )
    if choice.finish_reason == "content_filter":
        raise InvalidAiResponse(
            "The AI response was blocked by the content filter.",
            details={"reason": "content_filtered"},
        )

    text = (choice.message.content or "").strip()
    if not text:
        # JSON 模式下输出不是 JSON 时，API 会用空格替换 → content 可能全空
        raise InvalidAiResponse(
            "The AI returned empty content.",
            details={"reason": "not_json"},
        )
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise InvalidAiResponse(
            "The AI response was not valid JSON.",
            details={"reason": "not_json", "preview": text[:200]},
        ) from exc


def call_vision_api(image_path: str, prompt: str) -> dict:
    """输入：本地图片路径 + 提示词全文。

    输出：模型返回的原始 dict（仅 json.loads，不做业务校验）。
    重试策略（与 02 §6.2 一致）：最多 2 次尝试，只有 RETRYABLE_REASONS 才重试。
    抛出：AiProviderError / InvalidAiResponse
    """
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            return _call_sdk_once(image_path, prompt)
        except (AiProviderError, InvalidAiResponse) as exc:
            last_exc = exc
            reason = (exc.details or {}).get("reason", "")
            if attempt == 0 and reason in RETRYABLE_REASONS:
                if reason == "rate_limited":
                    time.sleep(RATE_LIMIT_BACKOFF_SECONDS)
                log.warning("retrying AI call reason=%s attempt=%d", reason, attempt + 2)
                continue
            raise
    raise last_exc  # pragma: no cover - 循环必然 return 或 raise

