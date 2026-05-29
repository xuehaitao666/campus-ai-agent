import inspect
import json
import logging
import warnings
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse
from fastapi.routing import APIRoute
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from langchain_core._api import LangChainBetaWarning
from langchain_core.messages import AIMessage, AIMessageChunk, AnyMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langfuse import Langfuse  # type: ignore[import-untyped]
from langfuse.langchain import (
    CallbackHandler,  # type: ignore[import-untyped]
)
from langgraph.types import Command, Interrupt
from langsmith import Client as LangsmithClient
from langsmith import uuid7

from agents import DEFAULT_AGENT, AgentGraph, get_agent, get_all_agent_info, load_agent
from agents.tools import generate_study_plan_func, get_campus_events_func, get_course_schedule_func, query_campus_policy_func
from core import settings
from core.response_templates import (
    format_course_fast_path_response,
    format_event_fast_path_response,
    format_fast_path_error,
    format_study_plan_fast_path_response,
)
from core.router import RouteIntent, parse_course_query, parse_event_query, route_query
from skills.executor import try_skill_fast_path
from core.tracing import (
    TraceRecord,
    TraceSpan,
    add_token_usage,
    bind_trace_record,
    generate_trace_id,
    write_trace_jsonl,
)
from memory import initialize_database, initialize_store
from schema import (
    ChatHistory,
    ChatHistoryInput,
    ChatMessage,
    Feedback,
    FeedbackResponse,
    ServiceMetadata,
    StreamInput,
    UserInput,
)
from service.utils import (
    convert_message_content_to_string,
    langchain_to_chat_message,
    remove_tool_calls,
)

warnings.filterwarnings("ignore", category=LangChainBetaWarning)
logger = logging.getLogger(__name__)


def custom_generate_unique_id(route: APIRoute) -> str:
    """Generate idiomatic operation IDs for OpenAPI client generation."""
    return route.name


