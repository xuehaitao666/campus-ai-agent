import json
from unittest.mock import Mock, patch

import pytest
from httpx import Request

from schema import ChatMessage


def _stream_response(events: list[str]) -> Mock:
    response = Mock()
    response.status_code = 200
    response.request = Request("POST", "http://test/test-agent/stream")
    response.iter_lines.return_value = events
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=None)
    return response


@pytest.mark.xfail(
    reason="Client currently treats ignored SSE comment/non-data lines as stream termination.",
    strict=True,
)
def test_stream_ignores_non_data_lines_and_stops_at_repeated_done(agent_client):
    message = {
        "type": "message",
        "content": {"type": "ai", "content": "最终回答"},
    }
    events = [
        "",
        ": keep-alive",
        "event: message",
        f"data: {json.dumps({'type': 'token', 'content': '部分'})}",
        f"data: {json.dumps(message, ensure_ascii=False)}",
        "data: [DONE]",
        "data: [DONE]",
    ]

    with patch("httpx.stream", return_value=_stream_response(events)):
        responses = list(agent_client.stream("测试流式事件"))

    assert responses[0] == "部分"
    assert responses[1] == ChatMessage(type="ai", content="最终回答")
    assert len(responses) == 2


def test_stream_malformed_json_raises_stable_parse_error(agent_client):
    with patch("httpx.stream", return_value=_stream_response(["data: {bad json"])):
        with pytest.raises(Exception, match="Error JSON parsing message from server"):
            list(agent_client.stream("损坏事件"))

    # TODO: Prefer AgentClientError if the client error contract is tightened later.


def test_stream_error_event_has_current_stable_ai_error_shape(agent_client):
    event = f"data: {json.dumps({'type': 'error', 'content': 'service unavailable'})}"

    with patch("httpx.stream", return_value=_stream_response([event, "data: [DONE]"])):
        responses = list(agent_client.stream("触发错误事件"))

    assert responses == [ChatMessage(type="ai", content="Error: service unavailable")]


def test_stream_message_event_preserves_custom_data(agent_client):
    event = {
        "type": "message",
        "content": {
            "type": "ai",
            "content": "带来源的回答",
            "custom_data": {
                "source_citations": [
                    {"source": "exam_policy.md", "chunk_id": "exam_policy.md::chunk-0001"}
                ]
            },
        },
    }

    with patch(
        "httpx.stream",
        return_value=_stream_response(
            [f"data: {json.dumps(event, ensure_ascii=False)}", "data: [DONE]"]
        ),
    ):
        responses = list(agent_client.stream("考试作弊有什么后果？"))

    assert responses[0].custom_data["source_citations"][0]["source"] == "exam_policy.md"
