from datetime import datetime
from typing import Literal

from langchain_community.tools import DuckDuckGoSearchResults, OpenWeatherMapQueryRun
from langchain_community.utilities import OpenWeatherMapAPIWrapper
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.runnables import RunnableConfig, RunnableLambda, RunnableSerializable
from langgraph.graph import END, MessagesState, StateGraph
from langgraph.managed import RemainingSteps
from langgraph.prebuilt import ToolNode

from agents.campus_prompt import CAMPUS_AI_AGENT_SYSTEM_PROMPT
from agents.safeguard import Safeguard, SafeguardOutput, SafetyAssessment
from agents.tools import calculator, generate_study_plan, get_campus_events, get_course_schedule
from core import get_model, settings


class AgentState(MessagesState, total=False):
    """`total=False` is PEP589 specs.

    documentation: https://typing.readthedocs.io/en/latest/spec/typeddict.html#totality
    """

    safety: SafeguardOutput
    remaining_steps: RemainingSteps


web_search = DuckDuckGoSearchResults(name="WebSearch")
tools = [web_search, calculator, get_course_schedule, get_campus_events, generate_study_plan]

# Add weather tool if API key is set
# Register for an API key at https://openweathermap.org/api/
if settings.OPENWEATHERMAP_API_KEY:
    wrapper = OpenWeatherMapAPIWrapper(
        openweathermap_api_key=settings.OPENWEATHERMAP_API_KEY.get_secret_value()
    )
    tools.append(OpenWeatherMapQueryRun(name="Weather", api_wrapper=wrapper))

current_date = datetime.now().strftime("%B %d, %Y")
instructions = f"""
    {CAMPUS_AI_AGENT_SYSTEM_PROMPT}

    当前日期：{current_date}。

    NOTE: THE USER CAN'T SEE THE TOOL RESPONSE.

    当前已接入的工具包括 get_course_schedule、get_campus_events、generate_study_plan、WebSearch、Calculator，以及在配置 OPENWEATHERMAP_API_KEY 后可用的 Weather。
    当用户询问课程、上课时间、教室、教师、课程安排等问题时，应优先调用 get_course_schedule。
    get_course_schedule 使用本地 mock 课程表数据，不代表真实教务系统数据。
    当用户询问校园活动、讲座、比赛、社团、招聘、工作坊、报名方式等问题时，应优先调用 get_campus_events。
    get_campus_events 使用本地 mock 校园活动数据，不代表真实校园活动平台数据。
    当用户询问学习计划、面试准备、备考安排、本周规划、今日学习安排、实习准备等问题时，应优先调用 generate_study_plan。
    generate_study_plan 使用本地 mock 学生画像和课程表生成规划，不代表学校正式学习或考试安排。

    其他要求：
    - 如使用 WebSearch，请只引用工具返回的链接，并用 Markdown 链接格式给出一到两个必要引用。
    - 如需要计算学习时长、复习周期、任务拆分或分数相关内容，可以使用 Calculator。
    - Calculator 使用 numexpr，但最终回答必须使用学生能理解的自然表达，例如“300 * 200”，不要输出 numexpr 语法说明。
    """


def wrap_model(model: BaseChatModel) -> RunnableSerializable[AgentState, AIMessage]:
    bound_model = model.bind_tools(tools)
    preprocessor = RunnableLambda(
        lambda state: [SystemMessage(content=instructions)] + state["messages"],
        name="StateModifier",
    )
    return preprocessor | bound_model  # type: ignore[return-value]


def format_safety_message(safety: SafeguardOutput) -> AIMessage:
    content = (
        f"This conversation was flagged for unsafe content: {', '.join(safety.unsafe_categories)}"
    )
    return AIMessage(content=content)


async def acall_model(state: AgentState, config: RunnableConfig) -> AgentState:
    m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
    model_runnable = wrap_model(m)
    response = await model_runnable.ainvoke(state, config)

    if state["remaining_steps"] < 2 and response.tool_calls:
        return {
            "messages": [
                AIMessage(
                    id=response.id,
                    content="Sorry, need more steps to process this request.",
                )
            ]
        }
    # We return a list, because this will get added to the existing list
    return {"messages": [response]}


async def safeguard_input(state: AgentState, config: RunnableConfig) -> AgentState:
    safeguard = Safeguard()
    safety_output = await safeguard.ainvoke(state["messages"])
    return {"safety": safety_output, "messages": []}


async def block_unsafe_content(state: AgentState, config: RunnableConfig) -> AgentState:
    safety: SafeguardOutput = state["safety"]
    return {"messages": [format_safety_message(safety)]}


# Define the graph
agent = StateGraph(AgentState)
agent.add_node("model", acall_model)
agent.add_node("tools", ToolNode(tools))
agent.add_node("guard_input", safeguard_input)
agent.add_node("block_unsafe_content", block_unsafe_content)
agent.set_entry_point("guard_input")


# Check for unsafe input and block further processing if found
def check_safety(state: AgentState) -> Literal["unsafe", "safe"]:
    safety: SafeguardOutput = state["safety"]
    match safety.safety_assessment:
        case SafetyAssessment.UNSAFE:
            return "unsafe"
        case _:
            return "safe"


agent.add_conditional_edges(
    "guard_input", check_safety, {"unsafe": "block_unsafe_content", "safe": "model"}
)

# Always END after blocking unsafe content
agent.add_edge("block_unsafe_content", END)

# Always run "model" after "tools"
agent.add_edge("tools", "model")


# After "model", if there are tool calls, run "tools". Otherwise END.
def pending_tool_calls(state: AgentState) -> Literal["tools", "done"]:
    last_message = state["messages"][-1]
    if not isinstance(last_message, AIMessage):
        raise TypeError(f"Expected AIMessage, got {type(last_message)}")
    if last_message.tool_calls:
        return "tools"
    return "done"


agent.add_conditional_edges("model", pending_tool_calls, {"tools": "tools", "done": END})


research_assistant = agent.compile()
