"""Built-in Skill definitions for Campus AI Agent v0.1.

Each Skill metadata record describes an existing capability without changing
any execution logic.  trigger_keywords are imported from core.router to stay
in sync with the live keyword-based router.
"""

from core.router import COURSE_KEYWORDS, EVENT_KEYWORDS, POLICY_KEYWORDS, STUDY_PLAN_KEYWORDS, RouteIntent
from skills.base import SkillExample, SkillMetadata

# ---------------------------------------------------------------------------
# course_query_skill
# ---------------------------------------------------------------------------

COURSE_QUERY_SKILL = SkillMetadata(
    name="course_query",
    display_name="课程查询",
    description="查询课程安排、上课时间、教室和教师信息。",
    version="1.0.0",
    intent=RouteIntent.COURSE.value,
    trigger_keywords=list(COURSE_KEYWORDS),
    fast_path_enabled=True,
    fast_path_handler_name="_maybe_handle_course_fast_path",
    bound_tools=["get_course_schedule"],
    input_schema={
        "day": "str | None",
        "time_period": "str | None",
        "course_name": "str | None",
    },
    output_format="structured_markdown",
    response_template_name="format_course_fast_path_response",
    examples=[
        SkillExample(
            query="我周一上午有什么课？",
            expected_intent=RouteIntent.COURSE.value,
            expected_params={
                "day": "周一",
                "time_period": "上午",
                "course_name": None,
            },
        ),
        SkillExample(
            query="数据结构课在哪里上？",
            expected_intent=RouteIntent.COURSE.value,
            expected_params={
                "day": None,
                "time_period": None,
                "course_name": "数据结构",
            },
        ),
    ],
)

# ---------------------------------------------------------------------------
# event_query_skill
# ---------------------------------------------------------------------------

EVENT_QUERY_SKILL = SkillMetadata(
    name="event_query",
    display_name="校园活动查询",
    description="查询校园活动、讲座、比赛、报名和宣讲会信息。",
    version="1.0.0",
    intent=RouteIntent.EVENT.value,
    trigger_keywords=list(EVENT_KEYWORDS),
    fast_path_enabled=True,
    fast_path_handler_name="_maybe_handle_event_fast_path",
    bound_tools=["get_campus_events"],
    input_schema={
        "keyword": "str | None",
        "date_range": "str | None",
        "event_type": "str | None",
        "target_audience": "str | None",
    },
    output_format="structured_markdown",
    response_template_name="format_event_fast_path_response",
    examples=[
        SkillExample(
            query="这周有什么 AI 相关讲座？",
            expected_intent=RouteIntent.EVENT.value,
            expected_params={
                "keyword": "AI",
                "date_range": "这周",
                "event_type": "讲座",
                "target_audience": None,
            },
        ),
        SkillExample(
            query="最近有什么比赛可以报名？",
            expected_intent=RouteIntent.EVENT.value,
            expected_params={
                "keyword": "报名",
                "date_range": "最近",
                "event_type": "比赛",
                "target_audience": None,
            },
        ),
    ],
)

# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# policy_qa_skill
# ---------------------------------------------------------------------------

POLICY_QA_SKILL = SkillMetadata(
    name="policy_qa",
    display_name="校园制度问答",
    description="基于校园制度知识库的 RAG 问答，覆盖请假、奖学金、宿舍、考试纪律等。",
    version="1.0.0",
    intent=RouteIntent.POLICY.value,
    trigger_keywords=list(POLICY_KEYWORDS),
    fast_path_enabled=True,
    fast_path_handler_name="_maybe_handle_policy_qa_fast_path",
    bound_tools=["query_campus_policy"],
    input_schema={"query": "str"},
    output_format="structured_markdown",
    response_template_name=None,
    examples=[
        SkillExample(
            query="请假流程是什么？",
            expected_intent=RouteIntent.POLICY.value,
        ),
        SkillExample(
            query="挂科了还能申请奖学金吗？",
            expected_intent=RouteIntent.POLICY.value,
        ),
        SkillExample(
            query="宿舍晚归会怎么处理？",
            expected_intent=RouteIntent.POLICY.value,
        ),
        SkillExample(
            query="考试作弊有什么后果？",
            expected_intent=RouteIntent.POLICY.value,
        ),
    ],
)

# --------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# study_plan_skill
# ---------------------------------------------------------------------------

STUDY_PLAN_SKILL = SkillMetadata(
    name="study_plan",
    display_name="学习计划生成",
    description="基于学生画像和课程表生成个性化学习计划，支持备考、面试准备、复习安排和学习路线规划。",
    version="1.0.0",
    intent=RouteIntent.STUDY_PLAN.value,
    trigger_keywords=list(STUDY_PLAN_KEYWORDS),
    fast_path_enabled=True,
    fast_path_handler_name="_maybe_handle_study_plan_fast_path",
    bound_tools=["generate_study_plan"],
    input_schema={
        "goal": "str | None",
        "days": "int",
        "available_time": "str | None",
        "focus_topics": "str | None",
    },
    output_format="structured_markdown",
    response_template_name="format_study_plan_fast_path_response",
    examples=[
        SkillExample(
            query="帮我制定一份 7 天 AI Agent 学习计划",
            expected_intent=RouteIntent.STUDY_PLAN.value,
        ),
        SkillExample(
            query="帮我准备 AI Agent 面试学习路线",
            expected_intent=RouteIntent.STUDY_PLAN.value,
        ),
        SkillExample(
            query="我明天下午没课，帮我安排学习",
            expected_intent=RouteIntent.STUDY_PLAN.value,
        ),
        SkillExample(
            query="结合我的课程表，帮我规划本周学习",
            expected_intent=RouteIntent.STUDY_PLAN.value,
        ),
    ],
)

# Built-in skill list

BUILTIN_SKILLS: list[SkillMetadata] = [COURSE_QUERY_SKILL, EVENT_QUERY_SKILL, POLICY_QA_SKILL, STUDY_PLAN_SKILL]
