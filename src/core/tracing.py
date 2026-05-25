import json
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

DEFAULT_TRACE_PATH = Path("logs/agent_trace.jsonl")


def generate_trace_id() -> str:
    """Create an identifier for correlating request and child trace records."""
    return str(uuid4())


@dataclass
class TraceRecord:
    trace_id: str
    run_id: str | None = None
    thread_id: str | None = None
    user_id: str | None = None
    agent_id: str | None = None
    model_name: str | None = None
    query: str | None = None
    route: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    retrieved_docs: list[dict[str, Any]] = field(default_factory=list)
    total_latency_ms: float | None = None
    llm_time_ms: float | None = None
    tool_time_ms: float | None = None
    rag_load_time_ms: float | None = None
    retrieval_time_ms: float | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    fallback_triggered: bool = False
    error_message: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    event_type: str = "request"
    returned_doc_count: int | None = None
    source_list: list[str] = field(default_factory=list)
    chunk_id_list: list[str] = field(default_factory=list)
    is_empty_result: bool | None = None
    is_low_relevance: bool | None = None
    no_answer_triggered: bool | None = None
    context_docs_count: int | None = None
    context_chars: int | None = None
    estimated_context_tokens: int | None = None
    dropped_context_docs_count: int | None = None


class TraceSpan:
    """Small monotonic timer used by request, model, and retrieval instrumentation."""

    def __init__(self) -> None:
        self._started_at: float | None = None
        self.elapsed_ms: float | None = None

    def start(self) -> "TraceSpan":
        self._started_at = perf_counter()
        return self

    def stop(self) -> float:
        if self.elapsed_ms is not None:
            return self.elapsed_ms
        if self._started_at is None:
            self.start()
        self.elapsed_ms = (perf_counter() - self._started_at) * 1000  # type: ignore[operator]
        return self.elapsed_ms

    def __enter__(self) -> "TraceSpan":
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()


_current_trace_record: ContextVar[TraceRecord | None] = ContextVar(
    "current_trace_record",
    default=None,
)


@contextmanager
def bind_trace_record(record: TraceRecord) -> Iterator[TraceRecord]:
    """Make a request trace available to nested agent/tool calls."""
    token = _current_trace_record.set(record)
    try:
        yield record
    finally:
        _current_trace_record.reset(token)


def current_trace_record() -> TraceRecord | None:
    return _current_trace_record.get()


def write_trace_jsonl(record: TraceRecord, path: str | Path = DEFAULT_TRACE_PATH) -> None:
    """Append one trace record as UTF-8 JSON Lines."""
    trace_path = Path(path)
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    with trace_path.open("a", encoding="utf-8") as trace_file:
        trace_file.write(json.dumps(asdict(record), ensure_ascii=False, default=str) + "\n")


def safe_extract_token_usage(message: Any) -> dict[str, int | None]:
    """Read provider token metadata without requiring it to be present."""
    usage = getattr(message, "usage_metadata", None) or {}
    response_metadata = getattr(message, "response_metadata", None) or {}
    token_usage = (
        response_metadata.get("token_usage", {}) if isinstance(response_metadata, dict) else {}
    )

    prompt_tokens = usage.get("input_tokens", token_usage.get("prompt_tokens"))
    completion_tokens = usage.get("output_tokens", token_usage.get("completion_tokens"))
    total_tokens = usage.get("total_tokens", token_usage.get("total_tokens"))

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }


def add_token_usage(record: TraceRecord, message: Any, accumulate: bool = True) -> None:
    """Accumulate available token counts into a request trace."""
    usage = safe_extract_token_usage(message)
    for key, value in usage.items():
        if value is not None:
            current = getattr(record, key)
            if accumulate:
                setattr(record, key, (current or 0) + value)
            elif current is None:
                setattr(record, key, value)
