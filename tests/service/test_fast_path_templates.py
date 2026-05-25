import json

from core.tracing import write_trace_jsonl
from service import service as service_module


def _capture_service_trace(monkeypatch, trace_path):
    monkeypatch.setattr(
        service_module,
        "write_trace_jsonl",
        lambda record: write_trace_jsonl(record, trace_path),
    )


def _read_record(trace_path):
    return json.loads(trace_path.read_text(encoding="utf-8").splitlines()[0])


def test_course_fast_path_invoke_returns_templated_content_without_agent(
    test_client,
    mock_agent,
    monkeypatch,
    tmp_path,
):
    trace_path = tmp_path / "templated_course_trace.jsonl"
    _capture_service_trace(monkeypatch, trace_path)

    response = test_client.post("/invoke", json={"message": "我周一上午有什么课？"})

    assert response.status_code == 200
    assert "## 课程查询结果" in response.json()["content"]
    assert "### 查询条件" in response.json()["content"]
    mock_agent.ainvoke.assert_not_awaited()
    record = _read_record(trace_path)
    assert record["route"] == "course_schedule_fast_path"
    assert record["total_tokens"] == 0


def test_event_fast_path_invoke_returns_templated_content_without_agent(
    test_client,
    mock_agent,
    monkeypatch,
    tmp_path,
):
    trace_path = tmp_path / "templated_event_trace.jsonl"
    _capture_service_trace(monkeypatch, trace_path)

    response = test_client.post("/invoke", json={"message": "这周有什么 AI 相关讲座？"})

    assert response.status_code == 200
    assert "## 校园活动查询结果" in response.json()["content"]
    assert "### 查询条件" in response.json()["content"]
    mock_agent.ainvoke.assert_not_awaited()
    record = _read_record(trace_path)
    assert record["route"] == "campus_event_fast_path"
    assert record["total_tokens"] == 0


def test_stream_fast_paths_emit_templated_message_content_without_agent(test_client, mock_agent):
    for query, title in [
        ("我周一上午有什么课？", "## 课程查询结果"),
        ("这周有什么 AI 相关讲座？", "## 校园活动查询结果"),
    ]:
        with test_client.stream("POST", "/stream", json={"message": query}) as response:
            lines = [line for line in response.iter_lines() if line]

        assert response.status_code == 200
        assert lines[-1] == "data: [DONE]"
        event = json.loads(lines[0].removeprefix("data: "))
        assert title in event["content"]["content"]

    mock_agent.astream.assert_not_called()
