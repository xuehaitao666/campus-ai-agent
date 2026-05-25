import json
from datetime import UTC, datetime

import pytest

from scripts.export_benchmark_run import export_benchmark_run, load_trace_records


def _write_trace(path, *records):
    lines = [
        json.dumps(record, ensure_ascii=False) if isinstance(record, dict) else record
        for record in records
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_export_benchmark_run_generates_summary_and_skips_bad_json(tmp_path):
    trace_file = tmp_path / "agent_trace.jsonl"
    _write_trace(
        trace_file,
        {
            "event_type": "request",
            "query": "我周一有什么课",
            "agent_id": "research-assistant",
            "model_name": "fake-model",
            "route": "invoke",
            "tool_calls": [{"name": "get_course_schedule"}],
            "retrieved_docs": [],
            "total_latency_ms": 100.0,
            "llm_time_ms": 80.0,
            "tool_time_ms": 10.0,
            "retrieval_time_ms": None,
            "prompt_tokens": 40,
            "completion_tokens": 10,
            "total_tokens": 50,
            "fallback_triggered": False,
            "error_message": None,
        },
        "{not-json",
        {
            "event_type": "rag_retrieval",
            "query": "请假流程",
            "retrieval_time_ms": 999.0,
        },
        {
            "event_type": "request",
            "query": "挂科还能申请奖学金吗",
            "agent_id": "rag-assistant",
            "model_name": "fake-model",
            "route": "stream",
            "tool_calls": [{"name": "Database_Search"}],
            "retrieved_docs": [{"source": "scholarship_policy.md", "chunk_id": "chunk-1"}],
            "total_latency_ms": 300.0,
            "llm_time_ms": 120.0,
            "tool_time_ms": 30.0,
            "retrieval_time_ms": 20.0,
            "prompt_tokens": 60,
            "completion_tokens": 20,
            "total_tokens": 80,
            "fallback_triggered": True,
            "error_message": "fake failure",
        },
    )

    output_path = export_benchmark_run(
        name="phase1_baseline",
        last=15,
        trace_file=trace_file,
        output_dir=tmp_path / "benchmark_runs",
        created_at=datetime(2026, 5, 25, tzinfo=UTC),
        git_commit_hash="abc123",
    )

    report = output_path.read_text(encoding="utf-8")
    assert output_path.name == "2026-05-25_phase1_baseline.md"
    assert "# Benchmark Run: phase1_baseline" in report
    assert "- git commit hash: abc123" in report
    assert "- sample size: 3 valid trace records" in report
    assert "- request sample size: 2" in report
    assert "- child event count: 1" in report
    assert "- skipped invalid JSON lines: 1" in report
    assert "- total_requests: 2" in report
    assert "- average_total_latency_ms: 200.00" in report
    assert "- average_llm_time_ms: 100.00" in report
    assert "- average_tool_time_ms: 20.00" in report
    assert "- average_retrieval_time_ms: 20.00" in report
    assert "- average_prompt_tokens: 50.00" in report
    assert "- average_completion_tokens: 15.00" in report
    assert "- average_total_tokens: 65.00" in report
    assert "- error_count: 1" in report
    assert "- fallback_count: 1" in report
    assert "get_course_schedule" in report
    assert "scholarship_policy.md (chunk-1)" in report
    assert "## 4. Observations\n\nTODO" in report


def test_export_handles_null_fields_and_reads_latest_valid_records(tmp_path):
    trace_file = tmp_path / "agent_trace.jsonl"
    _write_trace(
        trace_file,
        {"event_type": "request", "query": "old", "total_latency_ms": 1},
        {"event_type": "request", "query": "recent", "model_name": None, "llm_time_ms": None},
    )

    records, skipped_count = load_trace_records(trace_file, last=1)
    output_path = export_benchmark_run(
        name="null_fields",
        last=1,
        trace_file=trace_file,
        output_dir=tmp_path / "reports",
        created_at=datetime(2026, 5, 25, tzinfo=UTC),
        git_commit_hash="abc123",
    )
    report = output_path.read_text(encoding="utf-8")

    assert skipped_count == 0
    assert [record["query"] for record in records] == ["recent"]
    assert "| old |" not in report
    assert "| recent | - | - | - | - | - | - | - | - | - | - | - | - | - |" in report
    assert "- average_llm_time_ms: -" in report


def test_export_missing_trace_file_raises_friendly_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="Trace file not found"):
        export_benchmark_run(
            name="missing_trace",
            trace_file=tmp_path / "missing.jsonl",
            output_dir=tmp_path / "reports",
        )
