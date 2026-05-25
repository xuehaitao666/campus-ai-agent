import json
import logging
import math
import re
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path

import numexpr
from langchain_chroma import Chroma
from langchain_core.tools import BaseTool, tool

from core.tracing import TraceRecord, TraceSpan, current_trace_record, write_trace_jsonl

CAMPUS_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "campus"
COURSE_SCHEDULE_PATH = CAMPUS_DATA_DIR / "course_schedule.json"
CAMPUS_EVENTS_PATH = CAMPUS_DATA_DIR / "campus_events.json"
STUDENT_PROFILE_PATH = CAMPUS_DATA_DIR / "student_profile.json"
CAMPUS_POLICY_VECTOR_STORE_DIR = (
    Path(__file__).resolve().parents[2] / "data" / "vector_store" / "campus_policy"
)
CAMPUS_POLICY_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
logger = logging.getLogger(__name__)


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
    """Campus course schedule lookup tool.

    Use this tool whenever the user asks about course arrangements, class time,
    classroom/location, teacher, whether they have class on a certain day, what
    classes are in the morning/afternoon/evening, or where a specific course is
    held. It reads local mock course data, not a real educational administration
    system.

    Args:
        day: Optional weekday filter, such as "周一", "周二", "星期三", or "Monday".
        time_period: Optional time filter, such as "上午", "下午", or "晚上".
        course_name: Optional fuzzy course-name keyword, such as "数据结构" or "人工智能".
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
    """Campus event lookup tool.

    Use this tool whenever the user asks about campus activities, lectures,
    competitions, club events, recruitment fairs, workshops, event time, event
    location, suitable audience, organizers, or registration methods. It reads
    local mock event data, not a real campus activity platform.

    Args:
        keyword: Optional keyword matched against title, keywords, and description,
            such as "AI", "Agent", "实习", "比赛", or "报名".
        date_range: Optional date range, such as "今天", "明天", "本周", or "最近".
        event_type: Optional event type, such as "讲座", "比赛", "社团", "招聘", or "工作坊".
        target_audience: Optional audience keyword, such as "软件工程", "计算机", or "人工智能".
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


def _load_student_profile() -> dict:
    with STUDENT_PROFILE_PATH.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("student_profile.json must contain a student profile object")
    return data


def _split_focus_topics(focus_topics: str | None, profile: dict) -> list[str]:
    if focus_topics:
        topics = [
            item.strip() for item in re.split(r"[,，、/]\s*|\s+", focus_topics) if item.strip()
        ]
        if topics:
            return topics

    profile_topics = profile.get("skills_to_improve", [])
    if isinstance(profile_topics, list) and profile_topics:
        return [str(topic) for topic in profile_topics]

    return ["基础知识复习", "项目实践", "面试表达"]


def _preferred_time_for_day(day_date: date, profile: dict, available_time: str | None) -> str:
    if available_time:
        base_time = available_time
    else:
        preferred = profile.get("preferred_study_time", {})
        if isinstance(preferred, dict):
            key = "weekend" if day_date.weekday() >= 5 else "weekday"
            values = preferred.get(key) or preferred.get("weekday") or preferred.get("weekend")
            if isinstance(values, list):
                base_time = "；".join(str(value) for value in values)
            elif values:
                base_time = str(values)
            else:
                base_time = "晚上 19:30-22:00"
        else:
            base_time = "晚上 19:30-22:00"

    day_name = day_date.strftime("%A")
    courses = [
        course for course in _load_course_schedule() if course.get("day_of_week") == day_name
    ]
    if not courses:
        return base_time

    busy_slots = "；".join(
        f"{course.get('start_time')}-{course.get('end_time')} {course.get('course_name')}"
        for course in courses
    )
    return f"{base_time}（已参考课程表，避开上课时间：{busy_slots}）"


def _build_learning_topic(topics: list[str], day_index: int, goal: str) -> str:
    topic = topics[(day_index - 1) % len(topics)]
    return f"{topic}：围绕“{goal}”补齐核心知识点"


def _get_plan_start_date(available_time: str | None) -> date:
    if not available_time:
        return date.today()

    normalized = available_time.strip().lower()
    if "明天" in normalized or "tomorrow" in normalized:
        return date.today() + timedelta(days=1)

    return date.today()


