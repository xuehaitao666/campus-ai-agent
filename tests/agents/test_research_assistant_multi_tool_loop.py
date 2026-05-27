import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableLambda

from agents import research_assistant as research_module
from agents.safeguard import SafeguardOutput, SafetyAssessment


class SafeSafeguard:
    async def ainvoke(self, messages):
        return SafeguardOutput(safety_assessment=SafetyAssessment.SAFE)


class TwoToolLoopModel:
    def __init__(self, empty_event_result: bool = False):
        self.calls = []
        self.empty_event_result = empty_event_result

    def bind_tools(self, available_tools):
        async def invoke(messages):
            self.calls.append(messages)
            tool_messages = [message for message in messages if isinstance(message, ToolMessage)]
            if len(tool_messages) == 0:
                return AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "get_course_schedule",
                            "args": {"day": "周一"},
                            "id": "call-course-1",
                            "type": "tool_call",
                        }
                    ],
                )
            if len(tool_messages) == 1:
                keyword = "绝对不存在的活动" if self.empty_event_result else None
                return AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "get_campus_events",
                            "args": {"keyword": keyword},
                            "id": "call-event-1",
                            "type": "tool_call",
                        }
                    ],
                )
            return AIMessage(content="已基于课程和活动查询结果完成汇总。")

        return RunnableLambda(invoke)


@pytest.mark.asyncio
async def test_research_assistant_cycles_through_two_tools_before_final_answer(monkeypatch):
    model = TwoToolLoopModel()
    monkeypatch.setattr(research_module, "Safeguard", SafeSafeguard)
    monkeypatch.setattr(research_module, "get_model", lambda model_name: model)

    result = await research_module.research_assistant.ainvoke(
        {"messages": [HumanMessage(content="帮我查看周一课程和校园活动。")]},
        config={"configurable": {}},
    )

    tool_messages = [
        message for message in result["messages"] if isinstance(message, ToolMessage)
    ]

    assert len(model.calls) == 3
    assert [message.name for message in tool_messages] == [
        "get_course_schedule",
        "get_campus_events",
    ]
    assert [message.tool_call_id for message in tool_messages] == [
        "call-course-1",
        "call-event-1",
    ]
    assert "数据结构与算法" in tool_messages[0].content
    assert result["messages"][-1].content == "已基于课程和活动查询结果完成汇总。"
    assert any(isinstance(message, ToolMessage) for message in model.calls[1])
    assert len(
        [message for message in model.calls[2] if isinstance(message, ToolMessage)]
    ) == 2


@pytest.mark.asyncio
async def test_research_assistant_continues_after_second_tool_returns_no_result(monkeypatch):
    model = TwoToolLoopModel(empty_event_result=True)
    monkeypatch.setattr(research_module, "Safeguard", SafeSafeguard)
    monkeypatch.setattr(research_module, "get_model", lambda model_name: model)

    result = await research_module.research_assistant.ainvoke(
        {"messages": [HumanMessage(content="查课程，并看看不存在的活动。")]},
        config={"configurable": {}},
    )

    tool_messages = [
        message for message in result["messages"] if isinstance(message, ToolMessage)
    ]

    assert len(tool_messages) == 2
    assert "没有找到符合条件的校园活动" in tool_messages[1].content
    assert result["messages"][-1].content == "已基于课程和活动查询结果完成汇总。"
