from agents.tools import get_course_schedule, get_course_schedule_func


def test_get_course_schedule_by_day():
    result = get_course_schedule_func(day="周一")

    assert "找到 2 门符合条件的课程" in result
    assert "数据结构与算法" in result
    assert "概率论与数理统计" in result
    assert "软件楼 A302" in result


def test_get_course_schedule_by_time_period():
    result = get_course_schedule_func(time_period="晚上")

    assert "人工智能基础" in result
    assert "体育：羽毛球" in result
    assert "晚上第9-10节" in result


def test_get_course_schedule_by_course_name():
    result = get_course_schedule_func(course_name="数据结构")

    assert "数据结构与算法" in result
    assert "刘明" in result
    assert "专业必修" in result


def test_get_course_schedule_no_match():
    result = get_course_schedule_func(day="周日", course_name="量子计算")

    assert "没有找到符合条件的课程" in result
    assert "不要编造" not in result


def test_get_course_schedule_with_combined_filters():
    result = get_course_schedule_func(day="周二", time_period="晚上", course_name="人工智能")

    assert "找到 1 门符合条件的课程" in result
    assert "人工智能基础" in result
    assert "智慧教室 C105" in result
    assert "赵晨" in result


def test_get_course_schedule_tool_is_registered_with_expected_name():
    assert get_course_schedule.name == "get_course_schedule"
