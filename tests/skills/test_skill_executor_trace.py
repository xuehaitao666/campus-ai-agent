"""Tests for SkillExecutor trace fields — skill_name and skill_fallback_reason."""

from collections.abc import Callable

import pytest

from core.router import RouteIntent, route_query
from core.tracing import TraceRecord, generate_trace_id
from schema import ChatMessage, UserInput
from skills.executor import try_skill_fast_path


def _make_user_input(message: str) -> UserInput:
    return UserInput(message=message)


def _make_trace_record() -> TraceRecord:
    return TraceRecord(trace_id=generate_trace_id())


def _fake_course_handler(
    _user_input: UserInput, _trace_record: TraceRecord
) -> ChatMessage | None:
    return ChatMessage(type="ai", content="[course fast path result]")


def _fake_event_handler(
    _user_input: UserInput, _trace_record: TraceRecord
) -> ChatMessage | None:
    return ChatMessage(type="ai", content="[event fast path result]")


def _handler_that_returns_none(
    _user_input: UserInput, _trace_record: TraceRecord
) -> ChatMessage | None:
    return None


# -- helpers ----------------------------------------------------------------

def _full_handlers() -> dict[str, Callable]:
    return {
        "_maybe_handle_course_fast_path": _fake_course_handler,
        "_maybe_handle_event_fast_path": _fake_event_handler,
    }


# ---------------------------------------------------------------------------
# 1. course skill success → skill_name = "course_query"
# ---------------------------------------------------------------------------

def test_skill_name_written_on_course_success():
    trace_record = _make_trace_record()
    user_input = _make_user_input("我周一上午有什么课？")

    result = try_skill_fast_path(user_input, trace_record, _full_handlers())

    assert result is not None
    assert result.type == "ai"
    assert trace_record.skill_name == "course_query"
    assert trace_record.skill_fallback_reason is None


# ---------------------------------------------------------------------------
# 2. event skill success → skill_name = "event_query"
# ---------------------------------------------------------------------------

def test_skill_name_written_on_event_success():
    trace_record = _make_trace_record()
    user_input = _make_user_input("这周有什么 AI 相关讲座？")

    result = try_skill_fast_path(user_input, trace_record, _full_handlers())

    assert result is not None
    assert result.type == "ai"
    assert trace_record.skill_name == "event_query"
    assert trace_record.skill_fallback_reason is None


# ---------------------------------------------------------------------------
# 3. no intent match → fallback_reason = "no_intent_match"
# ---------------------------------------------------------------------------

def test_no_intent_match_sets_fallback_reason():
    trace_record = _make_trace_record()
    user_input = _make_user_input("什么是 LangGraph？")

    result = try_skill_fast_path(user_input, trace_record, _full_handlers())

    assert result is None
    assert trace_record.skill_name is None
    assert trace_record.skill_fallback_reason == "no_intent_match"


# ---------------------------------------------------------------------------
# 4. missing handler → fallback_reason = "handler_missing"
# ---------------------------------------------------------------------------

def test_missing_handler_sets_fallback_reason():
    trace_record = _make_trace_record()
    user_input = _make_user_input("我周一上午有什么课？")
    # Only event handler registered — course handler is missing
    handlers: dict[str, Callable] = {
        "_maybe_handle_event_fast_path": _fake_event_handler,
    }

    result = try_skill_fast_path(user_input, trace_record, handlers)

    assert result is None
    assert trace_record.skill_name is None
    assert trace_record.skill_fallback_reason == "handler_missing"


# ---------------------------------------------------------------------------
# 5. handler error → fallback_reason = "handler_error", error_message untouched
# ---------------------------------------------------------------------------

def test_handler_error_sets_fallback_reason_without_error_message():
    trace_record = _make_trace_record()
    # Ensure error_message starts as None
    assert trace_record.error_message is None

    user_input = _make_user_input("我周一上午有什么课？")

    def _exploding_handler(
        _user_input: UserInput, _trace_record: TraceRecord
    ) -> ChatMessage | None:
        raise RuntimeError("simulated handler crash")

    handlers = {"_maybe_handle_course_fast_path": _exploding_handler}

    result = try_skill_fast_path(user_input, trace_record, handlers)

    assert result is None
    assert trace_record.skill_name is None
    assert trace_record.skill_fallback_reason == "handler_error"
    assert trace_record.error_message is None


# ---------------------------------------------------------------------------
# 6. handler returns None → fallback_reason = "handler_returned_none"
# ---------------------------------------------------------------------------

def test_handler_returned_none_sets_fallback_reason():
    trace_record = _make_trace_record()
    user_input = _make_user_input("我周一上午有什么课？")
    handlers = {"_maybe_handle_course_fast_path": _handler_that_returns_none}

    result = try_skill_fast_path(user_input, trace_record, handlers)

    assert result is None
    assert trace_record.skill_name is None
    assert trace_record.skill_fallback_reason == "handler_returned_none"


# ---------------------------------------------------------------------------
# 7. executor does NOT modify trace_record.route
# ---------------------------------------------------------------------------

def test_route_field_is_not_modified_by_skill_executor():
    trace_record = _make_trace_record()
    trace_record.route = "invoke"

    user_input = _make_user_input("我周一上午有什么课？")
    result = try_skill_fast_path(user_input, trace_record, _full_handlers())

    assert result is not None
    assert trace_record.route == "invoke"


# ---------------------------------------------------------------------------
# 8. skill_name is None (not some other falsy value) when no match
# ---------------------------------------------------------------------------

def test_skill_name_is_none_when_not_matched():
    trace_record = _make_trace_record()
    user_input = _make_user_input("什么是 LangGraph？")

    try_skill_fast_path(user_input, trace_record, _full_handlers())

    assert trace_record.skill_name is None


# ---------------------------------------------------------------------------
# 9. skill_name and fallback_reason are mutually exclusive
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "query,expect_name",
    [
        ("我周一上午有什么课？", "course_query"),
        ("这周有什么 AI 相关讲座？", "event_query"),
    ],
)
def test_skill_name_and_fallback_reason_are_mutually_exclusive(query, expect_name):
    trace_record = _make_trace_record()
    user_input = _make_user_input(query)

    try_skill_fast_path(user_input, trace_record, _full_handlers())

    assert trace_record.skill_name == expect_name
    assert trace_record.skill_fallback_reason is None
