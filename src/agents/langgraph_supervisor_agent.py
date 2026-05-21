from typing import Any

from langchain.agents import create_agent
from langgraph_supervisor import create_supervisor

from core import get_model, settings

model = get_model(settings.DEFAULT_MODEL)


def add(a: float, b: float) -> float:
    """Add two numbers."""
    return a + b


def multiply(a: float, b: float) -> float:
    """Multiply two numbers."""
    return a * b


def web_search(query: str) -> str:
    """Search the web for information."""
    return (
        "以下是校园场景示例检索结果：\n"
        "1. **AI Agent 技术分享会**：周三 19:00，软件学院报告厅。\n"
        "2. **大学生创新创业比赛宣讲**：周四 15:00，图书馆路演厅。\n"
        "3. **软件工程社团项目招新**：周五 18:30，学生活动中心。"
    )


math_agent: Any = create_agent(
    model=model,
    tools=[add, multiply],
    name="sub-agent-math_expert",
    system_prompt="你是校园智能助理中的学习规划与计算专家，负责学时、复习周期、任务拆分、绩点或分数相关计算。每次只使用一个工具。",
).with_config(tags=["skip_stream"])

research_agent: Any = create_agent(
    model=model,
    tools=[web_search],
    name="sub-agent-research_expert",
    system_prompt="你是校园智能助理中的校园信息检索专家，负责查找讲座、比赛、社团、活动和校园资源信息。不要做数学计算。",
).with_config(tags=["skip_stream"])


# Create supervisor workflow
workflow = create_supervisor(
    [research_agent, math_agent],
    model=model,
    prompt=(
        "你是 Campus AI Agent 的多 Agent 调度器，负责在校园信息检索专家和学习规划计算专家之间分配任务。"
        "对于讲座、比赛、社团、活动和校园资源问题，使用 research_agent。"
        "对于学习计划、学时安排、任务拆分、绩点或分数计算问题，使用 math_agent。"
    ),
    add_handoff_back_messages=True,
    # UI now expects this to be True so we don't have to guess when a handoff back occurs
    output_mode="full_history",  # otherwise when reloading conversations, the sub-agents' messages are not included
)

langgraph_supervisor_agent = workflow.compile()
