"""Tests for study_plan_skill — metadata, executor dispatch, parser, and handler."""

import json
from collections.abc import Callable
from unittest.mock import patch

import pytest

from core.router import RouteIntent
from core.tracing import TraceRecord, generate_trace_id
from schema import ChatMessage, UserInput
from skills.executor import try_skill_fast_path
from skills.registry import default_registry


def _make_user_input(message: str) -> UserInput:
    return UserInput(message=message)


def _make_trace_record() -> TraceRecord:
    return TraceRecord(trace_id=generate_trace_id())


# ---------------------------------------------------------------------------
# 1. metadata in registry
# ---------------------------------------------------------------------------

def test_study_plan_skill_in_registry():
    skill = default_registry.get_skill("study_plan")

    assert skill.name == "study_plan"
    assert skill.intent == RouteIntent.STUDY_PLAN.value
    assert skill.fast_path_enabled is True
    assert skill.fast_path_handler_name == "_maybe_handle_study_plan_fast_path"
    assert "generate_study_plan" in skill.bound_tools
    assert skill.response_template_name == "format_study_plan_fast_path_response"
    assert len(skill.examples) > 0


# ---------------------------------------------------------------------------
# 2. trigger keywords
# ---------------------------------------------------------------------------

def test_study_plan_skill_trigger_keywords():
    skill = default_registry.get_skill("study_plan")
    keywords = skill.trigger_keywords

    assert len(keywords) > 0
    required = ["学习计划", "复习", "备考", "面试"]
    for word in required:
        assert word in keywords, f"trigger_keywords must contain '{word}'"
    assert any(w in keywords for w in ("规划", "学习路线")), (
        "trigger_keywords must contain '规划' or '学习路线'"
    )


# ---------------------------------------------------------------------------
# 3. executor dispatch
# ---------------------------------------------------------------------------

def test_study_plan_executor_dispatches():
    def fake_handler(
        _user_input: UserInput, _trace_record: TraceRecord
    ) -> ChatMessage | None:
        return ChatMessage(type="ai", content="[study plan result]")

    handlers = {"_maybe_handle_study_plan_fast_path": fake_handler}
    user_input = _make_user_input("帮我制定一份 7 天 AI Agent 学习计划")
    trace_record = _make_trace_record()

    result = try_skill_fast_path(user_input, trace_record, handlers)

    assert result is not None
    assert result.type == "ai"
    assert trace_record.skill_name == "study_plan"
    assert trace_record.skill_fallback_reason is None


# ---------------------------------------------------------------------------
# 4. parameter parser
# ---------------------------------------------------------------------------

def test_parse_study_plan_params_extracts_days_and_goal():
    from service.service import _parse_study_plan_fast_path_params

    params = _parse_study_plan_fast_path_params("帮我制定一份 7 天 AI Agent 学习计划")

    assert params["days"] == 7
    assert params["goal"] is not None
    assert "AI Agent" in params["goal"]


def test_parse_study_plan_params_chinese_days():
    from service.service import _parse_study_plan_fast_path_params

    assert _parse_study_plan_fast_path_params("三天复习计划")["days"] == 3
    assert _parse_study_plan_fast_path_params("七天备考")["days"] == 7


def test_parse_study_plan_params_available_time():
    from service.service import _parse_study_plan_fast_path_params

    params = _parse_study_plan_fast_path_params("我明天下午没课，帮我安排学习")
    assert params["available_time"] == "明天"


def test_parse_study_plan_params_focus_topics():
    from service.service import _parse_study_plan_fast_path_params

    params = _parse_study_plan_fast_path_params("帮我制定 LangGraph 和 FastAPI 学习计划")

    assert params["focus_topics"] is not None
    assert "LangGraph" in params["focus_topics"]
    assert "FastAPI" in params["focus_topics"]


# ---------------------------------------------------------------------------
# 5. handler success
# ---------------------------------------------------------------------------

def test_study_plan_fast_path_success(monkeypatch):
    plan_json = json.dumps({
        "plan_title": "AI Agent 学习计划",
        "goal": "AI Agent",
        "duration_days": 7,
        "daily_plan": [
            {
                "day": "Day 1（2026-05-25，Monday）",
                "available_time": "19:30-22:00",
                "learning_topic": "LangGraph",
                "practice_task": "完成一个小任务",
                "review_task": "复盘",
                "expected_output": "学习笔记",
            }
        ],
        "final_suggestion": "请根据实际情况调整。",
    }, ensure_ascii=False)

    monkeypatch.setattr(
        "service.service.generate_study_plan_func",
        lambda **kwargs: plan_json,
    )

    from service.service import _maybe_handle_study_plan_fast_path

    user_input = _make_user_input("帮我制定一份 7 天 AI Agent 学习计划")
    trace_record = _make_trace_record()

    result = _maybe_handle_study_plan_fast_path(user_input, trace_record)

    assert result is not None
    assert result.type == "ai"
    assert "学习计划" in result.content
    assert trace_record.route == "study_plan_fast_path"
    assert trace_record.tool_calls[0]["name"] == "generate_study_plan"
    assert trace_record.prompt_tokens == 0
    assert trace_record.total_tokens == 0


# ---------------------------------------------------------------------------
# 6. default days when not specified
# ---------------------------------------------------------------------------

def test_study_plan_fast_path_uses_default_days(monkeypatch):
    captured_days = []

    def fake_generate(**kwargs):
        captured_days.append(kwargs.get("days"))
        return json.dumps({"plan_title": "test", "daily_plan": []}, ensure_ascii=False)

    monkeypatch.setattr("service.service.generate_study_plan_func", fake_generate)

    from service.service import _maybe_handle_study_plan_fast_path

    user_input = _make_user_input("帮我准备 AI Agent 面试学习路线")
    trace_record = _make_trace_record()

    result = _maybe_handle_study_plan_fast_path(user_input, trace_record)

    assert result is not None
    assert captured_days[0] == 7


# ---------------------------------------------------------------------------
# 7. vague query returns None
# ---------------------------------------------------------------------------

def test_study_plan_vague_query_returns_none():
    from service.service import _maybe_handle_study_plan_fast_path

    user_input = _make_user_input("帮我安排一下")
    trace_record = _make_trace_record()

    result = _maybe_handle_study_plan_fast_path(user_input, trace_record)

    assert result is None
    assert trace_record.route != "study_plan_fast_path"


# ---------------------------------------------------------------------------
# 8. non-study query returns None
# ---------------------------------------------------------------------------

def test_study_plan_non_study_query_returns_none():
    from service.service import _maybe_handle_study_plan_fast_path

    user_input = _make_user_input("我周一上午有什么课？")
    trace_record = _make_trace_record()

    result = _maybe_handle_study_plan_fast_path(user_input, trace_record)

    assert result is None
    assert trace_record.route != "study_plan_fast_path"


# ---------------------------------------------------------------------------
# 9. handler error fallback
# ---------------------------------------------------------------------------

def test_study_plan_handler_error_fallback(monkeypatch):
    monkeypatch.setattr(
        "service.service.generate_study_plan_func",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("tool failure")),
    )

    from service.service import _maybe_handle_study_plan_fast_path

    handlers = {
        "_maybe_handle_study_plan_fast_path": _maybe_handle_study_plan_fast_path,
    }
    user_input = _make_user_input("帮我制定一份 7 天 AI Agent 学习计划")
    trace_record = _make_trace_record()

    result = try_skill_fast_path(user_input, trace_record, handlers)

    assert result is None
    assert trace_record.skill_name is None
    assert trace_record.skill_fallback_reason == "handler_error"
