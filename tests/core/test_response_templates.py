from core.response_templates import (
    format_course_fast_path_response,
    format_event_fast_path_response,
    format_fast_path_empty_result,
    format_fast_path_error,
)


def test_course_template_contains_title_conditions_and_tool_result():
    result = format_course_fast_path_response(
        "我周一上午有什么课？",
        {"day": "周一", "time_period": "上午", "course_name": None},
        "找到 1 门符合条件的课程：\n- 数据结构与算法",
    )

    assert "## 课程查询结果" in result
    assert "### 查询条件" in result
    assert "星期：`周一`" in result
    assert "时间段：`上午`" in result
    assert "找到 1 门符合条件的课程" in result


def test_event_template_contains_title_conditions_and_tool_result():
    result = format_event_fast_path_response(
        "这周有什么 AI 相关讲座？",
        {"keyword": "AI", "date_range": "这周", "event_type": "讲座"},
        "找到 1 个符合条件的校园活动：\n- AI Agent 技术分享会",
    )

    assert "## 校园活动查询结果" in result
    assert "### 查询条件" in result
    assert "关键词：`AI`" in result
    assert "活动类型：`讲座`" in result
    assert "AI Agent 技术分享会" in result


def test_empty_result_template_is_readable_for_both_intents():
    course_result = format_fast_path_empty_result(
        "course",
        "周五晚上有什么课？",
        {"day": "周五", "time_period": "晚上"},
    )
    event_result = format_fast_path_empty_result(
        "event",
        "明天有什么比赛？",
        {"date_range": "明天", "event_type": "比赛"},
    )

    assert "暂未找到符合条件的信息" in course_result
    assert "课程查询结果" in course_result
    assert "暂未找到符合条件的信息" in event_result
    assert "校园活动查询结果" in event_result


def test_error_template_does_not_expose_traceback():
    error = "Traceback (most recent call last):\n  File 'tools.py'\nValueError: database gone"

    result = format_fast_path_error("event", error)

    assert "校园活动查询结果" in result
    assert "查询服务暂时不可用" in result
    assert "Traceback" not in result
    assert "tools.py" not in result