def generate_study_plan_func(
    goal: str | None = None,
    days: int = 7,
    available_time: str | None = None,
    focus_topics: str | None = None,
) -> str:
    """Study plan generation tool.

    Use this tool whenever the user asks for a study plan, exam preparation,
    interview preparation, internship preparation, today's learning arrangement,
    weekly planning, or a plan that should consider the course schedule. It
    combines local mock student profile data and local mock course schedule data
    to produce a structured plan. It does not know real exams or official school
    arrangements unless the user provides them.

    Args:
        goal: Optional learning goal, such as "AI Agent 实习面试" or "期末复习".
        days: Number of days for the plan, such as 1, 7, 14, or 30. Defaults to 7.
        available_time: Optional user-provided available time, such as "晚上", "周末", or "今天下午".
        focus_topics: Optional focus topics, such as "LangGraph, FastAPI, RAG, Docker".
    """

    profile = _load_student_profile()
    normalized_days = max(1, min(int(days or 7), 30))
    target_goal = goal or profile.get("current_goal") or "完成阶段性学习目标"
    topics = _split_focus_topics(focus_topics, profile)
    start_date = _get_plan_start_date(available_time)

    daily_plan = []
    for index in range(1, normalized_days + 1):
        day_date = start_date + timedelta(days=index - 1)
        topic = _build_learning_topic(topics, index, target_goal)
        daily_plan.append(
            {
                "day": f"Day {index}（{day_date.isoformat()}，{day_date.strftime('%A')}）",
                "available_time": _preferred_time_for_day(day_date, profile, available_time),
                "learning_topic": topic,
                "practice_task": f"完成一个与“{topics[(index - 1) % len(topics)]}”相关的小任务，并记录关键代码、命令或解题过程。",
                "review_task": "用 10-15 分钟复盘今天的卡点、产出和明天要继续的问题。",
                "expected_output": f"形成 1 份关于“{topics[(index - 1) % len(topics)]}”的学习笔记或可展示成果。",
            }
        )

    if normalized_days == 1:
        plan_title = f"{target_goal}：当天学习计划"
    elif normalized_days >= 30:
        plan_title = f"{target_goal}：30 天阶段性学习计划"
    else:
        plan_title = f"{target_goal}：{normalized_days} 天学习计划"

    weekly_available_hours = profile.get("weekly_available_hours", "未提供")
    learning_style = profile.get("learning_style", "未提供")
    constraints = profile.get("constraints", [])
    constraints_text = (
        "；".join(str(item) for item in constraints)
        if isinstance(constraints, list)
        else str(constraints)
    )

    plan = {
        "plan_title": plan_title,
        "goal": target_goal,
        "duration_days": normalized_days,
        "daily_plan": daily_plan,
        "final_suggestion": (
            f"该计划参考了学生画像：{profile.get('grade', '未知年级')}、{profile.get('major', '未知专业')}，"
            f"每周可用学习时间约 {weekly_available_hours} 小时，学习风格为：{learning_style}。"
            f"安排时已参考课程表，尽量避开上课时间。约束条件：{constraints_text or '暂无'}。"
            "不要把本计划视为学校正式安排，可根据课程作业、考试通知和个人状态滚动调整。"
        ),
    }
    return json.dumps(plan, ensure_ascii=False, indent=2)


generate_study_plan: BaseTool = tool(generate_study_plan_func)
generate_study_plan.name = "generate_study_plan"


# Format retrieved documents
def format_contexts(docs):
    formatted_docs = []
    for index, doc in enumerate(docs, 1):
        source = doc.metadata.get("source", "unknown")
        path = doc.metadata.get("path", "")
        chunk_id = doc.metadata.get("chunk_id", f"chunk-{index}")
        formatted_docs.append(
            f"--- Source: {source} | Path: {path} | Chunk: {chunk_id} ---\n{doc.page_content}"
        )
    return "\n\n".join(formatted_docs)


