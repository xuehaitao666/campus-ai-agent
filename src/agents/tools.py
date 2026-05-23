import json
import math
import re
from datetime import date, datetime, timedelta
from pathlib import Path

import numexpr
from langchain_chroma import Chroma
from langchain_core.tools import BaseTool, tool
from langchain_openai import OpenAIEmbeddings


CAMPUS_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "campus"
COURSE_SCHEDULE_PATH = CAMPUS_DATA_DIR / "course_schedule.json"
CAMPUS_EVENTS_PATH = CAMPUS_DATA_DIR / "campus_events.json"


def calculator_func(expression: str) -> str:
    """Calculates a math expression using numexpr.

    Useful for when you need to answer questions about math using numexpr.
    This tool is only for math questions and nothing else. Only input
    math expressions.

    Args:
        expression (str): A valid numexpr formatted math expression.

    Returns:
        str: The result of the math expression.
    """

    try:
        local_dict = {"pi": math.pi, "e": math.e}
        output = str(
            numexpr.evaluate(
                expression.strip(),
                global_dict={},  # restrict access to globals
                local_dict=local_dict,  # add common mathematical functions
            )
        )
        return re.sub(r"^\[|\]$", "", output)
    except Exception as e:
        raise ValueError(
            f'calculator("{expression}") raised error: {e}.'
            " Please try again with a valid numerical expression"
        )


calculator: BaseTool = tool(calculator_func)
calculator.name = "Calculator"


def _normalize_day(day: str | None) -> str | None:
    if not day:
        return None
    normalized = day.strip().lower()
    day_mapping = {
        "周一": "monday",
        "星期一": "monday",
        "礼拜一": "monday",
        "monday": "monday",
        "mon": "monday",
        "周二": "tuesday",
        "星期二": "tuesday",
        "礼拜二": "tuesday",
        "tuesday": "tuesday",
        "tue": "tuesday",
        "周三": "wednesday",
        "星期三": "wednesday",
        "礼拜三": "wednesday",
        "wednesday": "wednesday",
        "wed": "wednesday",
        "周四": "thursday",
        "星期四": "thursday",
        "礼拜四": "thursday",
        "thursday": "thursday",
        "thu": "thursday",
        "周五": "friday",
        "星期五": "friday",
        "礼拜五": "friday",
        "friday": "friday",
        "fri": "friday",
        "周六": "saturday",
        "星期六": "saturday",
        "礼拜六": "saturday",
        "saturday": "saturday",
        "sat": "saturday",
        "周日": "sunday",
        "周天": "sunday",
        "星期日": "sunday",
        "星期天": "sunday",
        "礼拜日": "sunday",
        "礼拜天": "sunday",
        "sunday": "sunday",
        "sun": "sunday",
    }
    return day_mapping.get(normalized, normalized)


def _load_course_schedule() -> list[dict]:
    with COURSE_SCHEDULE_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("course_schedule.json must contain a list of courses")
    return data


def _format_course(course: dict) -> str:
    return (
        f"- {course['course_name']} | {course['day_of_week']} "
        f"{course['start_time']}-{course['end_time']} ({course['time_period']}) | "
        f"教室：{course['classroom']} | 教师：{course['teacher']} | "
        f"类型：{course['course_type']} | 周次：{course['weeks']} | 备注：{course['note']}"
    )


def get_course_schedule_func(
    day: str | None = None,
    time_period: str | None = None,
    course_name: str | None = None,
) -> str:
    """Query the local mock course schedule.

    Useful when students ask about courses, class time, classroom, teacher,
    course type, weeks, or daily schedule. All parameters are optional and
    can be combined. Use day for weekday values such as "周一" or "Monday",
    time_period for values such as "上午", "下午", or "晚上", and course_name
    for fuzzy course title keywords such as "数据结构".
    """

    courses = _load_course_schedule()
    normalized_day = _normalize_day(day)
    normalized_time_period = time_period.strip().lower() if time_period else None
    normalized_course_name = course_name.strip().lower() if course_name else None

    if not any([normalized_day, normalized_time_period, normalized_course_name]):
        preview = "\n".join(_format_course(course) for course in courses[:5])
        return (
            f"当前 mock 课程表共有 {len(courses)} 门课程。"
            "你可以按星期、时间段或课程名称查询，例如：周一、上午、数据结构。\n"
            f"课程表示例：\n{preview}"
        )

    matched_courses = []
    for course in courses:
        course_day = str(course.get("day_of_week", "")).strip().lower()
        course_time_period = str(course.get("time_period", "")).strip().lower()
        course_title = str(course.get("course_name", "")).strip().lower()

        if normalized_day and course_day != normalized_day:
            continue
        if normalized_time_period and normalized_time_period not in course_time_period:
            continue
        if normalized_course_name and normalized_course_name not in course_title:
            continue

        matched_courses.append(course)

    filters = []
    if day:
        filters.append(f"星期：{day}")
    if time_period:
        filters.append(f"时间段：{time_period}")
    if course_name:
        filters.append(f"课程关键词：{course_name}")
    filter_text = "，".join(filters)

    if not matched_courses:
        return f"没有找到符合条件的课程（{filter_text}）。请确认星期、时间段或课程名称是否正确。"

    formatted_courses = "\n".join(_format_course(course) for course in matched_courses)
    return f"找到 {len(matched_courses)} 门符合条件的课程（{filter_text}）：\n{formatted_courses}"


get_course_schedule: BaseTool = tool(get_course_schedule_func)
get_course_schedule.name = "get_course_schedule"


