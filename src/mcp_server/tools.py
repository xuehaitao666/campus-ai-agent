from collections.abc import Callable
from time import perf_counter
from typing import Any

from agents.tools import (
    get_campus_events_func,
    get_course_schedule_func,
    query_campus_policy_func,
)


def _call_native_tool(
    tool_name: str,
    native_tool: Callable[..., str],
    **kwargs: Any,
) -> dict[str, Any]:
    """Run a read-only native tool and return an MCP-serializable envelope."""
    started_at = perf_counter()
    try:
        content = native_tool(**kwargs)
        return {
            "success": True,
            "content": content,
            "tool_name": tool_name,
            "latency_ms": (perf_counter() - started_at) * 1000,
            "transport": "mcp",
        }
    except Exception as error:
        return {
            "success": False,
            "error": str(error),
            "tool_name": tool_name,
            "latency_ms": (perf_counter() - started_at) * 1000,
            "transport": "mcp",
        }


def get_course_schedule(
    day: str | None = None,
    time_period: str | None = None,
    course_name: str | None = None,
) -> dict[str, Any]:
    """Query the local read-only campus course schedule."""
    return _call_native_tool(
        "get_course_schedule",
        get_course_schedule_func,
        day=day,
        time_period=time_period,
        course_name=course_name,
    )


def get_campus_events(
    keyword: str | None = None,
    date_range: str | None = None,
    event_type: str | None = None,
    target_audience: str | None = None,
) -> dict[str, Any]:
    """Query local read-only campus events."""
    return _call_native_tool(
        "get_campus_events",
        get_campus_events_func,
        keyword=keyword,
        date_range=date_range,
        event_type=event_type,
        target_audience=target_audience,
    )


def query_campus_policy(query: str) -> dict[str, Any]:
    """Query the local read-only campus policy knowledge base."""
    return _call_native_tool(
        "query_campus_policy",
        query_campus_policy_func,
        query=query,
    )