@lru_cache(maxsize=1)
def create_campus_policy_embeddings():
    try:
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError as e:
        raise RuntimeError(
            "Failed to initialize local HuggingFace embeddings. "
            "Install langchain-huggingface and sentence-transformers."
        ) from e

    return HuggingFaceEmbeddings(
        model_name=CAMPUS_POLICY_EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def _record_rag_trace(
    route: str,
    query: str | None,
    documents,
    retrieval_time_ms: float,
    rag_load_time_ms: float | None = None,
    error_message: str | None = None,
    update_request: bool = True,
) -> None:
    request_record = current_trace_record()
    if request_record is None:
        return

    retrieved_docs = [
        {
            "source": doc.metadata.get("source", "unknown"),
            "path": doc.metadata.get("path", ""),
            "chunk_id": doc.metadata.get("chunk_id", ""),
        }
        for doc in (documents or [])
    ]
    source_list = [str(doc["source"]) for doc in retrieved_docs]
    chunk_id_list = [str(doc["chunk_id"]) for doc in retrieved_docs if doc["chunk_id"]]
    record = TraceRecord(
        trace_id=request_record.trace_id,
        run_id=request_record.run_id,
        thread_id=request_record.thread_id,
        user_id=request_record.user_id,
        agent_id=request_record.agent_id,
        model_name=request_record.model_name,
        query=query,
        route=route,
        tool_calls=[{"name": route, "args": {"query": query} if query else {}}],
        retrieved_docs=retrieved_docs,
        rag_load_time_ms=rag_load_time_ms,
        retrieval_time_ms=retrieval_time_ms,
        error_message=error_message,
        event_type="rag_retrieval",
        returned_doc_count=len(retrieved_docs) if documents is not None else None,
        source_list=source_list,
        chunk_id_list=chunk_id_list,
        is_empty_result=not retrieved_docs if documents is not None else None,
    )
    try:
        write_trace_jsonl(record)
    except Exception as e:
        logger.warning(f"Unable to write RAG trace record: {e}")

    if not update_request:
        return
    request_record.retrieved_docs.extend(retrieved_docs)
    request_record.rag_load_time_ms = (request_record.rag_load_time_ms or 0) + (
        rag_load_time_ms or 0
    )
    request_record.retrieval_time_ms = (request_record.retrieval_time_ms or 0) + retrieval_time_ms
    request_record.tool_time_ms = (
        (request_record.tool_time_ms or 0) + retrieval_time_ms + (rag_load_time_ms or 0)
    )
    if error_message and request_record.error_message is None:
        request_record.error_message = error_message
    if not any(
        call.get("name") == route and call.get("args", {}).get("query") == query
        for call in request_record.tool_calls
    ):
        request_record.tool_calls.append({"name": route, "args": {"query": query} if query else {}})


@lru_cache(maxsize=1)
def load_chroma_db():
    timer = TraceSpan().start()
    try:
        # Create the embedding function for our project description database
        embeddings = create_campus_policy_embeddings()

        # Load the stored campus policy vector database
        chroma_db = Chroma(
            persist_directory=str(CAMPUS_POLICY_VECTOR_STORE_DIR),
            embedding_function=embeddings,
        )
        retriever = chroma_db.as_retriever(search_kwargs={"k": 5})
    except Exception as e:
        _record_rag_trace(
            "load_chroma_db",
            None,
            None,
            timer.stop(),
            rag_load_time_ms=timer.elapsed_ms,
            error_message=str(e),
            update_request=False,
        )
        raise
    _record_rag_trace(
        "load_chroma_db",
        None,
        None,
        timer.stop(),
        rag_load_time_ms=timer.elapsed_ms,
        update_request=False,
    )
    return retriever


def clear_rag_cache() -> None:
    """Release cached campus-policy retrieval resources after index updates."""
    load_chroma_db.cache_clear()
    create_campus_policy_embeddings.cache_clear()


def _extract_policy_snippets(documents, keyword: str) -> list[str]:
    snippets = []
    for doc in documents:
        lines = [line.strip() for line in doc.page_content.splitlines() if line.strip()]
        matched_lines = [line for line in lines if keyword in line][:3]
        if matched_lines:
            snippets.extend(matched_lines)
            continue
        snippets.extend(lines[:3])
    return snippets[:6]


def _format_policy_sources(documents) -> str:
    sources = []
    for doc in documents:
        source = doc.metadata.get("source", "unknown")
        chunk_id = doc.metadata.get("chunk_id", "")
        source_text = f"- {source}"
        if chunk_id:
            source_text += f"（{chunk_id}）"
        if source_text not in sources:
            sources.append(source_text)
    return "\n".join(sources)


def _policy_no_answer(reason: str) -> str:
    return (
        "## 简要结论\n"
        "知识库中未找到明确依据。\n\n"
        "## 依据说明\n"
        f"{reason}\n\n"
        "## 办理流程\n"
        "知识库中未找到明确依据。\n\n"
        "## 注意事项\n"
        "建议以学校官方通知或辅导员答复为准。不要据此推断具体办理窗口、电话号码、网址或时间安排。\n\n"
        "## 来源文档\n"
        "无"
    )


def _has_relevant_policy_context(query: str, documents) -> bool:
    corpus = " ".join(
        f"{doc.page_content} {doc.metadata.get('source', '')}" for doc in documents
    ).lower()
    policy_keyword_groups = [
        {"请假", "病假", "事假", "假"},
        {"奖学金", "评奖", "挂科", "综测"},
        {"宿舍", "晚归", "大功率", "电器"},
        {"考试", "作弊", "缺考", "缓考", "旷考", "纪律"},
        {"学生手册", "手册"},
        {"材料", "证明"},
        {"流程", "申请", "办理"},
    ]
    matched_groups = [
        group for group in policy_keyword_groups if any(word in query for word in group)
    ]
    if not matched_groups:
        return bool(corpus.strip())
    return any(any(word.lower() in corpus for word in group) for group in matched_groups)


def query_campus_policy_func(query: str) -> str:
    """Campus policy RAG question answering tool.

    Use this tool when the user asks about campus policies or student handbook
    rules, including leave requests, scholarship eligibility, dormitory
    management, exam discipline, absence from exams, make-up exams, and student
    handbook procedures. It retrieves from the local Chroma vector store built
    from data/knowledge_base Markdown documents.

    Args:
        query: The user's campus policy question, such as "请假流程是什么？",
            "挂科后还能评奖学金吗？", or "考试作弊有什么后果？".
    """

    load_timer = TraceSpan().start()
    try:
        retriever = load_chroma_db()
        rag_load_time_ms = load_timer.stop()
        retrieval_timer = TraceSpan().start()
        documents = retriever.invoke(query)
    except Exception as e:
        if load_timer.elapsed_ms is None:
            rag_load_time_ms = load_timer.stop()
            retrieval_time_ms = 0.0
        else:
            retrieval_time_ms = retrieval_timer.stop()
        _record_rag_trace(
            "query_campus_policy",
            query,
            [],
            retrieval_time_ms,
            rag_load_time_ms=rag_load_time_ms,
            error_message=str(e),
        )
        raise
    _record_rag_trace(
        "query_campus_policy",
        query,
        documents,
        retrieval_timer.stop(),
        rag_load_time_ms=rag_load_time_ms,
    )

    if not documents:
        return _policy_no_answer("未检索到与该问题直接相关的校园制度文档片段。")

    if not _has_relevant_policy_context(query, documents):
        return _policy_no_answer("当前检索结果与问题相关性不足，当前依据不足。")

    basis_snippets = _extract_policy_snippets(documents, "条件")
    process_snippets = _extract_policy_snippets(documents, "流程")
    note_snippets = _extract_policy_snippets(documents, "注意")

    return (
        "## 简要结论\n"
        "已基于校园制度知识库检索结果整理如下。涉及未在检索片段中明确出现的细节，当前知识库未提供明确说明。\n\n"
        "## 依据说明\n"
        "### 制度明确规定\n" + "\n".join(f"- {snippet}" for snippet in basis_snippets) + "\n\n"
        "### 建议性提醒\n"
        "- 以下回答仅依据本地校园制度知识库检索片段，不代表查询了真实学校系统。\n"
        "- 未在来源文档中明确出现的办理窗口、电话号码、网址或具体时间，当前知识库未提供明确说明。"
        + "\n\n"
        "## 办理流程\n" + "\n".join(f"- {snippet}" for snippet in process_snippets) + "\n\n"
        "## 注意事项\n" + "\n".join(f"- {snippet}" for snippet in note_snippets) + "\n\n"
        "## 来源文档\n" + _format_policy_sources(documents)
    )


query_campus_policy: BaseTool = tool(query_campus_policy_func)
query_campus_policy.name = "query_campus_policy"


def database_search_func(query: str) -> str:
    """Searches the campus policy knowledge base for student handbook information."""
    load_timer = TraceSpan().start()
    try:
        # Get the chroma retriever
        retriever = load_chroma_db()
        rag_load_time_ms = load_timer.stop()

        # Search the database for relevant documents
        retrieval_timer = TraceSpan().start()
        documents = retriever.invoke(query)
    except Exception as e:
        if load_timer.elapsed_ms is None:
            rag_load_time_ms = load_timer.stop()
            retrieval_time_ms = 0.0
        else:
            retrieval_time_ms = retrieval_timer.stop()
        _record_rag_trace(
            "Database_Search",
            query,
            [],
            retrieval_time_ms,
            rag_load_time_ms=rag_load_time_ms,
            error_message=str(e),
        )
        raise
    _record_rag_trace(
        "Database_Search",
        query,
        documents,
        retrieval_timer.stop(),
        rag_load_time_ms=rag_load_time_ms,
    )

    # Format the documents into a string
    context_str = format_contexts(documents)

    return context_str


database_search: BaseTool = tool(database_search_func)
database_search.name = "Database_Search"  # Update name with the purpose of your database
