import pytest

from core.router import RouteIntent, route_query


@pytest.mark.parametrize(
    ("query", "expected_intent"),
    [
        ("我周一上午有什么课？", RouteIntent.COURSE),
        ("数据结构课在哪里上？", RouteIntent.COURSE),
        ("这周有什么 AI 相关讲座？", RouteIntent.EVENT),
        ("最近有没有比赛可以报名？", RouteIntent.EVENT),
        ("帮我制定一份 7 天 AI Agent 学习计划", RouteIntent.STUDY_PLAN),
        ("我明天下午没课，帮我安排学习", RouteIntent.STUDY_PLAN),
        ("挂科了还能申请奖学金吗？", RouteIntent.POLICY),
        ("宿舍晚归会怎么处理？", RouteIntent.POLICY),
        ("考试作弊有什么后果？", RouteIntent.POLICY),
        ("你好，你能做什么？", RouteIntent.GENERAL),
    ],
)
def test_route_query_classifies_supported_intents(query, expected_intent):
    decision = route_query(query)

    assert decision.intent == expected_intent
    assert decision.matched_keywords
    assert 0 <= decision.confidence <= 1
    assert decision.route_source == "rule"
    assert decision.reason


@pytest.mark.parametrize("query", ["什么是 LangGraph？", "AI 是什么？"])
def test_route_query_does_not_over_route_unclassified_technical_questions(query):
    decision = route_query(query)

    assert decision.intent in {RouteIntent.UNKNOWN, RouteIntent.GENERAL}
    assert decision.intent not in {
        RouteIntent.POLICY,
        RouteIntent.EVENT,
        RouteIntent.COURSE,
    }
    assert 0 <= decision.confidence <= 1
    assert decision.route_source == "rule"


@pytest.mark.parametrize("query", ["", "   ", "\n\t"])
def test_route_query_returns_unknown_for_blank_input(query):
    decision = route_query(query)

    assert decision.intent == RouteIntent.UNKNOWN
    assert decision.matched_keywords == []
    assert decision.confidence == 0
    assert decision.route_source == "rule"
