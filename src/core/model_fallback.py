from collections.abc import Callable
from typing import Any

from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableConfig

from core.settings import settings
from core.tracing import current_trace_record


def _model_name(model: Any) -> str | None:
    if model is None:
        return None
    return str(getattr(model, "value", model))


def _record_attempt(model: Any) -> None:
    record = current_trace_record()
    if record is None:
        return
    record.model_attempt_count += 1
    if record.primary_model is None:
        record.primary_model = _model_name(model)


def _record_primary_error(error: Exception) -> None:
    record = current_trace_record()
    if record is None:
        return
    record.model_error = str(error)
    record.model_error_type = type(error).__name__


async def ainvoke_with_model_fallback(
    state: Any,
    config: RunnableConfig,
    wrap_model: Callable[[Any], Any],
    model_factory: Callable[[Any], Any],
) -> AIMessage:
    """Invoke the primary model and make at most one configured fallback attempt."""
    primary_model = config["configurable"].get("model", settings.DEFAULT_MODEL)
    _record_attempt(primary_model)
    try:
        return await wrap_model(model_factory(primary_model)).ainvoke(state, config)
    except Exception as primary_error:
        _record_primary_error(primary_error)
        if not settings.ENABLE_MODEL_FALLBACK:
            raise

        fallback_model = settings.FALLBACK_MODEL
        if fallback_model is None:
            raise RuntimeError(
                "Model fallback is enabled but FALLBACK_MODEL is not configured."
            ) from primary_error
        if fallback_model == primary_model:
            raise RuntimeError(
                "FALLBACK_MODEL must differ from the primary model."
            ) from primary_error

        record = current_trace_record()
        if record is not None:
            record.fallback_triggered = True
            record.fallback_model = _model_name(fallback_model)
        _record_attempt(fallback_model)
        try:
            return await wrap_model(model_factory(fallback_model)).ainvoke(state, config)
        except Exception as fallback_error:
            if record is not None:
                record.model_error = (
                    f"Primary model failed: {primary_error}; "
                    f"fallback model failed: {fallback_error}"
                )
                record.model_error_type = type(fallback_error).__name__
            raise RuntimeError(
                "Primary and fallback model calls failed. Please try again later."
            ) from fallback_error
