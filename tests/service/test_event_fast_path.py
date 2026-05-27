import json
from datetime import date as real_date

import pytest
from langchain_core.messages import AIMessage

from agents import tools as tools_module
from core.router import parse_event_query
from core.tracing import write_trace_jsonl
from schema import ChatMessage
from service import service as service_module


def _capture_service_trace(monkeypatch, trace_path):
    monkeypatch.setattr(
        service_module,
        "write_trace_jsonl",
        lambda record: write_trace_jsonl(record, trace_path),
    )


def _read_record(trace_path):
    return json.loads(trace_path.read_text(encoding="utf-8").splitlines()[0])


def test_parse_event_query_extracts_supported_filters():
    assert parse_event_query("这周有什么人工智能相关讲座？") == {
        "keyword": "AI",
        "date_range": "这周",
        "event_type": "讲座",
        "target_audience": None,
    }
    assert parse_event_query("有什么活动推荐？") == {
        "keyword": None,
        "date_range": None,
        "event_type": None,
        "target_audience": None,
    }


@pytest.mark.parametrize(
    ("query", "field", "value"),
    [
        ("软件工程相关活动", "keyword", "软件工程"),
        ("比赛报名", "event_type", "比赛"),
        ("竞赛信息", "event_type", "比赛"),
        ("社团活动", "event_type", "社团"),
        ("招聘会", "event_type", "招聘"),
        ("宣讲会", "keyword", "宣讲"),
        ("本周有什么讲座", "date_range", "本周"),
        ("今天有什么活动", "date_range", "今天"),
        ("明天有什么活动", "date_range", "明天"),
    ],
)
def test_parse_event_query_maps_supported_event_expressions(query, field, value):
    assert parse_event_query(query)[field] == value


def test_invoke_ai_lecture_uses_fast_path_without_agent(
    test_client,
    mock_agent,
    monkeypatch,
    tmp_path,
):
    trace_path = tmp_path / "ai_lecture_trace.jsonl"
    _capture_service_trace(monkeypatch, trace_path)

    response = test_client.post("/invoke", json={"message": "这周有什么 AI 相关讲座？"})

    assert response.status_code == 200
    output = ChatMessage.model_validate(response.json())
    assert output.type == "ai"
    assert "AI Agent 技术分享会" in output.content
    mock_agent.ainvoke.assert_not_awaited()

    record = _read_record(trace_path)
    assert record["route"] == "campus_event_fast_path"
    assert record["tool_calls"][0]["name"] == "get_campus_events"
    assert record["tool_calls"][0]["args"] == {
        "keyword": "AI",
        "date_range": "这周",
        "event_type": "讲座",
        "target_audience": None,
    }
    assert record["total_latency_ms"] >= 0
    assert record["tool_time_ms"] >= 0
    assert record["llm_time_ms"] == 0
    assert record["prompt_tokens"] == 0
    assert record["completion_tokens"] == 0
    assert record["total_tokens"] == 0
    assert record["error_message"] is None


def test_invoke_recent_competition_registration_uses_fast_path_without_agent(
    test_client,
    mock_agent,
    monkeypatch,
):
    class FixedDate(real_date):
        @classmethod
        def today(cls):
            return cls(2026, 5, 26)

    monkeypatch.setattr(tools_module, "date", FixedDate)

    response = test_client.post("/invoke", json={"message": "最近有没有比赛可以报名？"})

    assert response.status_code == 200
    output = ChatMessage.model_validate(response.json())
    assert "大学生创新创业比赛宣讲" in output.content
    mock_agent.ainvoke.assert_not_awaited()


def test_stream_event_query_emits_message_and_done_without_agent(
    test_client,
    mock_agent,
    monkeypatch,
    tmp_path,
):
    trace_path = tmp_path / "stream_event_trace.jsonl"
    _capture_service_trace(monkeypatch, trace_path)

    with test_client.stream(
        "POST",
        "/stream",
        json={"message": "这周有什么 AI 相关讲座？", "stream_tokens": True},
    ) as response:
        lines = [line for line in response.iter_lines() if line]

    assert response.status_code == 200
    assert lines[-1] == "data: [DONE]"
    messages = [json.loads(line.removeprefix("data: ")) for line in lines[:-1]]
    assert len(messages) == 1
    assert messages[0]["type"] == "message"
    assert messages[0]["content"]["type"] == "ai"
    assert "AI Agent 技术分享会" in messages[0]["content"]["content"]
    mock_agent.astream.assert_not_called()

    record = _read_record(trace_path)
    assert record["route"] == "campus_event_fast_path"
    assert record["tool_calls"][0]["name"] == "get_campus_events"


def test_ai_explanation_question_falls_back_to_agent(test_client, mock_agent):
    mock_agent.ainvoke.return_value = [
        ("values", {"messages": [AIMessage(content="AI explanation from agent")]})
    ]

    response = test_client.post("/invoke", json={"message": "AI 是什么？"})

    assert response.status_code == 200
    assert response.json()["content"] == "AI explanation from agent"
    mock_agent.ainvoke.assert_awaited_once()


def test_unrelated_question_falls_back_to_agent(test_client, mock_agent):
    mock_agent.ainvoke.return_value = [
        ("values", {"messages": [AIMessage(content="LangGraph response from agent")]})
    ]

    response = test_client.post("/invoke", json={"message": "什么是 LangGraph？"})

    assert response.status_code == 200
    assert response.json()["content"] == "LangGraph response from agent"
    mock_agent.ainvoke.assert_awaited_once()


def test_unparsed_event_intent_falls_back_to_agent(test_client, mock_agent, monkeypatch, tmp_path):
    trace_path = tmp_path / "unparsed_event_trace.jsonl"
    _capture_service_trace(monkeypatch, trace_path)
    mock_agent.ainvoke.return_value = [
        ("values", {"messages": [AIMessage(content="请说明希望查询的活动条件")]})
    ]

    response = test_client.post("/invoke", json={"message": "有什么活动推荐？"})

    assert response.status_code == 200
    assert response.json()["content"] == "请说明希望查询的活动条件"
    mock_agent.ainvoke.assert_awaited_once()
    assert _read_record(trace_path)["route"] == "invoke"
