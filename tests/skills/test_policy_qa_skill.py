"""Tests for policy_qa_skill — metadata, executor dispatch, and fast-path handler."""

from collections.abc import Callable
from unittest.mock import patch

import pytest

from core.router import RouteIntent, route_query
from core.tracing import TraceRecord, generate_trace_id
from schema import ChatMessage, UserInput
from skills.definitions import BUILTIN_SKILLS
from skills.executor import try_skill_fast_path
from skills.registry import SkillRegistry, default_registry


def _make_user_input(message: str) -> UserInput:
    return UserInput(message=message)


def _make_trace_record() -> TraceRecord:
    return TraceRecord(trace_id=generate_trace_id())


# ---------------------------------------------------------------------------
# 1. policy_qa_skill is in the default registry
# ---------------------------------------------------------------------------

def test_policy_qa_skill_in_registry():
    skill = default_registry.get_skill("policy_qa")

    assert skill.name == "policy_qa"
    assert skill.intent == RouteIntent.POLICY.value
    assert skill.fast_path_enabled is True
    assert skill.fast_path_handler_name == "_maybe_handle_policy_qa_fast_path"
    assert "query_campus_policy" in skill.bound_tools
    assert len(skill.examples) > 0


# ---------------------------------------------------------------------------
# 2. trigger_keywords cover the main policy domains
# ---------------------------------------------------------------------------

def test_policy_qa_skill_trigger_keywords():
    skill = default_registry.get_skill("policy_qa")
    keywords = skill.trigger_keywords

    assert len(keywords) > 0, "trigger_keywords must not be empty"
    required = ["请假", "奖学金", "挂科", "宿舍"]
    for word in required:
        assert word in keywords, f"trigger_keywords must contain '{word}'"
    assert any(w in keywords for w in ("考试", "作弊")), (
        "trigger_keywords must contain '考试' or '作弊'"
    )


# ---------------------------------------------------------------------------
# 3. SkillExecutor dispatches to policy_qa
# ---------------------------------------------------------------------------

def test_policy_qa_executor_dispatches():
    def fake_policy_handler(
        _user_input: UserInput, _trace_record: TraceRecord
    ) -> ChatMessage | None:
        return ChatMessage(type="ai", content="[policy fast path result]")

    handlers = {
        "_maybe_handle_policy_qa_fast_path": fake_policy_handler,
    }
    user_input = _make_user_input("请假流程是什么？")
    trace_record = _make_trace_record()

    result = try_skill_fast_path(user_input, trace_record, handlers)

    assert result is not None
    assert result.type == "ai"
    assert trace_record.skill_name == "policy_qa"
    assert trace_record.skill_fallback_reason is None


# ---------------------------------------------------------------------------
# 4. real handler returns structured Markdown with source citation
# ---------------------------------------------------------------------------

def test_policy_qa_handler_success(monkeypatch):
    fake_markdown = (
        "## 简要结论\n"
        "已基于校园制度知识库检索结果整理如下。\n\n"
        "## 依据说明\n"
        "### 制度明确规定\n"
        "- 学生请假应坚持事前申请。\n\n"
        "## 来源文档\n"
        "- leave_policy.md | chunk-3\n"
    )

    monkeypatch.setattr(
        "service.service.query_campus_policy_func",
        lambda query: fake_markdown,
    )

    from service.service import _maybe_handle_policy_qa_fast_path

    user_input = _make_user_input("请假流程是什么？")
    trace_record = _make_trace_record()

    result = _maybe_handle_policy_qa_fast_path(user_input, trace_record)

    assert result is not None
    assert result.type == "ai"
    assert "## 简要结论" in result.content
    assert "## 来源文档" in result.content
    assert "leave_policy.md" in result.content
    assert trace_record.route == "campus_policy_fast_path"
    assert trace_record.tool_calls[0]["name"] == "query_campus_policy"


# ---------------------------------------------------------------------------
# 5. no-answer response is passed through without fabrication
# ---------------------------------------------------------------------------

def test_policy_qa_handler_no_answer(monkeypatch):
    no_answer_text = (
        "## 简要结论\n"
        "当前知识库中没有找到明确依据。\n\n"
        "## 注意事项\n"
        "建议以学校官方通知或辅导员答复为准。"
    )

    monkeypatch.setattr(
        "service.service.query_campus_policy_func",
        lambda query: no_answer_text,
    )

    from service.service import _maybe_handle_policy_qa_fast_path

    user_input = _make_user_input("请假去外太空需要什么材料？")
    trace_record = _make_trace_record()

    result = _maybe_handle_policy_qa_fast_path(user_input, trace_record)

    assert result is not None
    assert result.type == "ai"
    assert "没有找到明确依据" in result.content


# ---------------------------------------------------------------------------
# 6. tool exception → handler returns None → SkillExecutor records fallback
# ---------------------------------------------------------------------------

def test_policy_qa_handler_error_fallback(monkeypatch):
    monkeypatch.setattr(
        "service.service.query_campus_policy_func",
        lambda query: (_ for _ in ()).throw(RuntimeError("RAG tool failure")),
    )

    from service.service import _maybe_handle_policy_qa_fast_path

    handlers = {
        "_maybe_handle_policy_qa_fast_path": _maybe_handle_policy_qa_fast_path,
    }
    user_input = _make_user_input("请假流程是什么？")
    trace_record = _make_trace_record()

    result = try_skill_fast_path(user_input, trace_record, handlers)

    assert result is None
    assert trace_record.skill_name is None
    assert trace_record.skill_fallback_reason == "handler_error"


# ---------------------------------------------------------------------------
# 7. non-policy query does not trigger policy handler
# ---------------------------------------------------------------------------

def test_policy_qa_does_not_affect_non_policy_query():
    user_input = _make_user_input("我周一上午有什么课？")
    trace_record = _make_trace_record()

    from service.service import _maybe_handle_policy_qa_fast_path

    result = _maybe_handle_policy_qa_fast_path(user_input, trace_record)

    assert result is None
    assert trace_record.route != "campus_policy_fast_path"
