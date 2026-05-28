from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableLambda
from langgraph.store.memory import InMemoryStore

from agents import research_assistant as research_module
from agents.safeguard import SafeguardOutput, SafetyAssessment
from core.tracing import TraceRecord, bind_trace_record, generate_trace_id
from memory import user_memory as memory_module


class FailingStore:
    async def aget(self, namespace, key):
        raise RuntimeError("store unavailable")

    async def adelete(self, namespace, key):
        raise RuntimeError("store unavailable")


class SafeSafeguard:
    async def ainvoke(self, messages):
        return SafeguardOutput(safety_assessment=SafetyAssessment.SAFE)


class ViewMemoryFakeModel:
    def __init__(self):
        self.calls = []

    def bind_tools(self, available_tools):
        async def invoke(messages):
            self.calls.append(messages)
            if not any(isinstance(message, ToolMessage) for message in messages):
                return AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "view_user_memory",
                            "args": {},
                            "id": "view-memory-1",
                            "type": "tool_call",
                        }
                    ],
                )
            return AIMessage(content="我已展示当前保存的长期记忆。")

        return RunnableLambda(invoke)


def _runtime(store, user_id: str | None):
    configurable = {"user_id": user_id} if user_id else {}
    return SimpleNamespace(store=store, config={"configurable": configurable})


@pytest.mark.asyncio
async def test_view_user_memory_returns_only_current_users_memory():
    store = InMemoryStore()
    await store.aput(("user_memory", "user-a"), "profile", {"memory": "偏好简洁回答"})
    await store.aput(("user_memory", "user-b"), "profile", {"memory": "偏好详细解释"})

    result = await memory_module.view_user_memory_func(_runtime(store, "user-a"))

    assert "# 当前长期记忆" in result
    assert "偏好简洁回答" in result
    assert "偏好详细解释" not in result


@pytest.mark.asyncio
async def test_view_user_memory_returns_empty_message_when_no_memory_exists():
    result = await memory_module.view_user_memory_func(_runtime(InMemoryStore(), "user-a"))

    assert result == "当前没有保存的长期记忆。"


@pytest.mark.asyncio
async def test_delete_user_memory_deletes_current_user_only():
    store = InMemoryStore()
    await store.aput(("user_memory", "user-a"), "profile", {"memory": "偏好简洁回答"})
    await store.aput(("user_memory", "user-b"), "profile", {"memory": "偏好详细解释"})

    result = await memory_module.delete_user_memory_func(_runtime(store, "user-a"))
    after_delete = await memory_module.view_user_memory_func(_runtime(store, "user-a"))
    other_user = await memory_module.view_user_memory_func(_runtime(store, "user-b"))

    assert result == "已删除当前用户的长期记忆。"
    assert after_delete == "当前没有保存的长期记忆。"
    assert "偏好详细解释" in other_user


@pytest.mark.asyncio
async def test_management_tools_return_friendly_errors_without_identity_or_store():
    assert (
        await memory_module.view_user_memory_func(_runtime(InMemoryStore(), None))
        == "无法识别当前用户，暂时不能查看长期记忆。"
    )
    assert (
        await memory_module.delete_user_memory_func(_runtime(InMemoryStore(), None))
        == "无法识别当前用户，暂时不能删除长期记忆。"
    )
    assert (
        await memory_module.view_user_memory_func(_runtime(None, "user-a"))
        == "长期记忆存储当前不可用，请稍后再试。"
    )


@pytest.mark.asyncio
async def test_management_tools_hide_store_exceptions_and_record_trace():
    record = TraceRecord(trace_id=generate_trace_id(), route="invoke")

    with bind_trace_record(record):
        view_result = await memory_module.view_user_memory_func(_runtime(FailingStore(), "user-a"))
        delete_result = await memory_module.delete_user_memory_func(
            _runtime(FailingStore(), "user-a")
        )

    assert view_result == "长期记忆存储当前不可用，请稍后再试。"
    assert delete_result == "长期记忆存储当前不可用，请稍后再试。"
    assert "Traceback" not in view_result + delete_result
    assert record.memory_action == "delete"
    assert record.memory_action_success is False
    assert record.memory_error == "store unavailable"


def test_management_tools_are_registered_without_model_controlled_user_id():
    tool_names = {tool.name for tool in research_module.tools}
    view_schema = memory_module.view_user_memory.tool_call_schema.model_json_schema()
    delete_schema = memory_module.delete_user_memory_tool.tool_call_schema.model_json_schema()

    assert {"view_user_memory", "delete_user_memory"} <= tool_names
    assert view_schema.get("properties", {}) == {}
    assert delete_schema.get("properties", {}) == {}
    assert "user_id" not in str(view_schema) + str(delete_schema)


def test_memory_management_requests_are_not_persisted_as_new_memory():
    assert research_module.extract_memory_candidate("你记住了我什么？") is None
    assert research_module.extract_memory_candidate("不要再记住我的偏好") is None


@pytest.mark.asyncio
async def test_agent_view_tool_reads_existing_memory_without_overwriting_it(monkeypatch):
    store = InMemoryStore()
    await store.aput(("user_memory", "user-a"), "profile", {"memory": "偏好简洁回答"})
    model = ViewMemoryFakeModel()
    old_store = research_module.research_assistant.store
    research_module.research_assistant.store = store
    monkeypatch.setattr(research_module, "Safeguard", SafeSafeguard)
    monkeypatch.setattr(research_module, "get_model", lambda model_name: model)

    try:
        result = await research_module.research_assistant.ainvoke(
            {"messages": [HumanMessage(content="你记住了我什么？")]},
            config={"configurable": {"user_id": "user-a"}},
        )
    finally:
        research_module.research_assistant.store = old_store

    tool_message = next(
        message for message in result["messages"] if isinstance(message, ToolMessage)
    )
    saved = await store.aget(("user_memory", "user-a"), key="profile")
    assert "偏好简洁回答" in tool_message.content
    assert saved.value["memory"] == "偏好简洁回答"
