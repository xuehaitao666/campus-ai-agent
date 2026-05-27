import json

import pytest

from agents.tools import get_campus_events_func, get_course_schedule_func
from mcp_server import server
from mcp_server import tools as mcp_tools


def test_mcp_course_tool_calls_native_tool_and_matches_content():
    expected = get_course_schedule_func(day="周一")

    result = mcp_tools.get_course_schedule(day="周一")

    assert result["success"] is True
    assert result["tool_name"] == "get_course_schedule"
    assert result["transport"] == "mcp"
    assert result["content"] == expected
    assert result["latency_ms"] >= 0
    json.dumps(result, ensure_ascii=False)


def test_mcp_event_tool_calls_native_tool_and_matches_content():
    expected = get_campus_events_func(keyword="Agent")

    result = mcp_tools.get_campus_events(keyword="Agent")

    assert result["success"] is True
    assert result["tool_name"] == "get_campus_events"
    assert result["content"] == expected
    assert result["latency_ms"] >= 0
    json.dumps(result, ensure_ascii=False)


def test_mcp_policy_tool_preserves_native_source_content(monkeypatch):
    native_content = (
        "已检索校园制度依据。\n\n### 来源\n- leave_policy.md | leave_policy.md::chunk-0001"
    )
    captured_queries = []

    def fake_policy_tool(query: str) -> str:
        captured_queries.append(query)
        return native_content

    monkeypatch.setattr(mcp_tools, "query_campus_policy_func", fake_policy_tool)

    result = mcp_tools.query_campus_policy("请假流程是什么？")

    assert captured_queries == ["请假流程是什么？"]
    assert result["success"] is True
    assert result["tool_name"] == "query_campus_policy"
    assert "leave_policy.md" in result["content"]
    assert "leave_policy.md::chunk-0001" in result["content"]


def test_mcp_planner_tool_calls_native_planner_and_is_json_serializable(monkeypatch):
    content = "# 校园事务办理建议\n\n## 事务类型\n- `exam_absence`"
    monkeypatch.setattr(mcp_tools, "plan_campus_affair_func", lambda **kwargs: content)

    result = mcp_tools.plan_campus_affair("我生病缺考怎么办？", urgency="紧急")

    assert result["success"] is True
    assert result["tool_name"] == "plan_campus_affair"
    assert result["content"] == content
    assert result["transport"] == "mcp"
    json.dumps(result, ensure_ascii=False)


@pytest.mark.parametrize(
    ("wrapper_name", "native_name", "kwargs"),
    [
        ("get_course_schedule", "get_course_schedule_func", {"day": "周二"}),
        ("get_campus_events", "get_campus_events_func", {"keyword": "比赛"}),
        ("query_campus_policy", "query_campus_policy_func", {"query": "宿舍晚归"}),
        ("plan_campus_affair", "plan_campus_affair_func", {"issue": "生病缺考"}),
    ],
)
def test_mcp_tools_return_safe_error_envelope(monkeypatch, wrapper_name, native_name, kwargs):
    def failing_tool(**call_kwargs):
        raise RuntimeError("native tool unavailable")

    monkeypatch.setattr(mcp_tools, native_name, failing_tool)

    result = getattr(mcp_tools, wrapper_name)(**kwargs)

    assert result["success"] is False
    assert result["tool_name"] == wrapper_name
    assert result["transport"] == "mcp"
    assert result["error"] == "native tool unavailable"
    assert result["latency_ms"] >= 0
    assert "Traceback" not in result["error"]
    json.dumps(result, ensure_ascii=False)


@pytest.mark.asyncio
async def test_mcp_server_registers_only_read_only_campus_tools():
    available_tools = await server.mcp.list_tools()

    assert {tool.name for tool in available_tools} == {
        "get_course_schedule",
        "get_campus_events",
        "query_campus_policy",
        "plan_campus_affair",
    }
