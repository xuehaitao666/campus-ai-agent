import json

from langchain_core.documents import Document
from langchain_core.messages import AIMessage

from agents import tools as campus_tools
from core.tracing import (
    TraceRecord,
    bind_trace_record,
    generate_trace_id,
    safe_extract_token_usage,
    write_trace_jsonl,
)
from service import service as service_module


class FakeRetriever:
    def invoke(self, query: str):
        return [
            Document(
                page_content="学生请假应提交申请材料。",
                metadata={"source": "leave_policy.md", "chunk_id": "leave-1"},
            )
        ]


def _read_records(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _capture_service_trace(monkeypatch, trace_path):
    monkeypatch.setattr(
        service_module,
        "write_trace_jsonl",
        lambda record: write_trace_jsonl(record, trace_path),
    )


def test_trace_id_and_jsonl_record_allow_missing_token_usage(tmp_path):
    trace_path = tmp_path / "agent_trace.jsonl"
    trace_id = generate_trace_id()
    record = TraceRecord(trace_id=trace_id, query="请假流程是什么？", route="invoke")

    write_trace_jsonl(record, trace_path)

    stored_record = _read_records(trace_path)[0]
    assert stored_record["trace_id"] == trace_id
    assert stored_record["prompt_tokens"] is None
    assert stored_record["completion_tokens"] is None
    assert stored_record["total_tokens"] is None
    assert safe_extract_token_usage(AIMessage(content="没有 token metadata")) == {
        "prompt_tokens": None,
        "completion_tokens": None,
        "total_tokens": None,
    }


def test_invoke_writes_request_trace_with_latency_and_metadata(
    test_client,
    mock_agent,
    monkeypatch,
    tmp_path,
):
    trace_path = tmp_path / "invoke_trace.jsonl"
    _capture_service_trace(monkeypatch, trace_path)
    mock_agent.ainvoke.return_value = [
        ("values", {"messages": [AIMessage(content="已完成校园问答。")]})
    ]

    response = test_client.post(
        "/invoke",
        json={
            "message": "请假流程是什么？",
            "thread_id": "trace-thread",
            "user_id": "trace-user",
        },
    )

    assert response.status_code == 200
    record = _read_records(trace_path)[0]
    assert record["trace_id"]
    assert record["run_id"]
    assert record["thread_id"] == "trace-thread"
    assert record["user_id"] == "trace-user"
    assert record["agent_id"] == "research-assistant"
    assert record["query"] == "请假流程是什么？"
    assert record["route"] == "invoke"
    assert record["total_latency_ms"] >= 0
    assert record["error_message"] is None
    assert record["prompt_tokens"] is None


def test_invoke_error_writes_trace_error_message(test_client, mock_agent, monkeypatch, tmp_path):
    trace_path = tmp_path / "invoke_error_trace.jsonl"
    _capture_service_trace(monkeypatch, trace_path)
    mock_agent.ainvoke.side_effect = RuntimeError("fake agent failure")

    response = test_client.post(
        "/invoke",
        json={"message": "触发失败请求", "thread_id": "error-thread"},
    )

    assert response.status_code == 500
    record = _read_records(trace_path)[0]
    assert record["thread_id"] == "error-thread"
    assert record["total_latency_ms"] >= 0
    assert "fake agent failure" in record["error_message"]


def test_stream_writes_trace_without_changing_sse_protocol(
    test_client,
    mock_agent,
    monkeypatch,
    tmp_path,
):
    trace_path = tmp_path / "stream_trace.jsonl"
    _capture_service_trace(monkeypatch, trace_path)

    async def mock_astream(**kwargs):
        yield ("updates", {"model": {"messages": [AIMessage(content="流式完成。")]}})

    mock_agent.astream = mock_astream

    with test_client.stream(
        "POST",
        "/stream",
        json={"message": "流式问题", "thread_id": "stream-thread", "stream_tokens": False},
    ) as response:
        lines = list(response.iter_lines())

    assert response.status_code == 200
    assert [line for line in lines if line][-1] == "data: [DONE]"
    record = _read_records(trace_path)[0]
    assert record["route"] == "stream"
    assert record["thread_id"] == "stream-thread"
    assert record["total_latency_ms"] >= 0


def test_rag_tool_writes_retrieval_event_in_request_context(monkeypatch, tmp_path):
    trace_path = tmp_path / "rag_trace.jsonl"
    request_record = TraceRecord(trace_id=generate_trace_id(), route="invoke", query="请假材料")
    monkeypatch.setattr(campus_tools, "load_chroma_db", lambda: FakeRetriever())
    monkeypatch.setattr(
        campus_tools,
        "write_trace_jsonl",
        lambda record: write_trace_jsonl(record, trace_path),
    )

    with bind_trace_record(request_record):
        result = campus_tools.database_search_func("请假材料")

    record = _read_records(trace_path)[0]
    assert "学生请假应提交申请材料" in result
    assert record["event_type"] == "rag_retrieval"
    assert record["route"] == "Database_Search"
    assert record["returned_doc_count"] == 1
    assert record["source_list"] == ["leave_policy.md"]
    assert record["chunk_id_list"] == ["leave-1"]
    assert record["retrieval_time_ms"] >= 0
    assert record["is_empty_result"] is False
    assert request_record.retrieved_docs[0]["source"] == "leave_policy.md"