def _load_campus_events() -> list[dict]:
    with CAMPUS_EVENTS_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("campus_events.json must contain a list of events")
    return data


def _parse_event_date(event: dict) -> date:
    return datetime.strptime(event["date"], "%Y-%m-%d").date()


def _get_date_range_bounds(date_range: str | None) -> tuple[date | None, date | None]:
    if not date_range:
        return None, None

    normalized = date_range.strip().lower()
    today = date.today()

    if normalized in {"今天", "今日", "today"}:
        return today, today
    if normalized in {"明天", "tomorrow"}:
        tomorrow = today + timedelta(days=1)
        return tomorrow, tomorrow
    if normalized in {"本周", "这周", "本星期", "这一周", "this week"}:
        start = today - timedelta(days=today.weekday())
        return start, start + timedelta(days=6)
    if normalized in {"最近", "近期", "近两周", "recent", "upcoming"}:
        return today, today + timedelta(days=30)

    return None, None


def _format_event(event: dict) -> str:
    return (
        f"- {event['title']} | {event['date']} {event['start_time']}-{event['end_time']} | "
        f"地点：{event['location']} | 类型：{event['event_type']} | "
        f"适合人群：{event['target_audience']} | 主办方：{event['organizer']} | "
        f"报名方式：{event['registration_method']} | 简介：{event['description']}"
    )


def get_campus_events_func(
    keyword: str | None = None,
    date_range: str | None = None,
    event_type: str | None = None,
    target_audience: str | None = None,
) -> str:
    """Query local mock campus events.

    Useful when students ask about campus activities, lectures, competitions,
    clubs, recruitment events, workshops, or registration methods. All
    parameters are optional and can be combined. Use keyword for fuzzy matching
    in title, keywords, and description; date_range for values such as "今天",
    "明天", "本周", or "最近"; event_type for values such as "讲座", "比赛",
    "社团", "招聘", or "工作坊"; and target_audience for audience keywords such
    as "软件工程", "计算机", or "人工智能".
    """

    events = sorted(_load_campus_events(), key=lambda event: (event["date"], event["start_time"]))
    normalized_keyword = keyword.strip().lower() if keyword else None
    normalized_event_type = event_type.strip().lower() if event_type else None
    normalized_target_audience = target_audience.strip().lower() if target_audience else None
    start_date, end_date = _get_date_range_bounds(date_range)

    if not any([normalized_keyword, date_range, normalized_event_type, normalized_target_audience]):
        today = date.today()
        upcoming_events = [event for event in events if _parse_event_date(event) >= today]
        preview_events = upcoming_events[:5] if upcoming_events else events[:5]
        preview = "\n".join(_format_event(event) for event in preview_events)
        return (
            f"当前 mock 校园活动库共有 {len(events)} 个活动。"
            "你可以按关键词、活动类型、日期范围或适合人群查询，例如：AI、比赛、最近、软件工程。\n"
            f"近期活动摘要：\n{preview}"
        )

    matched_events = []
    for event in events:
        event_date = _parse_event_date(event)
        title = str(event.get("title", "")).lower()
        keywords = " ".join(str(item) for item in event.get("keywords", [])).lower()
        description = str(event.get("description", "")).lower()
        current_event_type = str(event.get("event_type", "")).lower()
        current_target_audience = str(event.get("target_audience", "")).lower()

        if normalized_keyword and normalized_keyword not in f"{title} {keywords} {description}":
            continue
        if normalized_event_type and normalized_event_type not in current_event_type:
            continue
        if normalized_target_audience and normalized_target_audience not in current_target_audience:
            continue
        if start_date and end_date and not (start_date <= event_date <= end_date):
            continue

        matched_events.append(event)

    filters = []
    if keyword:
        filters.append(f"关键词：{keyword}")
    if date_range:
        filters.append(f"日期范围：{date_range}")
    if event_type:
        filters.append(f"活动类型：{event_type}")
    if target_audience:
        filters.append(f"适合人群：{target_audience}")
    filter_text = "，".join(filters)

    if not matched_events:
        return f"没有找到符合条件的校园活动（{filter_text}）。请确认关键词、活动类型、日期范围或适合人群是否正确。"

    formatted_events = "\n".join(_format_event(event) for event in matched_events)
    return f"找到 {len(matched_events)} 个符合条件的校园活动（{filter_text}）：\n{formatted_events}"


get_campus_events: BaseTool = tool(get_campus_events_func)
get_campus_events.name = "get_campus_events"


# Format retrieved documents
def format_contexts(docs):
    return "\n\n".join(doc.page_content for doc in docs)


def load_chroma_db():
    # Create the embedding function for our project description database
    try:
        embeddings = OpenAIEmbeddings()
    except Exception as e:
        raise RuntimeError(
            "Failed to initialize OpenAIEmbeddings. Ensure the OpenAI API key is set."
        ) from e

    # Load the stored vector database
    chroma_db = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
    retriever = chroma_db.as_retriever(search_kwargs={"k": 5})
    return retriever


def database_search_func(query: str) -> str:
    """Searches chroma_db for information in the company's handbook."""
    # Get the chroma retriever
    retriever = load_chroma_db()

    # Search the database for relevant documents
    documents = retriever.invoke(query)

    # Format the documents into a string
    context_str = format_contexts(documents)

    return context_str


database_search: BaseTool = tool(database_search_func)
database_search.name = "Database_Search"  # Update name with the purpose of your database
