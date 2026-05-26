from datetime import date

from agents import tools
from agents.tools import get_campus_events, get_campus_events_func


def _freeze_today_to_event_fixture(monkeypatch):
    class FixedDate(date):
        @classmethod
        def today(cls):
            return cls(2026, 5, 25)

    monkeypatch.setattr(tools, "date", FixedDate)


def test_get_campus_events_by_keyword():
    result = get_campus_events_func(keyword="Agent")

    assert "AI Agent 技术分享会" in result
    assert "软件学院报告厅" in result
    assert "通过校园活动平台报名" in result


def test_get_campus_events_by_event_type():
    result = get_campus_events_func(event_type="比赛")

    assert "大学生创新创业比赛宣讲" in result
    assert "图书馆路演厅" in result
    assert "比赛" in result


def test_get_campus_events_by_target_audience():
    result = get_campus_events_func(target_audience="软件工程")

    assert "AI Agent 技术分享会" in result
    assert "算法刷题与面试工作坊" in result
    assert "软件工程" in result


def test_get_campus_events_by_date_range(monkeypatch):
    _freeze_today_to_event_fixture(monkeypatch)

    result = get_campus_events_func(date_range="最近")

    assert "AI Agent 技术分享会" in result
    assert "2026-05-25" in result
    assert "大学生心理健康主题沙龙" in result


def test_get_campus_events_with_combined_filters(monkeypatch):
    _freeze_today_to_event_fixture(monkeypatch)

    result = get_campus_events_func(
        keyword="AI",
        date_range="最近",
        event_type="讲座",
        target_audience="软件工程",
    )

    assert "找到 1 个符合条件的校园活动" in result
    assert "AI Agent 技术分享会" in result
    assert "软件学院学生科协" in result


def test_get_campus_events_no_match():
    result = get_campus_events_func(keyword="火星交换生", event_type="比赛")

    assert "没有找到符合条件的校园活动" in result
    assert "火星交换生" in result


def test_get_campus_events_tool_is_registered_with_expected_name():
    assert get_campus_events.name == "get_campus_events"
