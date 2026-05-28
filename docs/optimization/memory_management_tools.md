# Memory Management Tools

## 1. Why Memory Needs User Control

`research-assistant` 已能在用户明确提出“记住我的偏好”时，通过 LangGraph `store` 保存跨会话长期记忆。长期记忆可以让回答更连续，但也必须给用户最基本的知情与撤回能力。因此新增两个最小管理工具：

- `view_user_memory`：查看当前用户已保存的长期偏好；
- `delete_user_memory`：删除当前用户已保存的长期偏好。

## 2. Storage Contract

工具与原长期记忆写入链路遵守相同的存储契约：

| Field | Value |
| --- | --- |
| namespace | `("user_memory", user_id)` |
| key | `"profile"` |
| value | 当前保存的短偏好记录 |

删除使用 LangGraph Store 原生异步删除接口 `store.adelete(namespace, key="profile")`，不以空内容覆盖旧记录。

## 3. Runtime Identity and Privacy Boundary

两个工具没有向模型暴露 `user_id` 参数。工具使用 LangGraph `ToolRuntime` 自动注入：

- `tool_runtime.config["configurable"]["user_id"]`：当前请求身份；
- `tool_runtime.store`：当前 Agent 运行时的长期 store。

因此工具只能操作当前请求关联用户的 namespace，不能通过参数指定另一个用户。若请求没有 `user_id`、store 未初始化，或 store 操作异常，工具仅返回友好提示，不输出底层 traceback。

## 4. Behavior

### `view_user_memory`

- 有记忆：返回当前长期记忆及其用途说明；
- 无记忆：返回“当前没有保存的长期记忆。”；
- 无身份或存储不可用：返回可读错误提示。

### `delete_user_memory`

- 有记忆且删除成功：返回“已删除当前用户的长期记忆。”；
- 无记忆：返回“当前没有可删除的长期记忆。”；
- 无身份或存储不可用：返回可读错误提示。

为避免查看或删除请求反过来覆盖已有记忆，`你记住了我什么`、`删除我的记忆`、`不要再记住` 等管理指令会被排除在自动记忆写入候选之外。

## 5. Checkpointer Versus Store

- `checkpointer/history` 基于 `thread_id` 保存当前会话内的短期多轮状态；
- `store` 基于 `user_id` 保存跨 thread 可复用的长期偏好；
- memory 管理工具只管理 `store` 中当前用户的长期偏好，不删除聊天历史。

## 6. Trace

现有 Trace 继续记录 `memory_store_backend` 与 `memory_error`，并新增：

- `memory_action`: `view` 或 `delete`；
- `memory_action_success`: 操作是否成功。

## 7. MCP Boundary

本阶段不将 memory 管理工具暴露为 MCP tools。当前 stdio MCP adapter 没有可信的认证 `user_id` 上下文；在身份边界未设计前暴露查看或删除能力会增加越权风险。

## 8. Limitations

- 当前只支持查看和删除单条 profile memory，不支持编辑或多条记忆管理；
- 尚未提供前端 memory 管理界面；
- SQLite 默认模式下 store 为内存实现，服务重启后不会保留长期记忆；PostgresStore 才提供持久化闭环；
- 未实现更完整的敏感信息识别或审计策略。

## 9. Interview Talking Points

我在增加长期记忆后继续补齐了用户控制权：查看和删除不是通过可伪造的 `user_id` 参数完成，而是由 LangGraph `ToolRuntime` 注入当前请求身份与 store，仅访问 `("user_memory", current_user_id)` 下的 profile。删除使用 store 原生 `adelete`，异常安全降级并写入 Trace。同时我阻止“你记住了我什么”这类管理指令被误保存，从功能闭环延伸到隐私与一致性闭环。
