import logging
from typing import Any

from langchain_core.tools import BaseTool, tool
from langgraph.prebuilt import ToolRuntime
from langgraph.store.base import BaseStore

from core.tracing import current_trace_record

USER_MEMORY_NAMESPACE = "user_memory"
USER_MEMORY_KEY = "profile"
_STORE_ERROR_KEY = "_memory_store_error"
logger = logging.getLogger(__name__)


def _record_memory_action(
    action: str,
    success: bool,
    store: BaseStore | None = None,
    error: Exception | None = None,
) -> None:
    record = current_trace_record()
    if record is None:
        return
    record.memory_action = action
    record.memory_action_success = success
    if store is not None:
        record.memory_store_backend = type(store).__name__
    if error is not None:
        record.memory_error = str(error)


async def get_user_memory(store: BaseStore | None, user_id: str | None) -> dict[str, Any] | None:
    """Read only the current user's profile memory, degrading safely on failures."""
    if store is None or not user_id:
        return None
    try:
        item = await store.aget((USER_MEMORY_NAMESPACE, user_id), key=USER_MEMORY_KEY)
        if not item or not isinstance(item.value, dict):
            return None
        return dict(item.value)
    except Exception as error:
        logger.warning("Unable to view long-term memory for current user: %s", error)
        _record_memory_action("view", False, store, error)
        return {_STORE_ERROR_KEY: True}


async def delete_user_memory(store: BaseStore | None, user_id: str | None) -> bool:
    """Delete only the profile memory belonging to the current user."""
    if store is None or not user_id:
        return False
    try:
        await store.adelete((USER_MEMORY_NAMESPACE, user_id), key=USER_MEMORY_KEY)
        return True
    except Exception as error:
        logger.warning("Unable to delete long-term memory for current user: %s", error)
        _record_memory_action("delete", False, store, error)
        return False


def _runtime_user_id(tool_runtime: ToolRuntime) -> str | None:
    configurable = tool_runtime.config.get("configurable", {})
    user_id = configurable.get("user_id") if isinstance(configurable, dict) else None
    return str(user_id) if user_id else None


async def view_user_memory_func(tool_runtime: ToolRuntime) -> str:
    """View the current user's saved long-term preference.

    Call only when the user asks what has been remembered, wants to view their
    memory, or asks for their saved long-term preferences. User identity and
    storage are injected by the running agent, not supplied by the model.
    """
    user_id = _runtime_user_id(tool_runtime)
    if not user_id:
        _record_memory_action("view", False, tool_runtime.store)
        return "无法识别当前用户，暂时不能查看长期记忆。"
    if tool_runtime.store is None:
        _record_memory_action("view", False)
        return "长期记忆存储当前不可用，请稍后再试。"

    memory_record = await get_user_memory(tool_runtime.store, user_id)
    if memory_record and memory_record.get(_STORE_ERROR_KEY):
        return "长期记忆存储当前不可用，请稍后再试。"
    memory = memory_record.get("memory") if memory_record else None
    if not isinstance(memory, str) or not memory.strip():
        _record_memory_action("view", True, tool_runtime.store)
        return "当前没有保存的长期记忆。"

    _record_memory_action("view", True, tool_runtime.store)
    return (
        "# 当前长期记忆\n\n"
        f"- 用户偏好：{memory.strip()}\n\n"
        "说明：这条记忆来自长期 store，可用于后续个性化回答。"
    )


async def delete_user_memory_func(tool_runtime: ToolRuntime) -> str:
    """Delete the current user's saved long-term preference.

    Call only when the user explicitly asks to delete, clear, or forget their
    saved memory or preference. This tool never accepts another user's ID.
    """
    user_id = _runtime_user_id(tool_runtime)
    if not user_id:
        _record_memory_action("delete", False, tool_runtime.store)
        return "无法识别当前用户，暂时不能删除长期记忆。"
    if tool_runtime.store is None:
        _record_memory_action("delete", False)
        return "长期记忆存储当前不可用，请稍后再试。"

    memory_record = await get_user_memory(tool_runtime.store, user_id)
    if memory_record and memory_record.get(_STORE_ERROR_KEY):
        _record_memory_action("delete", False, tool_runtime.store)
        return "长期记忆存储当前不可用，请稍后再试。"
    memory = memory_record.get("memory") if memory_record else None
    if not isinstance(memory, str) or not memory.strip():
        _record_memory_action("delete", True, tool_runtime.store)
        return "当前没有可删除的长期记忆。"

    if not await delete_user_memory(tool_runtime.store, user_id):
        _record_memory_action("delete", False, tool_runtime.store)
        return "长期记忆存储当前不可用，请稍后再试。"

    _record_memory_action("delete", True, tool_runtime.store)
    return "已删除当前用户的长期记忆。"


view_user_memory: BaseTool = tool(view_user_memory_func)
view_user_memory.name = "view_user_memory"
delete_user_memory_tool: BaseTool = tool(delete_user_memory_func)
delete_user_memory_tool.name = "delete_user_memory"
