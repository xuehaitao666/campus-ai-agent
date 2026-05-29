"""Tests for SkillExecutor — fast-path dispatch via SkillRegistry."""

from collections.abc import Callable
from unittest.mock import Mock

import pytest

from core.router import RouteIntent, route_query
from core.tracing import TraceRecord, generate_trace_id
from schema import ChatMessage, UserInput
from skills.definitions import BUILTIN_SKILLS
from skills.executor import try_skill_fast_path
from skills.registry import default_registry


def _make_user_input(message: str) -> UserInput:
    return UserInput(message=message)


def _make_trace_record() -> TraceRecord:
    return TraceRecord(trace_id=generate_trace_id())


def _fake_course_handler(user_input: UserInput, trace_record: TraceRecord) -> ChatMessage | None:
    decision = route_query(user_input.message)
    if decision.intent != RouteIntent.COURSE:
        return None
    return ChatMessage(type="ai", content="[course fast path result]")


def _fake_event_handler(user_input: UserInput, trace_record: TraceRecord) -> ChatMessage | None:
    decision = route_query(user_input.message)
    if decision.intent != RouteIntent.EVENT:
        return None
    return ChatMessage(type="ai", content="[event fast path result]")


def _handler_that_returns_none(
    _user_input: UserInput, _trace_record: TraceRecord
) -> ChatMessage | None:
    return None


# ---------------------------------------------------------------------------
# 1. course fast path
# ---------------------------------------------------------------------------

def test_try_skill_fast_path_executes_course_handler():
    handlers = {
        "_maybe_handle_course_fast_path": _fake_course_handler,
        "_maybe_handle_event_fast_path": _fake_event_handler,
    }
    user_input = _make_user_input("我周一上午有什么课？")
    trace_record = _make_trace_record()

    result = try_skill_fast_path(user_input, trace_record, handlers)

    assert result is not None
    assert result.type == "ai"
    assert "course" in result.content


# ---------------------------------------------------------------------------
# 2. event fast path
# ---------------------------------------------------------------------------

def test_try_skill_fast_path_executes_event_handler():
    handlers = {
        "_maybe_handle_course_fast_path": _fake_course_handler,
        "_maybe_handle_event_fast_path": _fake_event_handler,
    }
    user_input = _make_user_input("这周有什么 AI 相关讲座？")
    trace_record = _make_trace_record()

    result = try_skill_fast_path(user_input, trace_record, handlers)

    assert result is not None
    assert result.type == "ai"
    assert "event" in result.content


# ---------------------------------------------------------------------------
# 3. unmatched query returns None
# ---------------------------------------------------------------------------

def test_try_skill_fast_path_returns_none_when_no_skill_matches():
    handlers = {
        "_maybe_handle_course_fast_path": _fake_course_handler,
        "_maybe_handle_event_fast_path": _fake_event_handler,
    }
    user_input = _make_user_input("什么是 LangGraph？")
    trace_record = _make_trace_record()

    result = try_skill_fast_path(user_input, trace_record, handlers)

    assert result is None


# ---------------------------------------------------------------------------
# 4. missing handler → skip + return None
# ---------------------------------------------------------------------------

def test_try_skill_fast_path_skips_missing_handler(caplog):
    # course handler is missing from the map — event still exists
    handlers: dict[str, Callable] = {
        "_maybe_handle_event_fast_path": _fake_event_handler,
    }
    user_input = _make_user_input("我周一上午有什么课？")
    trace_record = _make_trace_record()

    result = try_skill_fast_path(user_input, trace_record, handlers)

    # course intent matches but handler is missing → warning logged, fallback
    assert result is None
    assert "no handler is registered" in caplog.text


# ---------------------------------------------------------------------------
# 5. handler returns None → continue; no false positive
# ---------------------------------------------------------------------------

def test_try_skill_fast_path_uses_first_non_none_result():
    # course handler returns None, event handler returns real result
    handlers = {
        "_maybe_handle_course_fast_path": _handler_that_returns_none,
        "_maybe_handle_event_fast_path": _fake_event_handler,
    }
    user_input = _make_user_input("这周有什么 AI 相关讲座？")
    trace_record = _make_trace_record()

    result = try_skill_fast_path(user_input, trace_record, handlers)

    assert result is not None
    assert "event" in result.content


# ---------------------------------------------------------------------------
# 6. handler raises → caught, skipped, returns None
# ---------------------------------------------------------------------------

def test_try_skill_fast_path_handles_handler_exception_gracefully(caplog):
    def _exploding_handler(
        _user_input: UserInput, _trace_record: TraceRecord
    ) -> ChatMessage | None:
        raise RuntimeError("simulated handler crash")

    handlers = {
        "_maybe_handle_course_fast_path": _exploding_handler,
    }
    user_input = _make_user_input("我周一上午有什么课？")
    trace_record = _make_trace_record()

    result = try_skill_fast_path(user_input, trace_record, handlers)

    assert result is None
    assert "raised an exception" in caplog.text


# ---------------------------------------------------------------------------
# 7. returns None when all handlers return None
# ---------------------------------------------------------------------------

def test_try_skill_fast_path_returns_none_when_all_handlers_return_none():
    handlers = {
        "_maybe_handle_course_fast_path": _handler_that_returns_none,
        "_maybe_handle_event_fast_path": _handler_that_returns_none,
    }
    # Query matches course intent, but handler returns None
    user_input = _make_user_input("我想查询课表")
    trace_record = _make_trace_record()

    result = try_skill_fast_path(user_input, trace_record, handlers)

    assert result is None
