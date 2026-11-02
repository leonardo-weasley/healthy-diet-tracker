"""契约 A 的 schema 与状态判定测试（见 02 §9.1 AI1–AI7、AI13、AI14）。

全部离线：不联网、不需要 Key。
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

import app.ai.image_analyzer as analyzer
from app.ai.prompts import FOOD_NAME_HINTS, build_prompt
from app.ai.schemas import AIAnalysis

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
MOCK = json.loads((FIXTURES / "mock_ai_result.json").read_text(encoding="utf-8"))
MOCK_PARTIAL = json.loads((FIXTURES / "mock_ai_partial.json").read_text(encoding="utf-8"))


def _feed(raw):
    """把 raw 直接当作模型返回值喂给 analyze_food（绕过 SDK）。"""
    original = analyzer.call_vision_api
    analyzer.call_vision_api = lambda image_path, prompt: raw
    try:
        return analyzer.analyze_food("dummy.jpg")
    finally:
        analyzer.call_vision_api = original


# ── AI1 合法 JSON 通过 ──────────────────────────────────────
def test_valid_payload_passes():
    analysis = AIAnalysis.model_validate(MOCK)
    assert analysis.status == "success"
    assert len(analysis.foods) == 2
    assert set(analysis.foods[0].model_dump()) == {
        "food_name", "display_name", "estimated_weight_g", "confidence", "notes",
    }


# ── AI2 重量是字符串 ────────────────────────────────────────
def test_weight_as_string_is_rejected():
    bad = json.loads(json.dumps(MOCK))
    bad["foods"][0]["estimated_weight_g"] = "180g"
    with pytest.raises(ValidationError):
        AIAnalysis.model_validate(bad)


# ── AI3 confidence 越界 ─────────────────────────────────────
@pytest.mark.parametrize("value", [1.5, -0.1])
def test_confidence_out_of_range(value):
    bad = json.loads(json.dumps(MOCK))
    bad["foods"][0]["confidence"] = value
    with pytest.raises(ValidationError):
        AIAnalysis.model_validate(bad)


# ── AI4 缺 display_name ─────────────────────────────────────
def test_missing_display_name_is_rejected():
    bad = json.loads(json.dumps(MOCK))
    del bad["foods"][0]["display_name"]
    with pytest.raises(ValidationError):
        AIAnalysis.model_validate(bad)


# ── AI5 空 foods + warnings ────────────────────────────────
def test_empty_foods_is_error_status():
    raw = {"schema_version": "1.0", "status": "success", "foods": [], "warnings": []}
    out = _feed(raw)
    assert out["status"] == "error"
    assert out["warnings"] == ["no_food_detected"]
    assert out["foods"] == []


# ── AI6 一项 food_name 为 null ─────────────────────────────
def test_partial_fixture_yields_partial():
    out = _feed(MOCK_PARTIAL)
    assert out["status"] == "partial"
    assert any(w.startswith("food_unrecognized: ") for w in out["warnings"])
    assert any(w.startswith("missing_weight: ") for w in out["warnings"])


# ── AI7 一项缺重量 ─────────────────────────────────────────
def test_missing_weight_yields_partial():
    raw = json.loads(json.dumps(MOCK))
    raw["foods"][1]["estimated_weight_g"] = None
    out = _feed(raw)
    assert out["status"] == "partial"
    assert any(w.startswith("missing_weight: Grilled chicken breast") for w in out["warnings"])


# ── AI13 模型自报 status 乱写 ──────────────────────────────
def test_bogus_model_status_is_ignored():
    raw = json.loads(json.dumps(MOCK))
    raw["status"] = "unknown"
    out = _feed(raw)
    assert out["status"] == "success"
    assert AIAnalysis.model_validate(raw).status == "unknown"


# ── AI14 模型自写的 warnings 被丢弃 ────────────────────────
def test_model_warnings_are_discarded():
    raw = json.loads(json.dumps(MOCK))
    raw["warnings"] = ["blurry_image", "weights are rough"]
    out = _feed(raw)
    assert out["status"] == "success"
    assert out["warnings"] == []


# ── 额外字段被忽略，不导致 502 ─────────────────────────────
def test_extra_fields_are_ignored():
    raw = json.loads(json.dumps(MOCK))
    raw["foods"][0]["calories_kcal"] = 234.0
    analysis = AIAnalysis.model_validate(raw)
    assert "calories_kcal" not in analysis.foods[0].model_dump()


# ── 提示词与食品名单 ───────────────────────────────────────
def test_prompt_contains_json_example_and_hints():
    prompt = build_prompt()
    assert "json" in prompt
    assert "cooked_white_rice" in prompt
    assert "NEVER estimate calories" in prompt
    assert "{food_name_hints}" not in prompt


def test_food_name_hints_exist_in_database():
    db_path = Path(__file__).resolve().parents[2] / "app" / "nutrition" / "food_database.json"
    if not db_path.is_file():
        pytest.skip("成员3 的 food_database.json 还没落地")
    known = {row["food_name"] for row in json.loads(db_path.read_text(encoding="utf-8"))["foods"]}
    hints = {h.strip() for h in FOOD_NAME_HINTS.replace("\n", " ").split(",") if h.strip()}
    assert hints <= known, f"not in food_database.json: {sorted(hints - known)}"
