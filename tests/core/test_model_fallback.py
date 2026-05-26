import os
from unittest.mock import patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableLambda

from agents import rag_assistant as rag_module
from agents import research_assistant as research_module
from core import llm as llm_module
from core.settings import Settings
from core.settings import settings as runtime_settings
from core.tracing import TraceRecord, bind_trace_record, generate_trace_id
from schema.models import AnthropicModelName, OpenAIModelName


class FakeBoundModel:
    def __init__(self, content: str | None = None, error: Exception | None = None):
        self.content = content
        self.error = error
        self.calls = 0

    def bind_tools(self, tools):
        async def invoke(messages):
            self.calls += 1
            if self.error is not None:
                raise self.error
            return AIMessage(content=self.content or "")

        return RunnableLambda(invoke)


def _state():
    return {"messages": [HumanMessage(content="请回答")], "remaining_steps": 5}


def _config():
    return {"configurable": {"model": OpenAIModelName.GPT_5_NANO}}


@pytest.fixture(autouse=True)
def reset_fallback_settings(monkeypatch):
    monkeypatch.setattr(runtime_settings, "ENABLE_MODEL_FALLBACK", False)
    monkeypatch.setattr(runtime_settings, "FALLBACK_MODEL", None)


def test_settings_reads_model_reliability_configuration():
    with patch.dict(
        os.environ,
        {
            "OPENAI_API_KEY": "primary-key",
            "ANTHROPIC_API_KEY": "fallback-key",
            "MODEL_TIMEOUT_SECONDS": "12.5",
            "MODEL_MAX_RETRIES": "1",
            "MODEL_TEMPERATURE": "0.2",
            "ENABLE_MODEL_FALLBACK": "true",
            "FALLBACK_MODEL": "claude-haiku-4-5",
        },
        clear=True,
    ):
        settings = Settings(_env_file=None)

    assert settings.MODEL_TIMEOUT_SECONDS == 12.5
    assert settings.MODEL_MAX_RETRIES == 1
    assert settings.MODEL_TEMPERATURE == 0.2
    assert settings.ENABLE_MODEL_FALLBACK is True
    assert settings.FALLBACK_MODEL == AnthropicModelName.HAIKU_45


def test_settings_rejects_enabled_fallback_without_model():
    with patch.dict(
        os.environ,
        {"OPENAI_API_KEY": "primary-key", "ENABLE_MODEL_FALLBACK": "true"},
        clear=True,
    ):
        with pytest.raises(ValueError, match="FALLBACK_MODEL must be configured"):
            Settings(_env_file=None)


