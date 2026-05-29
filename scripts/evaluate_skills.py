#!/usr/bin/env python3
"""Lightweight Skill Evaluation Benchmark.

Evaluates Router intent classification and SkillRegistry matching without
calling real LLMs, RAG, or FastAPI endpoints.  Produces JSON and Markdown
reports suitable for CI gating and historical comparison.

Usage::

    uv run python scripts/evaluate_skills.py
    uv run python scripts/evaluate_skills.py --fail-under-route-accuracy 0.8
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

DEFAULT_CASES_PATH = PROJECT_ROOT / "data" / "evaluation" / "skill_eval_cases.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "docs" / "optimization" / "benchmark_runs"


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------


@dataclass
class SkillEvalCase:
    id: str
    query: str
    expected_intent: str
    expected_skill: str | None
    expected_fast_path: bool
    category: str


@dataclass
class SkillEvalResult:
    id: str
    query: str
    category: str
    expected_intent: str
    predicted_intent: str
    expected_skill: str | None
    predicted_skill: str | None
    expected_fast_path: bool
    predicted_fast_path: bool
    route_correct: bool
    skill_correct: bool
    fast_path_correct: bool


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------


def load_eval_cases(path: Path) -> list[SkillEvalCase]:
    """Load evaluation cases from a JSON file."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [SkillEvalCase(**item) for item in raw]


# ---------------------------------------------------------------------------
# Predict
# ---------------------------------------------------------------------------


def predict_skill_for_query(query: str) -> tuple[str, str | None, bool]:
    """Classify a query and find the matching fast-path Skill.

    Returns ``(predicted_intent, predicted_skill, predicted_fast_path)``.
    """
    from core.router import route_query

    decision = route_query(query)
    predicted_intent = decision.intent.value

    # Lazy import so the module can be loaded without the full src path
    from skills.registry import default_registry

    for skill in default_registry.list_skills():
        if skill.fast_path_enabled and skill.intent == predicted_intent:
            return predicted_intent, skill.name, True

    return predicted_intent, None, False


# ---------------------------------------------------------------------------
# Evaluate
# ---------------------------------------------------------------------------


def evaluate_cases(cases: list[SkillEvalCase]) -> dict:
    """Run all cases through the router + registry and build a report dict."""

    results: list[SkillEvalResult] = []
    failures: list[dict] = []

    for case in cases:
        pred_intent, pred_skill, pred_fast = predict_skill_for_query(case.query)

        route_ok = pred_intent == case.expected_intent
        skill_ok = pred_skill == case.expected_skill
        fast_ok = pred_fast == case.expected_fast_path

        results.append(
            SkillEvalResult(
                id=case.id,
                query=case.query,
                category=case.category,
                expected_intent=case.expected_intent,
                predicted_intent=pred_intent,
                expected_skill=case.expected_skill,
                predicted_skill=pred_skill,
                expected_fast_path=case.expected_fast_path,
                predicted_fast_path=pred_fast,
                route_correct=route_ok,
                skill_correct=skill_ok,
                fast_path_correct=fast_ok,
            )
        )

        if not (route_ok and skill_ok and fast_ok):
            failures.append(
                {
                    "id": case.id,
                    "query": case.query,
                    "expected_intent": case.expected_intent,
                    "predicted_intent": pred_intent,
                    "expected_skill": case.expected_skill,
                    "predicted_skill": pred_skill,
                    "expected_fast_path": case.expected_fast_path,
                    "predicted_fast_path": pred_fast,
                }
            )

    total = len(results)
    route_correct = sum(1 for r in results if r.route_correct)
    skill_correct = sum(1 for r in results if r.skill_correct)
    fast_correct = sum(1 for r in results if r.fast_path_correct)
    hit = sum(1 for r in results if r.predicted_fast_path)
    fallback = total - hit

    # Per-category
    per_category: dict[str, dict] = {}
    for r in results:
        cat = per_category.setdefault(r.category, {"count": 0, "route_correct": 0, "skill_correct": 0})
        cat["count"] += 1
        if r.route_correct:
            cat["route_correct"] += 1
        if r.skill_correct:
            cat["skill_correct"] += 1

    for cat in per_category.values():
        cat["route_accuracy"] = round(cat["route_correct"] / cat["count"], 4) if cat["count"] else 0.0
        cat["skill_accuracy"] = round(cat["skill_correct"] / cat["count"], 4) if cat["count"] else 0.0

    # Per-skill (expected)
    per_skill: dict[str, dict] = {}
    for case in cases:
        sk = case.expected_skill or "(none)"
        ps = per_skill.setdefault(sk, {"expected_count": 0, "predicted_count": 0})
        ps["expected_count"] += 1

    for r in results:
        sk = r.predicted_skill or "(none)"
        ps = per_skill.setdefault(sk, {"expected_count": 0, "predicted_count": 0})
        ps["predicted_count"] += 1

    return {
        "total_cases": total,
        "route_accuracy": round(route_correct / total, 4) if total else 0.0,
        "skill_accuracy": round(skill_correct / total, 4) if total else 0.0,
        "fast_path_accuracy": round(fast_correct / total, 4) if total else 0.0,
        "fast_path_hit_rate": round(hit / total, 4) if total else 0.0,
        "fallback_rate": round(fallback / total, 4) if total else 0.0,
        "per_category": per_category,
        "per_skill": per_skill,
        "failures": failures,
        "results": [asdict(r) for r in results],
        "generated_at": datetime.now(UTC).isoformat(),
    }


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------


