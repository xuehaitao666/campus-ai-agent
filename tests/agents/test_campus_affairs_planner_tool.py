from agents import research_assistant as research_module
from agents import tools as campus_tools
from core.tracing import TraceRecord, bind_trace_record, generate_trace_id


POLICY_WITH_SOURCE = (
    "## 简要结论\n已基于知识库检索。\n\n"
    "## 来源文档\n- exam_policy.md | exam_policy.md::chunk-0002"
)


def test_plan_campus_affair_tool_is_registered_in_default_agent():
    assert campus_tools.plan_campus_affair.name == "plan_campus_affair"
    assert set(campus_tools.plan_campus_affair.args) == {"issue", "deadline", "urgency"}
    assert "plan_campus_affair" in {tool.name for tool in research_module.tools}


def test_exam_absence_planner_uses_policy_and_outputs_action_sections(monkeypatch):
    policy_queries = []

    def fake_policy(query: str) -> str:
        policy_queries.append(query)
        return POLICY_WITH_SOURCE

    monkeypatch.setattr(campus_tools, "query_campus_policy_func", fake_policy)

    result = campus_tools.plan_campus_affair_func(
        "我生病了，可能缺考，如何申请缓考？",
        deadline="考试开始前",
        urgency="紧急",
    )

    assert policy_queries == ["我生病了，可能缺考，如何申请缓考？"]
    assert "`exam_absence`" in result
    assert "## 建议步骤" in result
    assert "## 时间线" in result
    assert "## 政策依据" in result
    assert "高" in result
    assert "exam_policy.md" in result
    assert "exam_policy.md::chunk-0002" in result


def test_scholarship_risk_planner_preserves_policy_basis(monkeypatch):
    monkeypatch.setattr(
        campus_tools,
        "query_campus_policy_func",
        lambda query: (
            "## 来源文档\n- scholarship_policy.md | scholarship_policy.md::chunk-0001"
        ),
    )

    result = campus_tools.plan_campus_affair_func("我挂科了，还能申请奖学金吗？")

    assert "`scholarship_risk`" in result
    assert "## 风险等级\n- 高" in result
    assert "scholarship_policy.md" in result
    assert "scholarship_policy.md::chunk-0001" in result


def test_schedule_conflict_planner_combines_course_and_event_results(monkeypatch):
    calls = []

    def fake_course(**kwargs):
        calls.append(("course", kwargs))
        return "找到课程：数据结构与算法 | 周一 08:30-10:05"

    def fake_event(**kwargs):
        calls.append(("event", kwargs))
        return "找到活动：创新创业比赛宣讲 | 周一 09:00-10:30"

    monkeypatch.setattr(campus_tools, "get_course_schedule_func", fake_course)
    monkeypatch.setattr(campus_tools, "get_campus_events_func", fake_event)

    result = campus_tools.plan_campus_affair_func("比赛报名和课程冲突了，怎么安排？")

    assert "`schedule_conflict`" in result
    assert "## 相关课程 / 活动" in result
    assert "数据结构与算法" in result
    assert "创新创业比赛宣讲" in result
    assert "冲突提醒" in result
    assert calls == [("course", {}), ("event", {"keyword": "比赛"})]


def test_policy_no_answer_does_not_turn_into_a_fabricated_rule(monkeypatch):
    monkeypatch.setattr(
        campus_tools,
        "query_campus_policy_func",
        lambda query: (
            "## 简要结论\n当前知识库中没有找到明确依据。\n\n"
            "## 来源文档\n无"
        ),
    )

    result = campus_tools.plan_campus_affair_func("我因为生病缺考了，应该怎么办？")

    assert "当前知识库中没有找到明确制度依据，建议以学院或教务处最新通知为准。" in result
    assert "当前知识库中没有找到明确依据" in result
    assert "联系电话：" not in result
    assert "办理地点：" not in result
    assert "http://" not in result
    assert "不得将未在来源文档中出现的办理窗口、电话号码、网址或期限视为确定规定" in result


def test_planner_records_composed_tool_metadata_without_external_model(monkeypatch):
    monkeypatch.setattr(campus_tools, "query_campus_policy_func", lambda query: POLICY_WITH_SOURCE)
    record = TraceRecord(trace_id=generate_trace_id(), route="invoke")

    with bind_trace_record(record):
        campus_tools.plan_campus_affair_func("生病缺考怎么申请缓考？")

    planner_call = next(
        call for call in record.tool_calls if call["name"] == "plan_campus_affair"
    )
    assert planner_call["args"]["affair_type"] == "exam_absence"
    assert planner_call["args"]["related_tools"] == ["query_campus_policy"]


def test_general_affair_returns_advisory_plan_without_calling_query_tools(monkeypatch):
    def unexpected_call(*args, **kwargs):
        raise AssertionError("General planning should not invoke a domain tool.")

    monkeypatch.setattr(campus_tools, "query_campus_policy_func", unexpected_call)
    monkeypatch.setattr(campus_tools, "get_course_schedule_func", unexpected_call)
    monkeypatch.setattr(campus_tools, "get_campus_events_func", unexpected_call)

    result = campus_tools.plan_campus_affair_func("我有件校园里的事情想问问")

    assert "`general`" in result
    assert "当前知识库中没有找到明确制度依据" in result
