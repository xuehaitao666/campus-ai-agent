import json
import math
import re
from pathlib import Path

import numexpr
from langchain_chroma import Chroma
from langchain_core.tools import BaseTool, tool
from langchain_openai import OpenAIEmbeddings


CAMPUS_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "campus"
COURSE_SCHEDULE_PATH = CAMPUS_DATA_DIR / "course_schedule.json"


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
