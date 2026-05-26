import json

from langchain_core.messages import AIMessage

from core.tracing import current_trace_record


def test_stream_message_event_keeps_sse_shape_and_includes_custom_data(test_client, mock_agent):
    async def mock_astream(**kwargs):
        record = current_trace_record()
        record.retrieved_docs = [
            {"source": "exam_policy.md", "chunk_id": "exam_policy.md::chunk-0001"}
        ]
        record.tool_calls = [{"name": "Database_Search", "args": {"query": "考试作弊"}}]
        record.retrieval_time_ms = 4.2
        yield (
            "updates",
            {
                "model": {
                    "messages": [
                        AIMessage(
                            content="流式知识库回答",
                            additional_kwargs={"custom_data": {"ui_hint": "citation-ready"}},
                        )
                    ]
                }
            },
        )

    mock_agent.astream = mock_astream

    with test_client.stream(
        "POST",
        "/stream",
        json={"message": "考试作弊有什么后果？", "stream_tokens": False},
    ) as response:
        lines = [line for line in response.iter_lines() if line]

    event = json.loads(lines[0].removeprefix("data: "))
    assert response.status_code == 200
    assert event["type"] == "message"
    assert event["content"]["content"] == "流式知识库回答"
    assert event["content"]["custom_data"]["ui_hint"] == "citation-ready"
    assert event["content"]["custom_data"]["retrieved_docs"][0]["source"] == "exam_policy.md"
    assert event["content"]["custom_data"]["metrics"]["retrieval_time_ms"] == 4.2
    assert lines[-1] == "data: [DONE]"
