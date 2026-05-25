import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolCall, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, MessagesState, StateGraph

from schema import ChatHistory, ChatMessage


def conversation_reply(state: MessagesState) -> MessagesState:
    user_messages = [
        message.content for message in state["messages"] if isinstance(message, HumanMessage)
    ]
    tool_call_id = f"history-call-{len(user_messages)}"
    latest_message = user_messages[-1]
    return {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    ToolCall(
                        name="history_lookup",
                        args={"message": latest_message},
                        id=tool_call_id,
                    )
                ],
            ),
            ToolMessage(
                content=f"Stored context for: {latest_message}",
                tool_call_id=tool_call_id,
            ),
            AIMessage(content=f"Known user messages: {' | '.join(user_messages)}"),
        ]
    }


@pytest.fixture
def history_agent():
    workflow = StateGraph(MessagesState)
    workflow.add_node("conversation_reply", conversation_reply)
    workflow.set_entry_point("conversation_reply")
    workflow.add_edge("conversation_reply", END)
    return workflow.compile(checkpointer=MemorySaver())


def test_same_thread_id_restores_prior_turn_messages(test_client, history_agent, monkeypatch):
    monkeypatch.setattr("service.service.get_agent", lambda agent_id: history_agent)
    thread_id = "same-thread"

    first_response = test_client.post(
        "/invoke",
        json={"message": "第一轮：我想了解请假流程。", "thread_id": thread_id},
    )
    second_response = test_client.post(
        "/invoke",
        json={"message": "第二轮：需要准备什么材料？", "thread_id": thread_id},
    )

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    first_message = ChatMessage.model_validate(first_response.json())
    second_message = ChatMessage.model_validate(second_response.json())

    assert "第一轮：我想了解请假流程。" in first_message.content
    assert "第一轮：我想了解请假流程。" in second_message.content
    assert "第二轮：需要准备什么材料？" in second_message.content


def test_different_thread_ids_keep_conversations_isolated(test_client, history_agent, monkeypatch):
    monkeypatch.setattr("service.service.get_agent", lambda agent_id: history_agent)

    response_a = test_client.post(
        "/invoke",
        json={"message": "线程 A 的问题", "thread_id": "thread-a"},
    )
    response_b = test_client.post(
        "/invoke",
        json={"message": "线程 B 的问题", "thread_id": "thread-b"},
    )

    assert response_a.status_code == 200
    assert response_b.status_code == 200
    answer_a = ChatMessage.model_validate(response_a.json())
    answer_b = ChatMessage.model_validate(response_b.json())
    assert "线程 A 的问题" in answer_a.content
    assert "线程 B 的问题" not in answer_a.content
    assert "线程 B 的问题" in answer_b.content
    assert "线程 A 的问题" not in answer_b.content

    history_a = ChatHistory.model_validate(
        test_client.post("/history", json={"thread_id": "thread-a"}).json()
    )
    history_b = ChatHistory.model_validate(
        test_client.post("/history", json={"thread_id": "thread-b"}).json()
    )

    assert all("线程 B 的问题" not in message.content for message in history_a.messages)
    assert all("线程 A 的问题" not in message.content for message in history_b.messages)


def test_history_returns_chat_history_with_human_ai_and_tool_messages(
    test_client,
    history_agent,
    monkeypatch,
):
    monkeypatch.setattr("service.service.get_agent", lambda agent_id: history_agent)
    thread_id = "history-types"

    invoke_response = test_client.post(
        "/invoke",
        json={"message": "查询历史中的工具消息", "thread_id": thread_id},
    )
    assert invoke_response.status_code == 200

    # /history currently reads DEFAULT_AGENT only. ChatHistoryInput can later gain
    # an agent_id field when histories must be selected per agent.
    history_response = test_client.post("/history", json={"thread_id": thread_id})

    assert history_response.status_code == 200
    history = ChatHistory.model_validate(history_response.json())
    assert isinstance(history, ChatHistory)
    assert all(isinstance(message, ChatMessage) for message in history.messages)
    assert [message.type for message in history.messages] == ["human", "ai", "tool", "ai"]

    human_message, tool_call_message, tool_message, final_message = history.messages
    assert human_message.content == "查询历史中的工具消息"
    assert tool_call_message.tool_calls[0]["name"] == "history_lookup"
    assert tool_message.content == "Stored context for: 查询历史中的工具消息"
    assert tool_message.tool_call_id == "history-call-1"
    assert final_message.content == "Known user messages: 查询历史中的工具消息"
