import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_TRACE_FILE = PROJECT_ROOT / "logs" / "agent_trace.jsonl"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "docs" / "optimization" / "benchmark_runs"
DEFAULT_LAST = 15


def is_request_trace(record: dict[str, Any]) -> bool:
    """Identify top-level request records, preferring explicit trace metadata."""
    event_type = record.get("event_type")
    if event_type is not None:
        return event_type == "request"

    trace_type = record.get("trace_type")
    if trace_type is not None:
        return trace_type == "request"

    if record.get("parent_trace_id"):
        return False

    return all(
        [
            record.get("query"),
            record.get("agent_id"),
            record.get("route"),
            record.get("total_latency_ms") is not None,
        ]
    )


def _read_valid_trace_records(trace_file: Path | str) -> tuple[list[dict[str, Any]], int]:
    path = Path(trace_file)
    if not path.exists():
        raise FileNotFoundError(f"Trace file not found: {path}")

    records: list[dict[str, Any]] = []
    skipped_count = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            skipped_count += 1
            continue
        if not isinstance(record, dict):
            skipped_count += 1
            continue
        records.append(record)

    return records, skipped_count


def load_trace_records(
    trace_file: Path | str, last: int = DEFAULT_LAST
) -> tuple[list[dict[str, Any]], int]:
    """Load the latest valid trace records and count malformed JSON lines."""
    if last < 1:
        raise ValueError("--last must be greater than 0")

    records, skipped_count = _read_valid_trace_records(trace_file)
    return records[-last:], skipped_count


def _request_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [record for record in records if is_request_trace(record)]


def select_trace_records(
    trace_file: Path | str,
    last: int = DEFAULT_LAST,
    request_only: bool = False,
    request_last: int | None = None,
) -> tuple[list[dict[str, Any]], int, str, int | None, int]:
    """Select records for one report and return selection metadata."""
    if last < 1:
        raise ValueError("--last must be greater than 0")
    if request_last is not None and request_last < 1:
        raise ValueError("--request-last must be greater than 0")

    records, skipped_count = _read_valid_trace_records(trace_file)

    if request_last is not None:
        selected_reversed: list[dict[str, Any]] = []
        skipped_child_event_count = 0
        for record in reversed(records):
            if is_request_trace(record):
                selected_reversed.append(record)
                if len(selected_reversed) == request_last:
                    break
            else:
                skipped_child_event_count += 1
        return (
            list(reversed(selected_reversed)),
            skipped_count,
            "request-last",
            request_last,
            skipped_child_event_count,
        )

    if request_only:
        selected = _request_records(records)[-last:]
        return (
            selected,
            skipped_count,
            "request-only",
            last,
            len(records) - len(_request_records(records)),
        )

    return records[-last:], skipped_count, "last", None, 0


def _average(records: list[dict[str, Any]], key: str) -> float | None:
    values = [
        value
        for record in records
        if isinstance((value := record.get(key)), (int, float)) and not isinstance(value, bool)
    ]
    return sum(values) / len(values) if values else None


def summarize_records(records: list[dict[str, Any]]) -> dict[str, int | float | None]:
    """Summarize request-level records while excluding retrieval child events."""
    requests = _request_records(records)
    return {
        "total_requests": len(requests),
        "average_total_latency_ms": _average(requests, "total_latency_ms"),
        "average_llm_time_ms": _average(requests, "llm_time_ms"),
        "average_tool_time_ms": _average(requests, "tool_time_ms"),
        "average_retrieval_time_ms": _average(requests, "retrieval_time_ms"),
        "average_prompt_tokens": _average(requests, "prompt_tokens"),
        "average_completion_tokens": _average(requests, "completion_tokens"),
        "average_total_tokens": _average(requests, "total_tokens"),
        "error_count": sum(bool(record.get("error_message")) for record in requests),
        "fallback_count": sum(record.get("fallback_triggered") is True for record in requests),
    }


def _value(value: Any) -> str:
    if value is None or value == "":
        return "-"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value).replace("|", r"\|").replace("\n", " ")


def _tool_calls(value: Any) -> str:
    if not value:
        return "-"
    tools = []
    for call in value:
        if isinstance(call, dict):
            tools.append(call.get("name") or str(call))
        else:
            tools.append(str(call))
    return _value(", ".join(tools))


def _retrieved_docs(value: Any) -> str:
    if not value:
        return "-"
    docs = []
    for document in value:
        if isinstance(document, dict):
            source = document.get("source") or "-"
            chunk_id = document.get("chunk_id")
            docs.append(f"{source} ({chunk_id})" if chunk_id else str(source))
        else:
            docs.append(str(document))
    return _value(", ".join(docs))


def _unique_values(records: list[dict[str, Any]], key: str) -> str:
    values = sorted({str(record[key]) for record in records if record.get(key)})
    return ", ".join(values) if values else "-"


