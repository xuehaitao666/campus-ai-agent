from agents.research_assistant import instructions
from agents.tools import (
    generate_study_plan,
    get_campus_events,
    get_course_schedule,
    query_campus_policy,
)


def test_prompt_routes_course_questions_to_course_tool():
    examples = ["我周一上午有什么课？", "数据结构在哪里上？"]

    assert "必须优先调用 get_course_schedule" in instructions
    assert "课程安排、上课时间、上课地点、教室、授课教师" in instructions
    assert "day" in instructions
    assert "time_period" in instructions
    assert "course_name" in instructions
    for example in examples:
        assert "课" in example or "数据结构" in example


def test_prompt_routes_event_questions_to_event_tool():
    examples = ["这周有什么 AI 相关讲座？", "最近有没有适合软件工程学生的活动？"]

    assert "必须优先调用 get_campus_events" in instructions
    assert "校园活动、讲座、比赛、社团活动、招聘会、工作坊" in instructions
    assert "keyword" in instructions
    assert "date_range" in instructions
    assert "event_type" in instructions
    assert "target_audience" in instructions
    for example in examples:
        assert "活动" in example or "讲座" in example


def test_prompt_routes_study_plan_questions_to_study_plan_tool():
    examples = ["帮我制定一份 7 天 AI Agent 学习计划。", "结合我的课程表，安排一下本周学习。"]

    assert "必须优先调用 generate_study_plan" in instructions
    assert "学习计划、备考安排、面试准备、今日学习安排、本周学习规划" in instructions
    assert "goal" in instructions
    assert "days" in instructions
    assert "available_time" in instructions
    assert "focus_topics" in instructions
    for example in examples:
        assert "学习" in example or "课程表" in example


def test_prompt_allows_direct_concept_answers():
    assert "LangGraph、FastAPI、RAG、Docker 是什么，可以直接回答" in instructions


def test_prompt_blocks_unsupported_policy_hallucination():
    assert "请假" in instructions
    assert "必须优先调用 query_campus_policy" in instructions
    assert "知识库中未找到明确依据" in instructions
    assert "不要编造学校规定" in instructions
    assert "不要声称查询了真实学校系统" in instructions


def test_prompt_requires_structured_answers_after_tool_results():
    assert "课程查询：用清晰条目列出课程名、时间、地点/教室、教师、课程类型、周次、备注" in instructions
    assert "活动查询：用清晰条目列出活动名、时间、地点、类型、适合人群、主办方、报名方式、简介" in instructions
    assert "学习计划：用结构化格式列出学习时间、学习主题、实践任务、复盘任务、预期产出" in instructions
    assert "制度问答：按“简要结论、依据说明、办理流程、注意事项、来源文档”组织回答" in instructions
    assert "区分“制度明确规定”和“建议性提醒”" in instructions
    assert "如果工具返回没有匹配结果" in instructions


def test_tool_descriptions_are_routing_friendly():
    course_description = get_course_schedule.description
    event_description = get_campus_events.description
    plan_description = generate_study_plan.description
    policy_description = query_campus_policy.description

    assert "course arrangements" in course_description
    assert "classroom/location" in course_description
    assert "teacher" in course_description
    assert {"day", "time_period", "course_name"} == set(get_course_schedule.args)

    assert "campus activities" in event_description
    assert "lectures" in event_description
    assert "registration methods" in event_description
    assert {"keyword", "date_range", "event_type", "target_audience"} == set(get_campus_events.args)

    assert "Study plan generation tool" in plan_description
    assert "course schedule" in plan_description
    assert "student profile" in plan_description
    assert {"goal", "days", "available_time", "focus_topics"} == set(generate_study_plan.args)

    assert "Campus policy RAG question answering tool" in policy_description
    assert "leave requests" in policy_description
    assert "scholarship eligibility" in policy_description
    assert {"query"} == set(query_campus_policy.args)