def verify_bearer(
    http_auth: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(HTTPBearer(description="Please provide AUTH_SECRET api key.", auto_error=False)),
    ],
) -> None:
    if not settings.AUTH_SECRET:
        return
    auth_secret = settings.AUTH_SECRET.get_secret_value()
    if not http_auth or http_auth.credentials != auth_secret:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Configurable lifespan that initializes the appropriate database checkpointer, store,
    and agents with async loading - for example for starting up MCP clients.
    """
    try:
        # Initialize both checkpointer (for short-term memory) and store (for long-term memory)
        async with initialize_database() as saver, initialize_store() as store:
            # Set up both components
            if hasattr(saver, "setup"):  # ignore: union-attr
                await saver.setup()
            # Only setup store for Postgres as InMemoryStore doesn't need setup
            if hasattr(store, "setup"):  # ignore: union-attr
                await store.setup()

            # Configure agents with both memory components and async loading
            agents = get_all_agent_info()
            for a in agents:
                try:
                    await load_agent(a.key)
                    logger.info(f"Agent loaded: {a.key}")
                except Exception as e:
                    logger.error(f"Failed to load agent {a.key}: {e}")
                    # Continue with other agents rather than failing startup

                agent = get_agent(a.key)
                # Set checkpointer for thread-scoped memory (conversation history)
                agent.checkpointer = saver
                # Set store for long-term memory (cross-conversation knowledge)
                agent.store = store
            yield
    except Exception as e:
        logger.error(f"Error during database/store/agents initialization: {e}")
        raise


app = FastAPI(lifespan=lifespan, generate_unique_id_function=custom_generate_unique_id)
router = APIRouter(dependencies=[Depends(verify_bearer)])


@router.get("/info")
async def info() -> ServiceMetadata:
    models = list(settings.AVAILABLE_MODELS)
    models.sort()
    return ServiceMetadata(
        agents=get_all_agent_info(),
        models=models,
        default_agent=DEFAULT_AGENT,
        default_model=settings.DEFAULT_MODEL,
    )


def _model_name(user_input: UserInput) -> str | None:
    model = user_input.model or settings.DEFAULT_MODEL
    return getattr(model, "value", str(model)) if model is not None else None


def _new_request_trace(user_input: UserInput, agent_id: str, route: str) -> TraceRecord:
    return TraceRecord(
        trace_id=generate_trace_id(),
        thread_id=user_input.thread_id,
        user_id=user_input.user_id,
        agent_id=agent_id,
        model_name=_model_name(user_input),
        query=user_input.message,
        route=route,
    )


def _update_trace_request_ids(
    record: TraceRecord,
    kwargs: dict[str, Any],
    run_id: UUID,
) -> None:
    configurable = kwargs["config"]["configurable"]
    record.run_id = str(run_id)
    record.thread_id = configurable["thread_id"]
    record.user_id = configurable["user_id"]


def _write_trace_safely(record: TraceRecord) -> None:
    try:
        write_trace_jsonl(record)
    except Exception as e:
        logger.warning(f"Unable to write trace record: {e}")


def _present_fields(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if value not in (None, "")}


def _trace_custom_data(record: TraceRecord) -> dict[str, Any]:
    custom_data: dict[str, Any] = {}
    if record.retrieved_docs:
        retrieved_docs = [
            _present_fields(
                {
                    "source": (
                        document.get("source") if document.get("source") != "unknown" else None
                    ),
                    "chunk_id": document.get("chunk_id"),
                    "section": document.get("section"),
                    "heading_path": document.get("heading_path"),
                    "policy_type": document.get("policy_type"),
                    "retrieval_source": document.get("retrieval_source"),
                    "hybrid_score": document.get("hybrid_score"),
                }
            )
            for document in record.retrieved_docs
        ]
        custom_data["retrieved_docs"] = retrieved_docs
        custom_data["source_citations"] = [
            _present_fields(
                {
                    "source": (
                        document.get("source") if document.get("source") != "unknown" else None
                    ),
                    "chunk_id": document.get("chunk_id"),
                    "section": document.get("section"),
                }
            )
            for document in record.retrieved_docs
        ]

    metrics = _present_fields(
        {
            "total_latency_ms": record.total_latency_ms,
            "llm_time_ms": record.llm_time_ms,
            "tool_time_ms": record.tool_time_ms,
            "retrieval_time_ms": record.retrieval_time_ms,
            "prompt_tokens": record.prompt_tokens,
            "completion_tokens": record.completion_tokens,
            "total_tokens": record.total_tokens,
            "context_docs_count": record.context_docs_count,
            "context_chars": record.context_chars,
            "estimated_context_tokens": record.estimated_context_tokens,
            "dropped_context_docs_count": record.dropped_context_docs_count,
            "history_message_count": record.history_message_count,
            "trimmed_message_count": record.trimmed_message_count,
        }
    )
    if metrics:
        custom_data["metrics"] = metrics

    if record.tool_calls:
        custom_data["tool_execution"] = [
            _present_fields(
                {
                    "tool_name": call.get("name"),
                    "status": "error" if record.error_message else "success",
                    "latency_ms": record.tool_time_ms,
                    "error": record.error_message,
                }
            )
            for call in record.tool_calls
        ]

    if (
        record.primary_model
        or record.fallback_model
        or record.fallback_triggered
        or record.model_error
    ):
        custom_data["model_fallback"] = _present_fields(
            {
                "primary_model": record.primary_model,
                "fallback_model": record.fallback_model,
                "fallback_triggered": record.fallback_triggered,
                "model_error": record.model_error,
            }
        )
    return custom_data


def _add_trace_custom_data(message: ChatMessage, record: TraceRecord) -> ChatMessage:
    trace_data = _trace_custom_data(record)
    for key, value in trace_data.items():
        message.custom_data.setdefault(key, value)
    return message


def _maybe_handle_course_fast_path(
    user_input: UserInput,
    trace_record: TraceRecord,
) -> ChatMessage | None:
    decision = route_query(user_input.message)
    if decision.intent != RouteIntent.COURSE:
        return None

    parameters = parse_course_query(user_input.message)
    if not any(parameters.values()):
        return None
    if (
        any(relative_day in user_input.message for relative_day in ("今天", "明天"))
        and not parameters["day"]
    ):
        return None

    run_id = uuid7()
    trace_record.run_id = str(run_id)
    trace_record.thread_id = user_input.thread_id or str(uuid4())
    trace_record.user_id = user_input.user_id or str(uuid4())
    trace_record.route = "course_schedule_fast_path"
    trace_record.tool_calls = [{"name": "get_course_schedule", "args": parameters}]
    trace_record.llm_time_ms = 0
    trace_record.prompt_tokens = 0
    trace_record.completion_tokens = 0
    trace_record.total_tokens = 0

    try:
        with TraceSpan() as tool_timer:
            tool_result = get_course_schedule_func(**parameters)
        content = format_course_fast_path_response(user_input.message, parameters, tool_result)
    except Exception as error:
        trace_record.error_message = str(error)
        content = format_fast_path_error("course", str(error))
    trace_record.tool_time_ms = tool_timer.elapsed_ms

    return ChatMessage(type="ai", content=content, run_id=str(run_id))


def _maybe_handle_event_fast_path(
    user_input: UserInput,
    trace_record: TraceRecord,
) -> ChatMessage | None:
    decision = route_query(user_input.message)
    if decision.intent != RouteIntent.EVENT:
        return None

    parameters = parse_event_query(user_input.message)
    if not any(parameters.values()):
        return None

    run_id = uuid7()
    trace_record.run_id = str(run_id)
    trace_record.thread_id = user_input.thread_id or str(uuid4())
    trace_record.user_id = user_input.user_id or str(uuid4())
    trace_record.route = "campus_event_fast_path"
    trace_record.tool_calls = [{"name": "get_campus_events", "args": parameters}]
    trace_record.llm_time_ms = 0
    trace_record.prompt_tokens = 0
    trace_record.completion_tokens = 0
    trace_record.total_tokens = 0

    try:
        with TraceSpan() as tool_timer:
            tool_result = get_campus_events_func(**parameters)
        content = format_event_fast_path_response(user_input.message, parameters, tool_result)
    except Exception as error:
        trace_record.error_message = str(error)
        content = format_fast_path_error("event", str(error))
    trace_record.tool_time_ms = tool_timer.elapsed_ms

    return ChatMessage(type="ai", content=content, run_id=str(run_id))


def _maybe_handle_policy_qa_fast_path(
    user_input: UserInput,
    trace_record: TraceRecord,
) -> ChatMessage | None:
    decision = route_query(user_input.message)
    if decision.intent != RouteIntent.POLICY:
        return None

    run_id = uuid7()
    trace_record.run_id = str(run_id)
    trace_record.thread_id = user_input.thread_id or str(uuid4())
    trace_record.user_id = user_input.user_id or str(uuid4())
    trace_record.route = "campus_policy_fast_path"
    trace_record.tool_calls = [{"name": "query_campus_policy", "args": {"query": user_input.message}}]
    trace_record.llm_time_ms = 0
    trace_record.prompt_tokens = 0
    trace_record.completion_tokens = 0
    trace_record.total_tokens = 0

    with TraceSpan() as tool_timer:
        content = query_campus_policy_func(query=user_input.message)
    trace_record.tool_time_ms = tool_timer.elapsed_ms
    return ChatMessage(type="ai", content=content, run_id=str(run_id))

def _parse_study_plan_fast_path_params(query: str) -> dict[str, object]:
    """Extract study-plan parameters from a user query using conservative rules.

    Returns a dict with keys *goal*, *days*, *available_time*, and
    *focus_topics*.  Values that cannot be extracted are None.
    """
    import re

    params: dict[str, object] = {
        "goal": None,
        "days": None,
        "available_time": None,
        "focus_topics": None,
    }

    # -- days ----------------------------------------------------------------
    m = re.search(r"(\d+)\s*天", query)
    if m:
        params["days"] = int(m.group(1))
    else:
        cn_map = {"七": 7, "一": 1, "两": 2, "三": 3, "五": 5, "十": 10}
        for cn, val in cn_map.items():
            if f"{cn}天" in query:
                params["days"] = val
                break

    # -- goal ----------------------------------------------------------------
    goal_patterns = [
        r"制定(?:一份|一个)?(.+?)(?:的)?(?:学习计划|学习路线|备考计划|复习计划)",
        r"准备(.+?)(?:面试|考试)",
        r"(.+?)备考",
        r"(.+?)复习",
    ]
    for pat in goal_patterns:
        m = re.search(pat, query)
        if m:
            raw = m.group(1).strip("的，,、 ")
            if raw and len(raw) >= 2:
                params["goal"] = raw
            break

    # -- available_time -----------------------------------------------------
    time_keywords = [
        "今天上午", "今天下午", "今天晚上", "明天",
        "周末", "上午", "下午", "晚上",
    ]
    for kw in time_keywords:
        if kw in query:
            params["available_time"] = kw
            break

    # -- focus_topics -------------------------------------------------------
    tech_keywords = [
        "AI Agent", "LangGraph", "LangChain", "RAG",
        "FastAPI", "Streamlit", "Docker", "Python",
        "数据结构", "算法", "数据库", "操作系统",
    ]
    found = [kw for kw in tech_keywords if kw.lower() in query.lower()]
    if found:
        params["focus_topics"] = ", ".join(found)

    return params


def _maybe_handle_study_plan_fast_path(
    user_input: UserInput,
    trace_record: TraceRecord,
) -> ChatMessage | None:
    decision = route_query(user_input.message)
    if decision.intent != RouteIntent.STUDY_PLAN:
        return None

    params = _parse_study_plan_fast_path_params(user_input.message)
    if not any(params.values()):
        return None

    run_id = uuid7()
    trace_record.run_id = str(run_id)
    trace_record.thread_id = user_input.thread_id or str(uuid4())
    trace_record.user_id = user_input.user_id or str(uuid4())
    trace_record.route = "study_plan_fast_path"
    trace_record.tool_calls = [{"name": "generate_study_plan", "args": params}]
    trace_record.llm_time_ms = 0
    trace_record.prompt_tokens = 0
    trace_record.completion_tokens = 0
    trace_record.total_tokens = 0

    with TraceSpan() as tool_timer:
        plan_json = generate_study_plan_func(
            goal=params["goal"],                   # type: ignore[arg-type]
            days=params["days"] or 7,              # type: ignore[arg-type]
            available_time=params["available_time"],  # type: ignore[arg-type]
            focus_topics=params["focus_topics"],      # type: ignore[arg-type]
        )
    trace_record.tool_time_ms = tool_timer.elapsed_ms

    content = format_study_plan_fast_path_response(plan_json)
    return ChatMessage(type="ai", content=content, run_id=str(run_id))

FAST_PATH_HANDLERS = {
    "_maybe_handle_course_fast_path": _maybe_handle_course_fast_path,
    "_maybe_handle_event_fast_path": _maybe_handle_event_fast_path,
    "_maybe_handle_policy_qa_fast_path": _maybe_handle_policy_qa_fast_path,
    "_maybe_handle_study_plan_fast_path": _maybe_handle_study_plan_fast_path,
}

async def _handle_input(
    user_input: UserInput,
    agent: AgentGraph,
    trace_id: str | None = None,
) -> tuple[dict[str, Any], UUID]:
    """
    Parse user input and handle any required interrupt resumption.
    Returns kwargs for agent invocation and the run_id.
    """
    run_id = uuid7()
    thread_id = user_input.thread_id or str(uuid4())
    user_id = user_input.user_id or str(uuid4())

    configurable = {"thread_id": thread_id, "user_id": user_id}
    if trace_id is not None:
        configurable["trace_id"] = trace_id
    if user_input.model is not None:
        configurable["model"] = user_input.model

    callbacks: list[Any] = []
    if settings.LANGFUSE_TRACING:
        # Initialize Langfuse CallbackHandler for Langchain (tracing)
        langfuse_handler = CallbackHandler()

        callbacks.append(langfuse_handler)

    if user_input.agent_config:
        # Check for reserved keys (including 'model' even if not in configurable)
        reserved_keys = {"thread_id", "user_id", "model", "trace_id"}
        if overlap := reserved_keys & user_input.agent_config.keys():
            raise HTTPException(
                status_code=422,
                detail=f"agent_config contains reserved keys: {overlap}",
            )
        configurable.update(user_input.agent_config)

    config = RunnableConfig(
        configurable=configurable,
        run_id=run_id,
        callbacks=callbacks,
    )

    # Check for interrupts that need to be resumed
    state = await agent.aget_state(config=config)
    interrupted_tasks = [
        task for task in state.tasks if hasattr(task, "interrupts") and task.interrupts
    ]

    input: Command | dict[str, Any]
    if interrupted_tasks:
        # assume user input is response to resume agent execution from interrupt
        input = Command(resume=user_input.message)
    else:
        input = {"messages": [HumanMessage(content=user_input.message)]}

    kwargs = {
        "input": input,
        "config": config,
    }

    return kwargs, run_id


@router.post("/{agent_id}/invoke", operation_id="invoke_with_agent_id")
@router.post("/invoke")
async def invoke(user_input: UserInput, agent_id: str = DEFAULT_AGENT) -> ChatMessage:
    """
    Invoke an agent with user input to retrieve a final response.

    If agent_id is not provided, the default agent will be used.
    Use thread_id to persist and continue a multi-turn conversation. run_id kwarg
    is also attached to messages for recording feedback.
    Use user_id to persist and continue a conversation across multiple threads.
    """
    # NOTE: Currently this only returns the last message or interrupt.
    # In the case of an agent outputting multiple AIMessages (such as the background step
    # in interrupt-agent, or a tool step in research-assistant), it's omitted. Arguably,
    # you'd want to include it. You could update the API to return a list of ChatMessages
    # in that case.
    trace_record = _new_request_trace(user_input, agent_id, "invoke")
    timer = TraceSpan().start()
    try:
        if output := try_skill_fast_path(user_input, trace_record, FAST_PATH_HANDLERS):
            trace_record.total_latency_ms = timer.stop()
            _add_trace_custom_data(output, trace_record)
            return output
        agent: AgentGraph = get_agent(agent_id)
        kwargs, run_id = await _handle_input(user_input, agent, trace_record.trace_id)
        _update_trace_request_ids(trace_record, kwargs, run_id)
        with bind_trace_record(trace_record):
            response_events: list[tuple[str, Any]] = await agent.ainvoke(**kwargs, stream_mode=["updates", "values"])  # type: ignore # fmt: skip
        response_type, response = response_events[-1]
        if response_type == "values":
            # Normal response, the agent completed successfully
            final_message = response["messages"][-1]
            add_token_usage(trace_record, final_message, accumulate=False)
            output = langchain_to_chat_message(final_message)
        elif response_type == "updates" and "__interrupt__" in response:
            # The last thing to occur was an interrupt
            # Return the value of the first interrupt as an AIMessage
            output = langchain_to_chat_message(
                AIMessage(content=response["__interrupt__"][0].value)
            )
        else:
            raise ValueError(f"Unexpected response type: {response_type}")

        output.run_id = str(run_id)
        trace_record.total_latency_ms = timer.stop()
        _add_trace_custom_data(output, trace_record)
        return output
    except HTTPException as e:
        trace_record.error_message = str(e.detail)
        raise
    except Exception as e:
        trace_record.error_message = str(e)
        logger.error(f"An exception occurred: {e}")
        raise HTTPException(status_code=500, detail="Unexpected error")
    finally:
        trace_record.total_latency_ms = timer.stop()
        _write_trace_safely(trace_record)


async def message_generator(
    user_input: StreamInput, agent_id: str = DEFAULT_AGENT
) -> AsyncGenerator[str, None]:
    """
    Generate a stream of messages from the agent.

    This is the workhorse method for the /stream endpoint.
    """
    trace_record = _new_request_trace(user_input, agent_id, "stream")
    timer = TraceSpan().start()
    try:
        if output := try_skill_fast_path(user_input, trace_record, FAST_PATH_HANDLERS):
            trace_record.total_latency_ms = timer.stop()
            _add_trace_custom_data(output, trace_record)
            yield f"data: {json.dumps({'type': 'message', 'content': output.model_dump()})}\n\n"
            return
        agent: AgentGraph = get_agent(agent_id)
        kwargs, run_id = await _handle_input(user_input, agent, trace_record.trace_id)
        _update_trace_request_ids(trace_record, kwargs, run_id)
        # Process streamed events from the graph and yield messages over the SSE stream.
        with bind_trace_record(trace_record):
            async for stream_event in agent.astream(
                **kwargs, stream_mode=["updates", "messages", "custom"], subgraphs=True
            ):
                if not isinstance(stream_event, tuple):
                    continue
                # Handle different stream event structures based on subgraphs
                if len(stream_event) == 3:
                    # With subgraphs=True: (node_path, stream_mode, event)
                    _, stream_mode, event = stream_event
                else:
                    # Without subgraphs: (stream_mode, event)
                    stream_mode, event = stream_event
                new_messages = []
                if stream_mode == "updates":
                    for node, updates in event.items():
                        # A simple approach to handle agent interrupts.
                        # In a more sophisticated implementation, we could add
                        # some structured ChatMessage type to return the interrupt value.
                        if node == "__interrupt__":
                            interrupt: Interrupt
                            for interrupt in updates:
                                new_messages.append(AIMessage(content=interrupt.value))
                            continue
                        updates = updates or {}
                        update_messages = updates.get("messages", [])
                        # special cases for using langgraph-supervisor library
                        if "supervisor" in node or "sub-agent" in node:
                            # the only tools that come from the actual agent are the handoff and handback tools
                            if isinstance(update_messages[-1], ToolMessage):
                                if "sub-agent" in node and len(update_messages) > 1:
                                    # If this is a sub-agent, we want to keep the last 2 messages - the handback tool, and it's result
                                    update_messages = update_messages[-2:]
                                else:
                                    # If this is a supervisor, we want to keep the last message only - the handoff result. The tool comes from the 'agent' node.
                                    update_messages = [update_messages[-1]]
                            else:
                                update_messages = []
                        new_messages.extend(update_messages)

                if stream_mode == "custom":
                    new_messages = [event]

                # LangGraph streaming may emit tuples: (field_name, field_value)
                # e.g. ('content', <str>), ('tool_calls', [ToolCall,...]), ('additional_kwargs', {...}), etc.
                # We accumulate only supported fields into `parts` and skip unsupported metadata.
                # More info at: https://langchain-ai.github.io/langgraph/cloud/how-tos/stream_messages/
                processed_messages = []
                current_message: dict[str, Any] = {}
                for message in new_messages:
                    if isinstance(message, tuple):
                        key, value = message
                        # Store parts in temporary dict
                        current_message[key] = value
                    else:
                        # Add complete message if we have one in progress
                        if current_message:
                            processed_messages.append(_create_ai_message(current_message))
                            current_message = {}
                        processed_messages.append(message)

                # Add any remaining message parts
                if current_message:
                    processed_messages.append(_create_ai_message(current_message))

                for message in processed_messages:
                    try:
                        add_token_usage(trace_record, message, accumulate=False)
                        chat_message = langchain_to_chat_message(message)
                        chat_message.run_id = str(run_id)
                        _add_trace_custom_data(chat_message, trace_record)
                    except Exception as e:
                        logger.error(f"Error parsing message: {e}")
                        yield f"data: {json.dumps({'type': 'error', 'content': 'Unexpected error'})}\n\n"
                        continue
                    # LangGraph re-sends the input message, which feels weird, so drop it
                    if chat_message.type == "human" and chat_message.content == user_input.message:
                        continue
                    yield f"data: {json.dumps({'type': 'message', 'content': chat_message.model_dump()})}\n\n"

                if stream_mode == "messages":
                    if not user_input.stream_tokens:
                        continue
                    msg, metadata = event
                    if "skip_stream" in metadata.get("tags", []):
                        continue
                    # For some reason, astream("messages") causes non-LLM nodes to send extra messages.
                    # Drop them.
                    if not isinstance(msg, AIMessageChunk):
                        continue
                    content = remove_tool_calls(msg.content)
                    if content:
                        # Empty content in the context of OpenAI usually means
                        # that the model is asking for a tool to be invoked.
                        # So we only print non-empty content.
                        yield f"data: {json.dumps({'type': 'token', 'content': convert_message_content_to_string(content)})}\n\n"
    except Exception as e:
        trace_record.error_message = str(e)
        logger.error(f"Error in message generator: {e}")
        yield f"data: {json.dumps({'type': 'error', 'content': 'Internal server error'})}\n\n"
    finally:
        trace_record.total_latency_ms = timer.stop()
        _write_trace_safely(trace_record)
        yield "data: [DONE]\n\n"


def _create_ai_message(parts: dict) -> AIMessage:
    sig = inspect.signature(AIMessage)
    valid_keys = set(sig.parameters)
    filtered = {k: v for k, v in parts.items() if k in valid_keys}
    return AIMessage(**filtered)


def _sse_response_example() -> dict[int | str, Any]:
    return {
        status.HTTP_200_OK: {
            "description": "Server Sent Event Response",
            "content": {
                "text/event-stream": {
                    "example": "data: {'type': 'token', 'content': 'Hello'}\n\ndata: {'type': 'token', 'content': ' World'}\n\ndata: [DONE]\n\n",
                    "schema": {"type": "string"},
                }
            },
        }
    }


@router.post(
    "/{agent_id}/stream",
    response_class=StreamingResponse,
    responses=_sse_response_example(),
    operation_id="stream_with_agent_id",
)
@router.post("/stream", response_class=StreamingResponse, responses=_sse_response_example())
async def stream(user_input: StreamInput, agent_id: str = DEFAULT_AGENT) -> StreamingResponse:
    """
    Stream an agent's response to a user input, including intermediate messages and tokens.

    If agent_id is not provided, the default agent will be used.
    Use thread_id to persist and continue a multi-turn conversation. run_id kwarg
    is also attached to all messages for recording feedback.
    Use user_id to persist and continue a conversation across multiple threads.

    Set `stream_tokens=false` to return intermediate messages but not token-by-token.
    """
    return StreamingResponse(
        message_generator(user_input, agent_id),
        media_type="text/event-stream",
    )


@router.post("/feedback")
async def feedback(feedback: Feedback) -> FeedbackResponse:
    """
    Record feedback for a run to LangSmith.

    This is a simple wrapper for the LangSmith create_feedback API, so the
    credentials can be stored and managed in the service rather than the client.
    See: https://api.smith.langchain.com/redoc#tag/feedback/operation/create_feedback_api_v1_feedback_post
    """
    client = LangsmithClient()
    kwargs = feedback.kwargs or {}
    client.create_feedback(
        run_id=feedback.run_id,
        key=feedback.key,
        score=feedback.score,
        **kwargs,
    )
    return FeedbackResponse()


@router.post("/history")
async def history(input: ChatHistoryInput) -> ChatHistory:
    """
    Get chat history.
    """
    agent_id = input.agent_id or DEFAULT_AGENT
    try:
        agent: AgentGraph = get_agent(agent_id)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")

    try:
        state_snapshot = await agent.aget_state(
            config=RunnableConfig(configurable={"thread_id": input.thread_id})
        )
        messages: list[AnyMessage] = state_snapshot.values["messages"]
        if not input.include_tools:
            messages = [
                message
                for message in messages
                if not isinstance(message, ToolMessage)
                and not (isinstance(message, AIMessage) and message.tool_calls)
            ]
        messages = messages[-input.limit :]
        chat_messages: list[ChatMessage] = [langchain_to_chat_message(m) for m in messages]
        return ChatHistory(messages=chat_messages)
    except Exception as e:
        logger.error(f"An exception occurred: {e}")
        raise HTTPException(status_code=500, detail="Unexpected error")


@app.get("/health")
async def health_check():
    """Health check endpoint."""

    health_status = {"status": "ok"}

    if settings.LANGFUSE_TRACING:
        try:
            langfuse = Langfuse()
            health_status["langfuse"] = "connected" if langfuse.auth_check() else "disconnected"
        except Exception as e:
            logger.error(f"Langfuse connection error: {e}")
            health_status["langfuse"] = "disconnected"

    return health_status


app.include_router(router)
