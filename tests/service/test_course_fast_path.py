import json

from langchain_core.messages import AIMessage

from core.router import parse_course_query
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


def test_parse_course_query_extracts_supported_filters():
    assert parse_course_query("星期一上午的数据结构在哪里上？") == {
        "day": "周一",
        "time_period": "上午",
        "course_name": "数据结构",
    }
    assert parse_course_query("我想查询课表") == {
        "day": None,
        "time_period": None,
        "course_name": None,
    }


def test_invoke_course_day_and_time_uses_fast_path_without_agent(
    test_client,
    mock_agent,
    monkeypatch,
    tmp_path,
):
    trace_path = tmp_path / "course_day_trace.jsonl"
    _capture_service_trace(monkeypatch, trace_path)

    response = test_client.post("/invoke", json={"message": "我周一上午有什么课？"})

    assert response.status_code == 200
    output = ChatMessage.model_validate(response.json())
    assert output.type == "ai"
    assert "数据结构与算法" in output.content
    mock_agent.ainvoke.assert_not_awaited()

    record = _read_record(trace_path)
    assert record["route"] == "course_schedule_fast_path"
    assert record["tool_calls"][0]["name"] == "get_course_schedule"
    assert record["tool_calls"][0]["args"] == {
        "day": "周一",
        "time_period": "上午",
        "course_name": None,
    }
    assert record["total_latency_ms"] >= 0
    assert record["tool_time_ms"] >= 0
    assert record["llm_time_ms"] == 0
    assert record["prompt_tokens"] == 0
    assert record["completion_tokens"] == 0
    assert record["total_tokens"] == 0
    assert record["error_message"] is None


def test_invoke_course_name_uses_fast_path_without_agent(test_client, mock_agent):
    response = test_client.post("/invoke", json={"message": "数据结构课在哪里上？"})

    assert response.status_code == 200
    output = ChatMessage.model_validate(response.json())
    assert "数据结构与算法" in output.content
    assert "软件楼 A302" in output.content
    mock_agent.ainvoke.assert_not_awaited()


def test_invoke_weekday_alias_uses_fast_path_without_agent(test_client, mock_agent):
    response = test_client.post("/invoke", json={"message": "星期一有什么课？"})

    assert response.status_code == 200
    output = ChatMessage.model_validate(response.json())
    assert "数据结构与算法" in output.content
    mock_agent.ainvoke.assert_not_awaited()


def test_stream_course_query_emits_message_and_done_without_agent(
    test_client,
    mock_agent,
    monkeypatch,
    tmp_path,
):
    trace_path = tmp_path / "stream_course_trace.jsonl"
    _capture_service_trace(monkeypatch, trace_path)

    with test_client.stream(
        "POST",
        "/stream",
        json={"message": "我周一上午有什么课？", "stream_tokens": True},
    ) as response:
        lines = [line for line in response.iter_lines() if line]

    assert response.status_code == 200
    assert lines[-1] == "data: [DONE]"
    messages = [json.loads(line.removeprefix("data: ")) for line in lines[:-1]]
    assert len(messages) == 1
    assert messages[0]["type"] == "message"
    assert messages[0]["content"]["type"] == "ai"
    assert "数据结构与算法" in messages[0]["content"]["content"]
    mock_agent.astream.assert_not_called()

    record = _read_record(trace_path)
    assert record["route"] == "course_schedule_fast_path"
    assert record["tool_calls"][0]["name"] == "get_course_schedule"


def test_non_course_question_falls_back_to_agent(test_client, mock_agent, monkeypatch, tmp_path):
    trace_path = tmp_path / "fallback_trace.jsonl"
    _capture_service_trace(monkeypatch, trace_path)
    mock_agent.ainvoke.return_value = [
        ("values", {"messages": [AIMessage(content="LangGraph agent response")]})
    ]

    response = test_client.post("/invoke", json={"message": "什么是 LangGraph？"})

    assert response.status_code == 200
    assert response.json()["content"] == "LangGraph agent response"
    mock_agent.ainvoke.assert_awaited_once()
    assert _read_record(trace_path)["route"] == "invoke"


def test_unparsed_course_intent_falls_back_to_agent(test_client, mock_agent, monkeypatch, tmp_path):
    trace_path = tmp_path / "unparsed_course_trace.jsonl"
    _capture_service_trace(monkeypatch, trace_path)
    mock_agent.ainvoke.return_value = [
        ("values", {"messages": [AIMessage(content="请补充课程查询条件")]})
    ]

    response = test_client.post("/invoke", json={"message": "我想查询课表"})

    assert response.status_code == 200
    assert response.json()["content"] == "请补充课程查询条件"
    mock_agent.ainvoke.assert_awaited_once()
    assert _read_record(trace_path)["route"] == "invoke"


def test_relative_date_course_query_falls_back_until_weekday_can_be_resolved(
    test_client,
    mock_agent,
):
    mock_agent.ainvoke.return_value = [
        ("values", {"messages": [AIMessage(content="由 Agent 处理相对日期课程查询")]})
    ]

    response = test_client.post("/invoke", json={"message": "我明天下午有什么课？"})

    assert response.status_code == 200
    assert response.json()["content"] == "由 Agent 处理相对日期课程查询"
    mock_agent.ainvoke.assert_awaited_once()