def render_markdown_report(report: dict) -> str:
    """Render the evaluation report as Markdown."""

    def _cell(value) -> str:
        if value is None:
            return "-"
        return str(value)

    lines = [
        "# Skill Evaluation Benchmark",
        "",
        f"**Generated**: {report.get('generated_at', '-')}",
        f"**Total cases**: {report['total_cases']}",
        "",
        "## 1. Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
        f"| Route Accuracy | {report['route_accuracy']:.2%} |",
        f"| Skill Accuracy | {report['skill_accuracy']:.2%} |",
        f"| Fast Path Accuracy | {report['fast_path_accuracy']:.2%} |",
        f"| Fast Path Hit Rate | {report['fast_path_hit_rate']:.2%} |",
        f"| Fallback Rate | {report['fallback_rate']:.2%} |",
        "",
        "## 2. Per-category Results",
        "",
        "| Category | Count | Route Accuracy | Skill Accuracy |",
        "| --- | ---: | ---: | ---: |",
    ]

    for cat, data in sorted(report.get("per_category", {}).items()):
        lines.append(
            f"| {cat} | {data['count']} | {data['route_accuracy']:.2%} | {data['skill_accuracy']:.2%} |"
        )

    lines.extend([
        "",
        "## 3. Per-skill Results",
        "",
        "| Skill | Expected Count | Predicted Count |",
        "| --- | ---: | ---: |",
    ])

    for sk, data in sorted(report.get("per_skill", {}).items()):
        lines.append(f"| {sk} | {data['expected_count']} | {data['predicted_count']} |")

    lines.extend([
        "",
        "## 4. Failure Cases",
        "",
    ])

    failures = report.get("failures", [])
    if not failures:
        lines.append("No failures.")
    else:
        lines.append("| ID | Query | Expected Intent | Predicted Intent | Expected Skill | Predicted Skill |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for f in failures:
            lines.append(
                f"| {f['id']} | {f['query']} | {f['expected_intent']} | {f['predicted_intent']} "
                f"| {_cell(f['expected_skill'])} | {_cell(f['predicted_skill'])} |"
            )

    lines.extend([
        "",
        "## 5. Case-level Results",
        "",
        "| ID | Query | Expected Intent | Predicted Intent | Expected Skill | Predicted Skill | Fast Path | Result |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ])

    for r in report.get("results", []):
        result = "PASS" if (r["route_correct"] and r["skill_correct"] and r["fast_path_correct"]) else "FAIL"
        lines.append(
            f"| {r['id']} | {r['query']} | {r['expected_intent']} | {r['predicted_intent']} "
            f"| {_cell(r['expected_skill'])} | {_cell(r['predicted_skill'])} "
            f"| {r['predicted_fast_path']} | {result} |"
        )

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Write
# ---------------------------------------------------------------------------


def write_reports(report: dict, output_dir: Path, name: str) -> tuple[Path, Path]:
    """Write JSON and Markdown reports.  Returns ``(json_path, md_path)``."""
    output_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(UTC).date().isoformat()
    json_path = output_dir / f"{today}_{name}.json"
    md_path = output_dir / f"{today}_{name}.md"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown_report(report), encoding="utf-8")
    return json_path, md_path


# ---------------------------------------------------------------------------
# Threshold check
# ---------------------------------------------------------------------------


def check_thresholds(
    report: dict,
    fail_under_route_accuracy: float | None,
    fail_under_skill_accuracy: float | None,
) -> bool:
    """Return ``True`` when all thresholds are met, ``False`` otherwise."""
    ok = True
    if fail_under_route_accuracy is not None and report["route_accuracy"] < fail_under_route_accuracy:
        print(f"FAIL: route_accuracy {report['route_accuracy']:.2%} < {fail_under_route_accuracy:.2%}")
        ok = False
    if fail_under_skill_accuracy is not None and report["skill_accuracy"] < fail_under_skill_accuracy:
        print(f"FAIL: skill_accuracy {report['skill_accuracy']:.2%} < {fail_under_skill_accuracy:.2%}")
        ok = False
    return ok


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Skill Evaluation Benchmark.")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--name", default="skill_evaluation_benchmark")
    parser.add_argument("--fail-under-route-accuracy", type=float, default=None)
    parser.add_argument("--fail-under-skill-accuracy", type=float, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not args.cases.exists():
        print(f"Cases file not found: {args.cases}", file=sys.stderr)
        return 1

    cases = load_eval_cases(args.cases)
    report = evaluate_cases(cases)
    json_path, md_path = write_reports(report, args.output_dir, args.name)

    print(f"JSON report : {json_path}")
    print(f"Markdown    : {md_path}")
    print()
    print(f"Total cases      : {report['total_cases']}")
    print(f"Route accuracy   : {report['route_accuracy']:.2%}")
    print(f"Skill accuracy   : {report['skill_accuracy']:.2%}")
    print(f"Fast path hit    : {report['fast_path_hit_rate']:.2%}")
    print(f"Fallback rate    : {report['fallback_rate']:.2%}")
    print(f"Failures         : {len(report['failures'])}")

    if not check_thresholds(report, args.fail_under_route_accuracy, args.fail_under_skill_accuracy):
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
