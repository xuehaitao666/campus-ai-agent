from dataclasses import dataclass, field
from enum import StrEnum


class RouteIntent(StrEnum):
    COURSE = "course_schedule"
    EVENT = "campus_event"
    STUDY_PLAN = "study_plan"
    POLICY = "campus_policy"
    GENERAL = "general_chat"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class RouteDecision:
    intent: RouteIntent
    confidence: float
    matched_keywords: list[str] = field(default_factory=list)
    reason: str = ""
    route_source: str = "rule"


COURSE_KEYWORDS = (
    "课程",
    "上课",
    "课表",
    "教室",
    "老师",
    "教师",
    "周一",
    "周二",
    "周三",
    "周四",
    "周五",
    "星期一",
    "星期二",
    "星期三",
    "星期四",
    "星期五",
    "今天",
    "明天",
    "上午",
    "下午",
    "晚上",
    "数据结构",
    "操作系统",
)
EVENT_KEYWORDS = (
    "活动",
    "讲座",
    "比赛",
    "竞赛",
    "报名",
    "社团",
    "宣讲会",
    "ai",
    "招聘会",
    "分享会",
)
EVENT_CONTEXT_KEYWORDS = tuple(keyword for keyword in EVENT_KEYWORDS if keyword != "ai")
STUDY_PLAN_KEYWORDS = (
    "学习计划",
    "复习",
    "备考",
    "面试",
    "安排",
    "规划",
    "怎么学",
    "学习路线",
    "本周计划",
    "7天",
    "七天",
)
POLICY_KEYWORDS = (
    "请假",
    "奖学金",
    "挂科",
    "宿舍",
    "晚归",
    "考试",
    "作弊",
    "缺考",
    "处分",
    "补考",
    "缓考",
    "学籍",
    "违纪",
)
GENERAL_KEYWORDS = ("你好", "你是谁", "你能做什么", "介绍一下")
COURSE_DAY_ALIASES = (
    ("星期一", "周一"),
    ("周一", "周一"),
    ("星期二", "周二"),
    ("周二", "周二"),
    ("星期三", "周三"),
    ("周三", "周三"),
    ("星期四", "周四"),
    ("周四", "周四"),
    ("星期五", "周五"),
    ("周五", "周五"),
)
COURSE_TIME_PERIODS = ("上午", "下午", "晚上")
COURSE_NAMES = ("数据结构", "操作系统")
EVENT_DATE_RANGES = ("这周", "本周", "最近", "今天", "明天")
EVENT_TYPE_ALIASES = (
    ("招聘会", "招聘"),
    ("讲座", "讲座"),
    ("比赛", "比赛"),
    ("竞赛", "比赛"),
    ("社团", "社团"),
)


def _matches(query: str, keywords: tuple[str, ...]) -> list[str]:
    return [keyword for keyword in keywords if keyword in query]


def _decision(
    intent: RouteIntent,
    keywords: list[str],
    reason: str,
    *,
    base_confidence: float = 0.72,
) -> RouteDecision:
    confidence = min(0.99, base_confidence + 0.06 * max(len(keywords) - 1, 0))
    return RouteDecision(
        intent=intent,
        confidence=confidence,
        matched_keywords=keywords,
        reason=reason,
    )


def parse_course_query(query: str) -> dict[str, str | None]:
    """Extract supported course schedule filters for a rule-based fast path."""
    normalized_query = query.strip().lower()
    day = next(
        (canonical for alias, canonical in COURSE_DAY_ALIASES if alias in normalized_query),
        None,
    )
    time_period = next(
        (period for period in COURSE_TIME_PERIODS if period in normalized_query),
        None,
    )
    course_name = next(
        (course for course in COURSE_NAMES if course in normalized_query),
        None,
    )
    return {
        "day": day,
        "time_period": time_period,
        "course_name": course_name,
    }


def parse_event_query(query: str) -> dict[str, str | None]:
    """Extract event filters supported by the local campus events tool."""
    normalized_query = query.strip().lower()
    date_range = next(
        (date_range for date_range in EVENT_DATE_RANGES if date_range in normalized_query),
        None,
    )
    event_type = next(
        (canonical for alias, canonical in EVENT_TYPE_ALIASES if alias in normalized_query),
        None,
    )

    keyword = None
    if "ai" in normalized_query or "人工智能" in normalized_query:
        keyword = "AI"
    elif "软件工程" in normalized_query:
        keyword = "软件工程"
    elif "宣讲会" in normalized_query:
        keyword = "宣讲"
    elif "报名" in normalized_query:
        keyword = "报名"

    return {
        "keyword": keyword,
        "date_range": date_range,
        "event_type": event_type,
        "target_audience": None,
    }


def route_query(query: str) -> RouteDecision:
    """Classify a user query without invoking models, agents, or tools."""
    normalized_query = query.strip().lower()
    if not normalized_query:
        return RouteDecision(
            intent=RouteIntent.UNKNOWN,
            confidence=0.0,
            reason="Query is empty after trimming whitespace.",
        )

    study_matches = _matches(normalized_query, STUDY_PLAN_KEYWORDS)
    policy_matches = _matches(normalized_query, POLICY_KEYWORDS)
    course_matches = _matches(normalized_query, COURSE_KEYWORDS)
    event_context_matches = _matches(normalized_query, EVENT_CONTEXT_KEYWORDS)
    event_matches = _matches(normalized_query, EVENT_KEYWORDS) if event_context_matches else []
    general_matches = _matches(normalized_query, GENERAL_KEYWORDS)

    if study_matches:
        return _decision(
            RouteIntent.STUDY_PLAN,
            study_matches,
            "Matched an explicit study planning or preparation expression.",
            base_confidence=0.82,
        )
    if policy_matches:
        return _decision(
            RouteIntent.POLICY,
            policy_matches,
            "Matched a campus policy, discipline, or student affairs expression.",
            base_confidence=0.86,
        )
    if event_matches:
        return _decision(
            RouteIntent.EVENT,
            event_matches,
            "Matched an explicit campus event expression; AI is only considered with event context.",
            base_confidence=0.82,
        )
    if course_matches:
        return _decision(
            RouteIntent.COURSE,
            course_matches,
            "Matched a course, classroom, subject, or teaching-time expression.",
            base_confidence=0.78,
        )
    if general_matches:
        return _decision(
            RouteIntent.GENERAL,
            general_matches,
            "Matched a greeting or assistant-introduction expression.",
            base_confidence=0.75,
        )

    return RouteDecision(
        intent=RouteIntent.UNKNOWN,
        confidence=0.0,
        reason="No rule keyword matched the query.",
    )
