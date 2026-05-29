"""Skill fast-path executor — dispatches matching fast-path handlers via the registry."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING

from core.router import route_query
from skills.registry import default_registry

if TYPE_CHECKING:
    from core.tracing import TraceRecord
    from schema import ChatMessage, UserInput

logger = logging.getLogger(__name__)

Handler = Callable[["UserInput", "TraceRecord"], "ChatMessage | None"]


def try_skill_fast_path(
    user_input: UserInput,
    trace_record: TraceRecord,
    handlers: Mapping[str, Handler],
) -> ChatMessage | None:
    """Try every fast-path-enabled Skill in the registry and return the first match.

    For each registered Skill:
      1. Skip if ``fast_path_enabled`` is False.
      2. Call ``route_query`` to check whether the query intent matches the
         Skill's declared intent.  If not, skip early.
      3. Look up the handler function by ``fast_path_handler_name`` in the
         *handlers* dict.  If the handler is missing, log a warning and skip —
         the main request path will fall back to the Agent.
      4. Call the handler.  It returns ``ChatMessage`` on success or ``None``
         when the query does not satisfy all fast-path pre-conditions (e.g.
         no parsable parameters).

    Returns the first non-``None`` ``ChatMessage``, or ``None`` when no Skill
    can handle the query on the fast path.

    Skill-level trace fields are written to *trace_record*:
    * ``skill_name`` — set to the matched Skill's name on success.
    * ``skill_fallback_reason`` — set to a reason code when no Skill executes.
    """
    decision = route_query(user_input.message)

    fast_path_skills = [
        skill for skill in default_registry.list_skills() if skill.fast_path_enabled
    ]
    if not fast_path_skills:
        trace_record.skill_fallback_reason = "no_fast_path_skill"
        return None

    intent_matched = False
    for skill in fast_path_skills:
        if decision.intent != skill.intent:
            continue
        intent_matched = True

        handler = handlers.get(skill.fast_path_handler_name)
        if handler is None:
            trace_record.skill_fallback_reason = "handler_missing"
            logger.warning(
                "Skill %r has fast_path_handler_name=%r but no handler is "
                "registered.  Falling back to Agent.",
                skill.name,
                skill.fast_path_handler_name,
            )
            continue

        try:
            result = handler(user_input, trace_record)
        except Exception:
            trace_record.skill_fallback_reason = "handler_error"
            logger.exception(
                "Fast-path handler %r for skill %r raised an exception.  "
                "Falling back to Agent.",
                skill.fast_path_handler_name,
                skill.name,
            )
            continue

        if result is not None:
            trace_record.skill_name = skill.name
            trace_record.skill_fallback_reason = None
            return result

    if not intent_matched:
        trace_record.skill_fallback_reason = "no_intent_match"
    elif trace_record.skill_fallback_reason is None:
        trace_record.skill_fallback_reason = "handler_returned_none"

    return None
