import json
from datetime import date

from agents import tools
from agents.tools import generate_study_plan, generate_study_plan_func


def _load_plan(result: str) -> dict:
    return json.loads(result)


def _freeze_today_to_course_fixture(monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 5, 25)

    monkeypatch.setattr(tools, "date", FixedDate)


def test_generate_study_plan_default_7_days():
    plan = _load_plan(generate_study_plan_func())

    assert plan["duration_days"] == 7
    assert "AI Agent 实习面试" in plan["goal"]
    assert len(plan["daily_plan"]) == 7
    assert {"day", "available_time", "learning_topic", "practice_task", "review_task", "expected_output"} <= set(
        plan["daily_plan"][0]
    )


def test_generate_study_plan_one_day():
    plan = _load_plan(generate_study_plan_func(days=1, available_time="今天下午"))

    assert plan["duration_days"] == 1
    assert "当天学习计划" in plan["plan_title"]
    assert "今天下午" in plan["daily_plan"][0]["available_time"]


def test_generate_study_plan_30_days():
    plan = _load_plan(generate_study_plan_func(days=30))

    assert plan["duration_days"] == 30
    assert len(plan["daily_plan"]) == 30
    assert "30 天阶段性学习计划" in plan["plan_title"]


def test_generate_study_plan_with_goal():
    plan = _load_plan(generate_study_plan_func(goal="期末复习", days=7))

    assert plan["goal"] == "期末复习"
    assert "期末复习" in plan["plan_title"]


def test_generate_study_plan_with_focus_topics():
    plan = _load_plan(generate_study_plan_func(focus_topics="LangGraph, FastAPI, RAG", days=3))
    topics = [item["learning_topic"] for item in plan["daily_plan"]]

    assert "LangGraph" in topics[0]
    assert "FastAPI" in topics[1]
    assert "RAG" in topics[2]


def test_generate_study_plan_avoids_course_time(monkeypatch):
    _freeze_today_to_course_fixture(monkeypatch)

    plan = _load_plan(generate_study_plan_func(days=4))
    monday_plan = plan["daily_plan"][0]

    assert "Monday" in monday_plan["day"]
    assert "避开上课时间" in monday_plan["available_time"]
    assert "08:30-10:05" in monday_plan["available_time"]
    assert "14:00-15:35" in monday_plan["available_time"]


def test_generate_study_plan_tolerates_missing_profile_fields(tmp_path, monkeypatch):
    profile_path = tmp_path / "student_profile.json"
    profile_path.write_text(json.dumps({"current_goal": "补齐 Python 基础"}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(tools, "STUDENT_PROFILE_PATH", profile_path)

    plan = _load_plan(generate_study_plan_func(days=2))

    assert plan["goal"] == "补齐 Python 基础"
    assert plan["duration_days"] == 2
    assert len(plan["daily_plan"]) == 2
    assert "未知专业" in plan["final_suggestion"]


def test_generate_study_plan_tool_is_registered_with_expected_name():
    assert generate_study_plan.name == "generate_study_plan"
