import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableLambda
from langgraph.store.memory import InMemoryStore

from agents import research_assistant as research_module
from agents.safeguard import SafeguardOutput, SafetyAssessment


class FailingStore:
    async def aget(self, namespace, key):
        raise RuntimeError("read failed")

    async def aput(self, namespace, key, value):
        raise RuntimeError("write failed")


class SafeSafeguard:
    async def ainvoke(self, messages):
        return SafeguardOutput(safety_assessment=SafetyAssessment.SAFE)


class CapturingModel:
    def __init__(self):
        self.calls = []

    def bind_tools(self, available_tools):
        async def invoke(messages):
            self.calls.append(messages)
            return AIMessage(content="已回答")

        return RunnableLambda(invoke)


def test_extract_memory_candidate_only_accepts_explicit_non_sensitive_memory():
    assert (
        research_module.extract_memory_candidate("请记住我偏好简洁回答")
        == "请记住我偏好简洁回答"
    )
    assert research_module.extract_memory_candidate("请帮我查询课程表") is None
    assert research_module.extract_memory_candidate("记住我的密码是 secret-123") is None
    assert research_module.extract_memory_candidate("请记住我的手机号是 13800000000") is None


@pytest.mark.asyncio
async def test_memory_helpers_do_not_fail_without_store():
    assert await research_module.load_user_memory(None, "user-a") is None
    assert await research_module.save_user_memory(None, "user-a", "请记住我偏好简洁回答") is False


@pytest.mark.asyncio
async def test_in_memory_store_saves_and_loads_memory_for_same_user_only():
    store = InMemoryStore()

    saved = await research_module.save_user_memory(store, "user-a", "请记住我偏好简洁回答")

    assert saved is True
    assert await research_module.load_user_memory(store, "user-a") == "请记住我偏好简洁回答"
    assert await research_module.load_user_memory(store, "user-b") is None


@pytest.mark.asyncio
async def test_memory_store_contract_uses_user_profile_key_and_updates_latest_value():
    store = InMemoryStore()

    await research_module.save_user_memory(store, "user-a", "请记住我偏好简洁回答")
    first = await store.aget(("user_memory", "user-a"), key="profile")
    await research_module.save_user_memory(store, "user-a", "请记住我偏好表格回答")
    updated = await store.aget(("user_memory", "user-a"), key="profile")

    assert first.value["memory"] == "请记住我偏好简洁回答"
    assert updated.value["memory"] == "请记住我偏好表格回答"
    assert await store.aget(("user_memory", "user-b"), key="profile") is None


@pytest.mark.asyncio
async def test_sensitive_memory_candidate_is_not_written_to_store():
    store = InMemoryStore()
    candidate = research_module.extract_memory_candidate("请记住我的密码是 secret-123")

    saved = await research_module.save_user_memory(store, "user-a", candidate)

    assert candidate is None
    assert saved is False
    assert await store.aget(("user_memory", "user-a"), key="profile") is None


@pytest.mark.asyncio
async def test_store_errors_do_not_break_memory_helpers():
    store = FailingStore()

    assert await research_module.load_user_memory(store, "user-a") is None
    assert await research_module.save_user_memory(store, "user-a", "请记住我偏好简洁回答") is False


def test_build_messages_injects_memory_without_removing_latest_input():
    latest_input = HumanMessage(content="那帮我安排今天的学习。")

    messages = research_module.build_messages_with_memory(
        [latest_input], "请记住我偏好简洁回答"
    )

    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], SystemMessage)
    assert "用户长期记忆：请记住我偏好简洁回答" in messages[1].content
    assert messages[-1] is latest_input


@pytest.mark.asyncio
async def test_research_assistant_uses_injected_store_across_user_requests(monkeypatch):
    store = InMemoryStore()
    model = CapturingModel()
    old_store = research_module.research_assistant.store
    research_module.research_assistant.store = store
    monkeypatch.setattr(research_module, "Safeguard", SafeSafeguard)
    monkeypatch.setattr(research_module, "get_model", lambda model_name: model)

    try:
        await research_module.research_assistant.ainvoke(
            {"messages": [HumanMessage(content="请记住我偏好简洁回答")]},
            config={"configurable": {"user_id": "user-a"}},
        )
        await research_module.research_assistant.ainvoke(
            {"messages": [HumanMessage(content="今天帮我规划学习")]},
            config={"configurable": {"user_id": "user-a"}},
        )
    finally:
        research_module.research_assistant.store = old_store

    assert await research_module.load_user_memory(store, "user-a") == "请记住我偏好简洁回答"
    assert any(
        isinstance(message, SystemMessage)
        and "用户长期记忆：请记住我偏好简洁回答" in message.content
        for message in model.calls[-1]
    )
