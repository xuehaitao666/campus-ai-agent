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
from agents.tools import (
    calculator,
    generate_study_plan,
    get_campus_events,
    get_course_schedule,
    query_campus_policy,
)
from core import get_model, settings
from core.model_fallback import ainvoke_with_model_fallback
from core.tracing import TraceSpan, add_token_usage, current_trace_record


class AgentState(MessagesState, total=False):
    """`total=False` is PEP589 specs.

    documentation: https://typing.readthedocs.io/en/latest/spec/typeddict.html#totality
    """

    safety: SafeguardOutput
    remaining_steps: RemainingSteps


web_search = DuckDuckGoSearchResults(name="WebSearch")
tools = [
    web_search,
    calculator,
    get_course_schedule,
    get_campus_events,
    generate_study_plan,
    query_campus_policy,
]

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

    你是 Campus AI Agent 校园智能助理。当前已接入的工具包括：
    - get_course_schedule：本地 mock 课程表查询工具。
    - get_campus_events：本地 mock 校园活动查询工具。
    - generate_study_plan：基于本地 mock 学生画像和课程表的学习计划生成工具。
    - query_campus_policy：基于本地 Chroma 向量库的校园制度 RAG 问答工具。
    - WebSearch、Calculator，以及在配置 OPENWEATHERMAP_API_KEY 后可用的 Weather。

    工具选择规则：
    1. 当用户询问课程安排、上课时间、上课地点、教室、授课教师、某一天是否有课、某个时间段有什么课、某门课在哪里上时，必须优先调用 get_course_schedule。
       - 参数提取：day 对应“周一/周二/今天/明天”等星期信息；time_period 对应“上午/下午/晚上”；course_name 对应课程名关键词，如“数据结构”。
    2. 当用户询问校园活动、讲座、比赛、社团活动、招聘会、工作坊、活动报名方式、活动时间或活动地点时，必须优先调用 get_campus_events。
       - 参数提取：keyword 对应“AI/Agent/实习/比赛/报名”等关键词；date_range 对应“今天/明天/本周/最近”；event_type 对应“讲座/比赛/社团/招聘/工作坊”；target_audience 对应“软件工程/计算机/人工智能”等人群。
    3. 当用户询问学习计划、备考安排、面试准备、今日学习安排、本周学习规划、实习准备，或要求结合课程表安排学习时，必须优先调用 generate_study_plan。
       - 参数提取：goal 对应学习目标；days 对应计划天数；available_time 对应可用时间；focus_topics 对应重点主题，如 LangGraph、FastAPI、RAG、Docker。
    4. 当用户询问通用概念解释，例如 LangGraph、FastAPI、RAG、Docker 是什么，可以直接回答，不必调用工具。
    5. 当用户询问学校制度、奖学金、请假、宿舍规定、考试纪律、缺考处理、学生手册等内容时，必须优先调用 query_campus_policy。
       - 参数提取：query 使用用户完整的校园制度问题。
       - 所有校园制度类回答必须基于 query_campus_policy 从 data/vector_store/campus_policy/ 检索到的结果。
       - 如果工具返回“知识库中未找到明确依据”或“当前依据不足”，必须如实说明，不要编造学校规定。
       - 不要声称查询了真实学校系统，不要编造办理窗口、电话号码、网址或具体时间。

    工具结果回答格式：
    - 课程查询：用清晰条目列出课程名、时间、地点/教室、教师、课程类型、周次、备注。
    - 活动查询：用清晰条目列出活动名、时间、地点、类型、适合人群、主办方、报名方式、简介。
    - 学习计划：用结构化格式列出学习时间、学习主题、实践任务、复盘任务、预期产出，并给出最终建议。
    - 制度问答：按“简要结论、依据说明、办理流程、注意事项、来源文档”组织回答；区分“制度明确规定”和“建议性提醒”，并列出来源文档名称。
    - 如果工具返回没有匹配结果，必须如实说明没有查到相关信息，不要编造课程、活动、制度或学校安排。

    真实性边界：
    - get_course_schedule、get_campus_events、generate_study_plan 都基于本地 mock 数据，不代表真实教务系统、真实校园活动平台或学校正式安排。
    - 如使用 WebSearch，请只引用工具返回的链接，并用 Markdown 链接格式给出一到两个必要引用。
    - 如需要计算学习时长、复习周期、任务拆分或分数相关内容，可以使用 Calculator。Calculator 使用 numexpr，但最终回答必须使用学生能理解的自然表达。
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
    timer = TraceSpan().start()
    try:
        response = await ainvoke_with_model_fallback(state, config, wrap_model, get_model)
    finally:
        record = current_trace_record()
        if record is not None:
            elapsed_ms = timer.stop()
            record.llm_time_ms = (record.llm_time_ms or 0) + elapsed_ms

    record = current_trace_record()
    if record is not None:
        add_token_usage(record, response)
        record.tool_calls.extend(
            {"name": call["name"], "args": call.get("args", {})} for call in response.tool_calls
        )

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