def test_get_model_passes_reliability_configuration_to_openai(monkeypatch):
    captured = {}

    def fake_chat_openai(**kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(llm_module.settings, "MODEL_TIMEOUT_SECONDS", 18.0)
    monkeypatch.setattr(llm_module.settings, "MODEL_MAX_RETRIES", 1)
    monkeypatch.setattr(llm_module.settings, "MODEL_TEMPERATURE", 0.25)
    monkeypatch.setattr(llm_module, "ChatOpenAI", fake_chat_openai)
    llm_module.get_model.cache_clear()

    llm_module.get_model(OpenAIModelName.GPT_5_NANO)

    assert captured["temperature"] == 0.25
    assert captured["timeout"] == 18.0
    assert captured["max_retries"] == 1
    assert captured["streaming"] is True
    llm_module.get_model.cache_clear()


@pytest.mark.asyncio
async def test_primary_success_does_not_trigger_fallback(monkeypatch):
    primary = FakeBoundModel(content="primary response")
    selected_models = []

    def fake_get_model(model_name):
        selected_models.append(model_name)
        return primary

    monkeypatch.setattr(research_module, "get_model", fake_get_model)
    record = TraceRecord(trace_id=generate_trace_id())

    with bind_trace_record(record):
        result = await research_module.acall_model(_state(), _config())

    assert result["messages"][0].content == "primary response"
    assert selected_models == [OpenAIModelName.GPT_5_NANO]
    assert record.primary_model == "gpt-5-nano"
    assert record.fallback_triggered is False
    assert record.model_attempt_count == 1
    assert record.model_error is None


@pytest.mark.asyncio
async def test_primary_failure_without_enabled_fallback_propagates_error(monkeypatch):
    primary = FakeBoundModel(error=TimeoutError("primary timed out"))
    selected_models = []

    def fake_get_model(model_name):
        selected_models.append(model_name)
        return primary

    monkeypatch.setattr(research_module, "get_model", fake_get_model)
    record = TraceRecord(trace_id=generate_trace_id())

    with bind_trace_record(record):
        with pytest.raises(TimeoutError, match="primary timed out"):
            await research_module.acall_model(_state(), _config())

    assert selected_models == [OpenAIModelName.GPT_5_NANO]
    assert record.fallback_triggered is False
    assert record.model_attempt_count == 1
    assert record.model_error == "primary timed out"
    assert record.model_error_type == "TimeoutError"


@pytest.mark.asyncio
@pytest.mark.parametrize("agent_module", [research_module, rag_module])
async def test_enabled_fallback_retries_once_for_supported_agents(monkeypatch, agent_module):
    primary = FakeBoundModel(error=TimeoutError("primary timed out"))
    fallback = FakeBoundModel(content="fallback response")
    selected_models = []
    monkeypatch.setattr(runtime_settings, "ENABLE_MODEL_FALLBACK", True)
    monkeypatch.setattr(runtime_settings, "FALLBACK_MODEL", AnthropicModelName.HAIKU_45)

    def fake_get_model(model_name):
        selected_models.append(model_name)
        return fallback if model_name == AnthropicModelName.HAIKU_45 else primary

    monkeypatch.setattr(agent_module, "get_model", fake_get_model)
    record = TraceRecord(trace_id=generate_trace_id())

    with bind_trace_record(record):
        result = await agent_module.acall_model(_state(), _config())

    assert result["messages"][0].content == "fallback response"
    assert selected_models == [OpenAIModelName.GPT_5_NANO, AnthropicModelName.HAIKU_45]
    assert record.fallback_triggered is True
    assert record.fallback_model == "claude-haiku-4-5"
    assert record.model_attempt_count == 2
    assert record.model_error == "primary timed out"
    assert record.llm_time_ms is not None


@pytest.mark.asyncio
async def test_same_fallback_model_does_not_loop(monkeypatch):
    primary = FakeBoundModel(error=RuntimeError("primary failed"))
    selected_models = []
    monkeypatch.setattr(research_module.settings, "ENABLE_MODEL_FALLBACK", True)
    monkeypatch.setattr(research_module.settings, "FALLBACK_MODEL", OpenAIModelName.GPT_5_NANO)

    def fake_get_model(model_name):
        selected_models.append(model_name)
        return primary

    monkeypatch.setattr(research_module, "get_model", fake_get_model)

    with pytest.raises(RuntimeError, match="must differ"):
        await research_module.acall_model(_state(), _config())

    assert selected_models == [OpenAIModelName.GPT_5_NANO]


@pytest.mark.asyncio
async def test_failed_fallback_returns_stable_error_and_trace(monkeypatch):
    primary = FakeBoundModel(error=TimeoutError("primary timed out"))
    fallback = FakeBoundModel(error=ConnectionError("fallback unavailable"))
    monkeypatch.setattr(research_module.settings, "ENABLE_MODEL_FALLBACK", True)
    monkeypatch.setattr(research_module.settings, "FALLBACK_MODEL", AnthropicModelName.HAIKU_45)
    monkeypatch.setattr(
        research_module,
        "get_model",
        lambda name: fallback if name == AnthropicModelName.HAIKU_45 else primary,
    )
    record = TraceRecord(trace_id=generate_trace_id())

    with bind_trace_record(record):
        with pytest.raises(RuntimeError, match="Primary and fallback model calls failed"):
            await research_module.acall_model(_state(), _config())

    assert record.fallback_triggered is True
    assert record.model_attempt_count == 2
    assert "primary timed out" in record.model_error
    assert "fallback unavailable" in record.model_error
    assert record.model_error_type == "ConnectionError"
