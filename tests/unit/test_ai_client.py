"""供应商适配层测试（见 02 §9.1 AI8–AI12）。

全部打桩：不联网、不需要 Key、不读取真实图片。
"""

import json
from types import SimpleNamespace

import pytest
from openai import APIConnectionError, APIStatusError, APITimeoutError

import app.ai.client as ai_client
from app.utils.errors import AiProviderError, InvalidAiResponse


@pytest.fixture(autouse=True)
def _reset_client(monkeypatch):
    """每个用例都从干净的单例开始，避免 Key 在用例之间泄漏。"""
    monkeypatch.setattr(ai_client, "_client", None, raising=False)


@pytest.fixture
def image(tmp_path):
    path = tmp_path / "meal.jpg"
    path.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg-bytes")
    return str(path)


def _resp(content, finish_reason="stop"):
    return SimpleNamespace(
        choices=[SimpleNamespace(finish_reason=finish_reason,
                                 message=SimpleNamespace(content=content))]
    )


def _stub(monkeypatch, *, content="", finish_reason="stop", error=None):
    def create(**kwargs):
        if error is not None:
            raise error
        return _resp(content, finish_reason)

    fake = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    monkeypatch.setattr(ai_client, "_get_client", lambda: fake)


# ── 正常解析 ───────────────────────────────────────────────
def test_parses_valid_json(monkeypatch, image):
    payload = {"schema_version": "1.0", "status": "success", "foods": [], "warnings": []}
    _stub(monkeypatch, content=json.dumps(payload))
    assert ai_client.call_vision_api(image, "p") == payload


# ── JSON Output 兜底：内容被替换成空格 ─────────────────────
def test_blank_content_is_not_json(monkeypatch, image):
    _stub(monkeypatch, content="   ")
    with pytest.raises(InvalidAiResponse) as exc:
        ai_client.call_vision_api(image, "p")
    assert exc.value.details["reason"] == "not_json"


# ── 截断不重试 ─────────────────────────────────────────────
def test_truncated_is_not_retried(monkeypatch, image):
    calls = []

    def create(**kwargs):
        calls.append(1)
        return _resp('{"foods": [', finish_reason="length")

    fake = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(ai_client, "_get_client", lambda: fake)

    with pytest.raises(InvalidAiResponse) as exc:
        ai_client.call_vision_api(image, "p")
    assert exc.value.details["reason"] == "truncated"
    assert len(calls) == 1


# ── 内容过滤 ───────────────────────────────────────────────
def test_content_filter(monkeypatch, image):
    _stub(monkeypatch, content="{}", finish_reason="content_filter")
    with pytest.raises(InvalidAiResponse) as exc:
        ai_client.call_vision_api(image, "p")
    assert exc.value.details["reason"] == "content_filtered"


# ── 重试：超时恰好 1 次 ────────────────────────────────────
@pytest.mark.parametrize("reason", ["timeout", "network", "provider_5xx", "not_json"])
def test_retryable_reasons_retry_once(monkeypatch, image, reason):
    calls = []

    def boom(path, prompt):
        calls.append(1)
        raise AiProviderError("boom", details={"reason": reason})

    monkeypatch.setattr(ai_client, "_call_sdk_once", boom)
    with pytest.raises(AiProviderError):
        ai_client.call_vision_api(image, "p")
    assert len(calls) == 2


# ── 重试：401 / 402 不重试 ────────────────────────────────
@pytest.mark.parametrize("reason", ["auth", "insufficient_balance", "provider_4xx", "file_missing"])
def test_non_retryable_reasons_fail_fast(monkeypatch, image, reason):
    calls = []

    def boom(path, prompt):
        calls.append(1)
        raise AiProviderError("boom", details={"reason": reason})

    monkeypatch.setattr(ai_client, "_call_sdk_once", boom)
    with pytest.raises(AiProviderError):
        ai_client.call_vision_api(image, "p")
    assert len(calls) == 1


# ── 429：等 2 秒后重试 1 次 ───────────────────────────────
def test_rate_limited_sleeps_then_retries(monkeypatch, image):
    calls = []
    slept = []

    def boom(path, prompt):
        calls.append(1)
        raise AiProviderError("boom", details={"reason": "rate_limited"})

    monkeypatch.setattr(ai_client, "_call_sdk_once", boom)
    monkeypatch.setattr(ai_client.time, "sleep", lambda s: slept.append(s))

    with pytest.raises(AiProviderError):
        ai_client.call_vision_api(image, "p")
    assert len(calls) == 2
    assert slept == [ai_client.RATE_LIMIT_BACKOFF_SECONDS]


# ── HTTP 状态码 → reason ─────────────────────────────────
class _FakeStatus(APIStatusError):
    def __init__(self, code):
        self.status_code = code


@pytest.mark.parametrize(
    ("code", "reason"),
    [(401, "auth"), (402, "insufficient_balance"), (429, "rate_limited"),
     (500, "provider_5xx"), (503, "provider_5xx"), (400, "provider_4xx"), (422, "provider_4xx")],
)
def test_classify_status_codes(code, reason):
    assert ai_client._classify(_FakeStatus(code)) == reason


def test_classify_timeout_and_network():
    assert ai_client._classify(APITimeoutError(request=None)) == "timeout"
    assert ai_client._classify(APIConnectionError(request=None)) == "network"


# ── SDK 抛 5xx 会被映射成 provider_5xx 并重试一次 ─────────
def test_sdk_error_is_wrapped_and_retried(monkeypatch, image):
    calls = []

    def create(**kwargs):
        calls.append(1)
        raise _FakeStatus(503)

    fake = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    monkeypatch.setattr(ai_client, "_get_client", lambda: fake)

    with pytest.raises(AiProviderError) as exc:
        ai_client.call_vision_api(image, "p")
    assert exc.value.details["reason"] == "provider_5xx"
    assert len(calls) == 2


# ── 缺 Key 时立即报错，且不发请求 ─────────────────────────
def test_missing_api_key(monkeypatch, image):
    monkeypatch.delenv("AI_API_KEY", raising=False)
    with pytest.raises(AiProviderError) as exc:
        ai_client._get_client()
    assert exc.value.details["reason"] == "missing_api_key"


# ── 文件不存在 ─────────────────────────────────────────────
def test_missing_image_file(monkeypatch, tmp_path):
    monkeypatch.setenv("AI_API_KEY", "sk-test")
    with pytest.raises(AiProviderError) as exc:
        ai_client.call_vision_api(str(tmp_path / "nope.jpg"), "p")
    assert exc.value.details["reason"] == "file_missing"
