import json
from datetime import date

from agents import tools as campus_tools
from agents.research_assistant import instructions, tools
from agents.tools import (
    CAMPUS_EVENTS_PATH,
    COURSE_SCHEDULE_PATH,
    STUDENT_PROFILE_PATH,
    generate_study_plan_func,
    get_campus_events_func,
    get_course_schedule_func,
)


def _tool_names() -> set[str]:
    return {tool.name for tool in tools}


def test_day15_campus_tools_are_registered_in_default_agent():
    assert {"get_course_schedule", "get_campus_events", "generate_study_plan"} <= _tool_names()


def test_day15_campus_tools_can_read_mock_data_files():
    with COURSE_SCHEDULE_PATH.open(encoding="utf-8") as f:
        courses = json.load(f)
    with CAMPUS_EVENTS_PATH.open(encoding="utf-8") as f:
        events = json.load(f)
    with STUDENT_PROFILE_PATH.open(encoding="utf-8") as f:
        profile = json.load(f)

    assert len(courses) >= 8
    assert len(events) >= 8
    assert profile["major"] == "软件工程"
    assert "AI Agent" in profile["current_goal"]


def test_day15_system_prompt_contains_tool_selection_rules():
    assert "必须优先调用 get_course_schedule" in instructions
    assert "必须优先调用 get_campus_events" in instructions
    assert "必须优先调用 generate_study_plan" in instructions
    assert "如果工具返回没有匹配结果" in instructions


def test_day15_course_question_by_day_and_time_period_uses_mock_data():
    result = get_course_schedule_func(day="周一", time_period="上午")

    assert "数据结构与算法" in result
    assert "软件楼 A302" in result
    assert "刘明" in result
    assert "概率论与数理统计" not in result


def test_day15_course_question_by_course_name_uses_mock_data():
    result = get_course_schedule_func(course_name="数据结构")

    assert "数据结构与算法" in result
    assert "08:30-10:05" in result
    assert "软件楼 A302" in result
    assert "刘明" in result


def test_day15_event_question_by_keyword_uses_mock_data():
    result = get_campus_events_func(keyword="AI", date_range="最近")

    assert "AI Agent 技术分享会" in result
    assert "软件学院报告厅" in result
    assert "通过校园活动平台报名" in result


def test_day15_event_question_by_type_and_audience_uses_mock_data():
    result = get_campus_events_func(
        event_type="讲座",
        date_range="最近",
        target_audience="软件工程",
    )

    assert "AI Agent 技术分享会" in result
    assert "讲座" in result
    assert "软件工程" in result


def test_day15_study_plan_7_days_uses_profile_and_course_schedule():
    plan = json.loads(generate_study_plan_func(goal="AI Agent 学习计划", days=7))

    assert plan["duration_days"] == 7
    assert plan["goal"] == "AI Agent 学习计划"
    assert len(plan["daily_plan"]) == 7
    assert "软件工程" in plan["final_suggestion"]
    assert any("避开上课时间" in item["available_time"] for item in plan["daily_plan"])


def test_day15_study_plan_for_tomorrow_starts_tomorrow(monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 5, 23)

    monkeypatch.setattr(campus_tools, "date", FixedDate)

    plan = json.loads(
        generate_study_plan_func(
            goal="明天学习安排",
            days=1,
            available_time="明天晚上",
        )
    )

    assert plan["duration_days"] == 1
    assert "2026-05-24" in plan["daily_plan"][0]["day"]
    assert "明天晚上" in plan["daily_plan"][0]["available_time"]


def test_day15_no_match_returns_clear_message_without_fabrication():
    course_result = get_course_schedule_func(course_name="量子魔法课")
    event_result = get_campus_events_func(keyword="火星交换生")

    assert "没有找到符合条件的课程" in course_result
    assert "量子魔法课" in course_result
    assert "没有找到符合条件的校园活动" in event_result
    assert "火星交换生" in event_result
