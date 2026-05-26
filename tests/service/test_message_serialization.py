from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from core.tracing import current_trace_record
from schema import ChatMessage
from service.utils import langchain_to_chat_message


def test_langchain_message_conversion_preserves_custom_data():
    human = langchain_to_chat_message(
        HumanMessage(content="问题", additional_kwargs={"custom_data": {"channel": "human"}})
    )
    ai = langchain_to_chat_message(
        AIMessage(
            content="回答",
            additional_kwargs={"custom_data": {"retrieved_docs": [{"source": "exam_policy.md"}]}},
            response_metadata={"custom_data": {"metrics": {"total_tokens": 12}}},
        )
    )
    tool = langchain_to_chat_message(
        ToolMessage(
            content="工具结果",
            tool_call_id="call-1",
            additional_kwargs={"custom_data": {"tool_execution": {"tool_name": "Database_Search"}}},
        )
    )

    assert human.custom_data == {"channel": "human"}
    assert ai.custom_data["retrieved_docs"][0]["source"] == "exam_policy.md"
    assert ai.custom_data["metrics"]["total_tokens"] == 12
    assert tool.custom_data["tool_execution"]["tool_name"] == "Database_Search"
    assert tool.tool_call_id == "call-1"


def test_invoke_adds_trace_custom_data_without_breaking_message_fields(test_client, mock_agent):
    async def invoke_with_rag_trace(**kwargs):
        record = current_trace_record()
        record.retrieved_docs = [
            {
                "source": "leave_policy.md",
                "chunk_id": "leave_policy.md::chunk-0001",
                "section": "请假流程",
                "heading_path": "请假制度 > 请假流程",
                "policy_type": "leave",
                "retrieval_source": "vector+bm25",
                "hybrid_score": 0.03,
            }
        ]
        record.tool_calls = [{"name": "Database_Search", "args": {"query": "请假流程"}}]
        record.retrieval_time_ms = 15.2
        record.tool_time_ms = 15.2
        record.context_docs_count = 1
        record.context_chars = 200
        record.estimated_context_tokens = 100
        record.primary_model = "gpt-5-nano"
        record.fallback_triggered = False
        return [("values", {"messages": [AIMessage(content="请假流程回答")]})]

    mock_agent.ainvoke.side_effect = invoke_with_rag_trace

    response = test_client.post("/invoke", json={"message": "请假流程是什么？"})

    assert response.status_code == 200
    output = ChatMessage.model_validate(response.json())
    assert output.type == "ai"
    assert output.content == "请假流程回答"
    document = output.custom_data["retrieved_docs"][0]
    assert document["source"] == "leave_policy.md"
    assert document["chunk_id"] == "leave_policy.md::chunk-0001"
    assert document["section"] == "请假流程"
    assert output.custom_data["source_citations"][0] == {
        "source": "leave_policy.md",
        "chunk_id": "leave_policy.md::chunk-0001",
        "section": "请假流程",
    }
    assert output.custom_data["metrics"]["retrieval_time_ms"] == 15.2
    assert output.custom_data["tool_execution"][0]["tool_name"] == "Database_Search"
    assert output.custom_data["model_fallback"]["fallback_triggered"] is False
