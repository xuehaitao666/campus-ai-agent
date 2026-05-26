import json

from schema import ChatMessage


def test_chat_message_without_custom_data_remains_compatible():
    message = ChatMessage(type="ai", content="普通回答")

    assert message.custom_data == {}
    assert message.model_dump()["custom_data"] == {}


def test_chat_message_serializes_structured_custom_data():
    message = ChatMessage(
        type="ai",
        content="基于知识库回答。",
        custom_data={
            "retrieved_docs": [
                {"source": "leave_policy.md", "chunk_id": "leave_policy.md::chunk-0001"}
            ],
            "metrics": {"retrieval_time_ms": 12.5},
        },
    )

    serialized = json.loads(message.model_dump_json())

    assert serialized["content"] == "基于知识库回答。"
    assert serialized["custom_data"]["retrieved_docs"][0]["source"] == "leave_policy.md"
    assert serialized["custom_data"]["metrics"]["retrieval_time_ms"] == 12.5