def _git_commit_hash() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "-"
    return result.stdout.strip() or "-"


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def render_markdown(
    name: str,
    records: list[dict[str, Any]],
    trace_file: Path | str,
    skipped_count: int = 0,
    selection_mode: str = "last",
    requested_request_count: int | None = None,
    skipped_child_event_count: int = 0,
    created_at: datetime | None = None,
    git_commit_hash: str | None = None,
) -> str:
    """Render one comparable benchmark report from selected trace records."""
    created_at = created_at or datetime.now(UTC)
    requests = _request_records(records)
    summary = summarize_records(records)
    trace_path = Path(trace_file)
    commit_hash = git_commit_hash if git_commit_hash is not None else _git_commit_hash()
    child_event_count = len(records) - len(requests)

    lines = [
        f"# Benchmark Run: {name}",
        "",
        "## 1. Run Metadata",
        "",
        f"- created_at: {created_at.isoformat()}",
        f"- git commit hash: {commit_hash}",
        f"- trace file: {_display_path(trace_path)}",
        f"- selection_mode: {selection_mode}",
        f"- requested_request_count: {_value(requested_request_count)}",
        f"- actual_request_count: {len(requests)}",
        f"- sample size: {len(records)} valid trace records",
        f"- request sample size: {len(requests)}",
        f"- child event count: {child_event_count}",
        f"- skipped child event count: {skipped_child_event_count}",
        f"- skipped invalid JSON lines: {skipped_count}",
        f"- model list: {_unique_values(requests, 'model_name')}",
        f"- agent list: {_unique_values(requests, 'agent_id')}",
        "",
        "## 2. Summary",
        "",
    ]
    if requested_request_count is not None and len(requests) < requested_request_count:
        metadata_end = lines.index("## 2. Summary") - 1
        lines.insert(
            metadata_end,
            "- request selection note: "
            f"requested {requested_request_count} request-level traces, "
            f"only {len(requests)} available",
        )
    lines.extend(f"- {key}: {_value(value)}" for key, value in summary.items())
    lines.extend(
        [
            "",
            "## 3. Per-query Results",
            "",
            "| query | agent_id | model_name | route | tool_calls | retrieved_docs | total_latency_ms | llm_time_ms | tool_time_ms | retrieval_time_ms | prompt_tokens | completion_tokens | total_tokens | error_message |",
            "| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        ]
    )

    for record in requests:
        cells = [
            _value(record.get("query")),
            _value(record.get("agent_id")),
            _value(record.get("model_name")),
            _value(record.get("route")),
            _tool_calls(record.get("tool_calls")),
            _retrieved_docs(record.get("retrieved_docs")),
            _value(record.get("total_latency_ms")),
            _value(record.get("llm_time_ms")),
            _value(record.get("tool_time_ms")),
            _value(record.get("retrieval_time_ms")),
            _value(record.get("prompt_tokens")),
            _value(record.get("completion_tokens")),
            _value(record.get("total_tokens")),
            _value(record.get("error_message")),
        ]
        lines.append("| " + " | ".join(cells) + " |")

    if not requests:
        lines.append("| - | - | - | - | - | - | - | - | - | - | - | - | - | - |")

    lines.extend(
        [
            "",
            "## 4. Observations",
            "",
            "TODO",
            "",
            "## 5. Next Optimization Target",
            "",
            "TODO",
            "",
        ]
    )
    return "\n".join(lines)


def export_benchmark_run(
    name: str,
    last: int = DEFAULT_LAST,
    trace_file: Path | str = DEFAULT_TRACE_FILE,
    output_dir: Path | str = DEFAULT_OUTPUT_DIR,
    request_only: bool = False,
    request_last: int | None = None,
    created_at: datetime | None = None,
    git_commit_hash: str | None = None,
) -> Path:
    """Write one benchmark Markdown file from the latest trace window."""
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip()).strip("._")
    if not safe_name:
        raise ValueError("--name must contain at least one filename-safe character")

    (
        records,
        skipped_count,
        selection_mode,
        requested_request_count,
        skipped_child_event_count,
    ) = select_trace_records(
        trace_file,
        last=last,
        request_only=request_only,
        request_last=request_last,
    )
    created_at = created_at or datetime.now(UTC)
    output_path = Path(output_dir) / f"{created_at.date().isoformat()}_{safe_name}.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        render_markdown(
            name=safe_name,
            records=records,
            trace_file=trace_file,
            skipped_count=skipped_count,
            selection_mode=selection_mode,
            requested_request_count=requested_request_count,
            skipped_child_event_count=skipped_child_event_count,
            created_at=created_at,
            git_commit_hash=git_commit_hash,
        ),
        encoding="utf-8",
    )
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export Agent Trace records as a benchmark report."
    )
    parser.add_argument(
        "--name", required=True, help="Benchmark run name, for example phase1_baseline."
    )
    parser.add_argument(
        "--last", type=int, default=DEFAULT_LAST, help="Number of latest trace records."
    )
    parser.add_argument(
        "--request-only",
        action="store_true",
        help="Filter child events before taking the latest --last request records.",
    )
    parser.add_argument(
        "--request-last",
        type=int,
        help="Select the latest N request-level traces; takes precedence over --last.",
    )
    parser.add_argument("--trace-file", type=Path, default=DEFAULT_TRACE_FILE)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        output_path = export_benchmark_run(
            name=args.name,
            last=args.last,
            request_only=args.request_only,
            request_last=args.request_last,
            trace_file=args.trace_file,
            output_dir=args.output_dir,
        )
    except (FileNotFoundError, ValueError) as error:
        print(f"Benchmark export failed: {error}", file=sys.stderr)
        return 1

    print(f"Benchmark run exported to: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
