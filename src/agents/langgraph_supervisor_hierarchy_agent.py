from langchain.agents import create_agent
from langgraph_supervisor import create_supervisor

from agents.langgraph_supervisor_agent import add, multiply, web_search
from core import get_model, settings

model = get_model(settings.DEFAULT_MODEL)


def workflow(chosen_model):
    math_agent = create_agent(
        model=chosen_model,
        tools=[add, multiply],
        name="sub-agent-math_expert",  # Identify the graph node as a sub-agent
        system_prompt="你是校园智能助理中的学习规划与计算专家，负责学时、复习周期、任务拆分、绩点或分数相关计算。每次只使用一个工具。",
    ).with_config(tags=["skip_stream"])

    research_agent = (
        create_supervisor(
            [math_agent],
            model=chosen_model,
            tools=[web_search],
            prompt="你是校园智能助理中的校园信息检索主管，负责讲座、比赛、社团、活动和校园资源信息检索。不要做数学计算，需要计算时交给 math_agent。",
            supervisor_name="supervisor-research_expert",  # Identify the graph node as a supervisor to the math agent
        )
        .compile(
            name="sub-agent-research_expert"
        )  # Identify the graph node as a sub-agent to the main supervisor
        .with_config(tags=["skip_stream"])
    )  # Stream tokens are ignored for sub-agents in the UI

    # Create supervisor workflow
    return create_supervisor(
        [research_agent],
        model=chosen_model,
        prompt=(
            "你是 Campus AI Agent 的分层多 Agent 调度器，负责协调校园信息检索专家及其学习规划计算能力。"
            "对于讲座、比赛、社团、活动、校园资源和需要检索后再规划的问题，使用 research_agent。"
        ),
        add_handoff_back_messages=True,
        # UI now expects this to be True so we don't have to guess when a handoff back occurs
        output_mode="full_history",  # otherwise when reloading conversations, the sub-agents' messages are not included
    )  # default name for supervisor is "supervisor".


langgraph_supervisor_hierarchy_agent = workflow(model).compile()
