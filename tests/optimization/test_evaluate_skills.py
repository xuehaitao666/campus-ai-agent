"""Tests for the Skill Evaluation Benchmark script."""

import json
import sys
from pathlib import Path

import pytest

# Ensure src/ is importable
_src = Path(__file__).resolve().parents[2] / "src"
sys.path.insert(0, str(_src))

from scripts.evaluate_skills import (
    SkillEvalCase,
    SkillEvalResult,
    check_thresholds,
    evaluate_cases,
    load_eval_cases,
    predict_skill_for_query,
    render_markdown_report,
    write_reports,
)


# ---------------------------------------------------------------------------
# 1. load_eval_cases
# ---------------------------------------------------------------------------

def test_load_eval_cases(tmp_path):
    cases_json = tmp_path / "cases.json"
    cases_json.write_text(
        json.dumps(
            [
                {
                    "id": "c1",
                    "query": "test query",
                    "expected_intent": "course_schedule",
                    "expected_skill": "course_query",
                    "expected_fast_path": True,
                    "category": "course",
                }
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    cases = load_eval_cases(cases_json)

    assert len(cases) == 1
    assert cases[0].id == "c1"
    assert cases[0].query == "test query"
    assert isinstance(cases[0], SkillEvalCase)


# ---------------------------------------------------------------------------
# 2. predict_skill for course
# ---------------------------------------------------------------------------

def test_predict_skill_for_course_query():
    intent, skill, fast = predict_skill_for_query("我周一上午有什么课？")

    assert intent == "course_schedule"
    assert skill == "course_query"
    assert fast is True


# ---------------------------------------------------------------------------
# 3. predict_skill for policy
# ---------------------------------------------------------------------------

def test_predict_skill_for_policy_query():
    intent, skill, fast = predict_skill_for_query("请假流程是什么？")

    assert intent == "campus_policy"
    assert skill == "policy_qa"
    assert fast is True


# ---------------------------------------------------------------------------
# 4. predict_skill for general returns None
# ---------------------------------------------------------------------------

def test_predict_skill_for_general_query_returns_none():
    intent, skill, fast = predict_skill_for_query("什么是 LangGraph？")

    # Router classifies this as "unknown" — no keyword match
    assert skill is None
    assert fast is False


# ---------------------------------------------------------------------------
# 5. evaluate_cases computes metrics
# ---------------------------------------------------------------------------

def test_evaluate_cases_computes_metrics():
    cases = [
        SkillEvalCase(
            id="c1", query="我周一上午有什么课？",
            expected_intent="course_schedule", expected_skill="course_query",
            expected_fast_path=True, category="course",
        ),
        SkillEvalCase(
            id="p1", query="请假流程是什么？",
            expected_intent="campus_policy", expected_skill="policy_qa",
            expected_fast_path=True, category="policy",
        ),
        SkillEvalCase(
            id="g1", query="什么是 LangGraph？",
            expected_intent="unknown", expected_skill=None,
            expected_fast_path=False, category="general",
        ),
    ]

    report = evaluate_cases(cases)

    assert report["total_cases"] == 3
    assert report["route_accuracy"] == 1.0
    assert report["skill_accuracy"] == 1.0
    assert report["fast_path_hit_rate"] == pytest.approx(0.6667, abs=1e-3)
    assert report["fallback_rate"] == pytest.approx(0.3333, abs=1e-3)
    assert len(report["failures"]) == 0


# ---------------------------------------------------------------------------
# 6. render_markdown_report
# ---------------------------------------------------------------------------

def test_render_markdown_report_contains_summary():
    report = evaluate_cases([
        SkillEvalCase(
            id="c1", query="我周一上午有什么课？",
            expected_intent="course_schedule", expected_skill="course_query",
            expected_fast_path=True, category="course",
        ),
    ])

    md = render_markdown_report(report)

    assert "## 1. Summary" in md
    assert "## 2. Per-category Results" in md
    assert "## 4. Failure Cases" in md
    assert "Route Accuracy" in md


# ---------------------------------------------------------------------------
# 7. write_reports creates both files
# ---------------------------------------------------------------------------

def test_write_reports_creates_json_and_markdown(tmp_path):
    report = evaluate_cases([
        SkillEvalCase(
            id="c1", query="我周一上午有什么课？",
            expected_intent="course_schedule", expected_skill="course_query",
            expected_fast_path=True, category="course",
        ),
    ])

    json_path, md_path = write_reports(report, tmp_path, "test_benchmark")

    assert json_path.exists()
    assert md_path.exists()

    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["total_cases"] == 1

    md_text = md_path.read_text(encoding="utf-8")
    assert "Skill Evaluation Benchmark" in md_text


# ---------------------------------------------------------------------------
# 8. threshold check
# ---------------------------------------------------------------------------

def test_fail_under_threshold_exits_nonzero():
    report = {
        "route_accuracy": 0.5,
        "skill_accuracy": 0.5,
    }

    # Above threshold → pass
    assert check_thresholds(report, fail_under_route_accuracy=0.4, fail_under_skill_accuracy=0.4) is True

    # Below route threshold → fail
    assert check_thresholds(report, fail_under_route_accuracy=0.8, fail_under_skill_accuracy=None) is False

    # Below skill threshold → fail
    assert check_thresholds(report, fail_under_route_accuracy=None, fail_under_skill_accuracy=0.8) is False

    # No thresholds → pass
    assert check_thresholds(report, fail_under_route_accuracy=None, fail_under_skill_accuracy=None) is True


# ---------------------------------------------------------------------------
# 9. default cases file is valid JSON and has all categories
# ---------------------------------------------------------------------------

def test_default_cases_file_is_valid():
    from scripts.evaluate_skills import DEFAULT_CASES_PATH

    cases = load_eval_cases(DEFAULT_CASES_PATH)
    assert len(cases) >= 20

    categories = {c.category for c in cases}
    assert categories >= {"course", "event", "policy", "study", "general"}

    # Every case should have a query
    for c in cases:
        assert c.query, f"Case {c.id} has empty query"
