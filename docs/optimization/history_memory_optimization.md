# History Interface and Context Trimming Optimization

## 1. Background

Campus AI Agent 使用 LangGraph checkpoint 保存 thread 级别的完整对话历史。完整历史适合恢复会话与调试，但如果每一次模型调用都携带所有历史消息，多轮对话越长，prompt token、模型延迟和调用成本就越容易持续增长。

Phase 4.2 将两个关注点分开处理：

- `/history` 面向调用方查看历史，提供 Agent 选择、返回数量限制和工具中间步骤开关。
- 模型调用上下文面向推理成本控制，只将有限数量的最近消息交给模型，同时保留 checkpoint 中的完整历史。

本阶段不引入长期记忆、摘要记忆或向量记忆，也不修改 RAG 检索逻辑。

## 2. History API Parameters

`ChatHistoryInput` 现在支持：

| 字段 | 默认值 | 作用 |
| --- | --- | --- |
| `thread_id` | 必填 | 指定要读取的对话线程 |
| `agent_id` | `null` | 指定从哪个 Agent 读取 checkpoint；缺省继续使用默认 Agent |
| `limit` | `50` | 返回最近的可见消息条数，范围为 `1` 到 `200` |
| `include_tools` | `true` | 是否保留工具调用请求与工具返回消息 |

只提供 `thread_id` 的旧请求保持兼容。

当 `include_tools=false` 时，接口过滤：

- `ToolMessage` 工具执行结果；
- 带 `tool_calls` 的中间 `AIMessage`。

这样用户仍能看到问题与最终回答，而不必处理 Agent 内部工具闭环。

## 3. `history.limit` and `HISTORY_MAX_MESSAGES`

这两个限制用途不同，不能混用：

| 配置 | 生效位置 | 目的 |
| --- | --- | --- |
| `history.limit` | `/history` API 返回阶段 | 控制调用方一次查看多少条消息 |
| `HISTORY_MAX_MESSAGES` | Agent 调用模型之前 | 控制模型上下文成本，默认 `20` |

`history.limit` 不改变存储状态，也不改变模型看到的上下文。`HISTORY_MAX_MESSAGES` 不删除历史记录，只生成一个交给模型使用的裁剪视图。

环境变量示例：

```env
HISTORY_MAX_MESSAGES=20
```

## 4. Model Context Trimming

`trim_messages_for_model(messages, max_messages)` 使用以下策略：

1. 保留所有 `SystemMessage`。
2. 对非 system 消息仅保留最近 `HISTORY_MAX_MESSAGES` 条。
3. 始终保留最新的用户输入，因为它位于最近消息窗口中。
4. 不生成摘要，不将旧消息写入其他存储。
5. Agent graph 与 checkpoint 仍保留原始完整消息序列。

这是一种保守的成本控制方式：对长对话建立明确上限，同时避免在摘要质量或记忆召回准确率上引入新的变量。

## 5. Trace Fields

模型节点会把裁剪情况记录进请求 Trace：

| Trace 字段 | 含义 |
| --- | --- |
| `history_message_count` | 当前模型节点裁剪前看到的历史消息总数 |
| `trimmed_message_count` | 因上下文预算被移除的旧消息数量 |
| `history_max_messages` | 本次调用使用的非 system 消息上限 |

工具调用闭环可能使一个请求多次进入模型节点，Trace 保存该请求中观测到的最大历史规模与最大裁剪数量，便于 benchmark 分析。

## 6. Test Coverage

本阶段测试覆盖：

- 仅发送 `thread_id` 的旧 history 请求仍然有效；
- `agent_id` 能选择对应 Agent，未知 Agent 返回明确错误；
- 不同 `thread_id` 的历史互不串线；
- `limit` 仅返回最近指定数量的消息；
- `include_tools=true` 保留工具消息，`false` 只保留用户与最终 AI 消息；
- 裁剪函数保留 system message 与最新用户输入；
- 超出 `HISTORY_MAX_MESSAGES` 时 Trace 能记录裁剪数量；
- 相关测试使用 fake graph / fake model，不调用真实模型 API。

## 7. Current Boundaries

本阶段刻意没有实现：

- 跨 thread 的长期用户记忆；
- 旧历史摘要或自动压缩内容；
- 向量化历史召回；
- 面向前端的历史筛选 UI；
- 针对 ToolMessage 成组保留的复杂上下文策略。

后续如果对话长度进一步增长，可以在保留当前最近消息窗口的基础上，增加经过验证的摘要层或用户画像存储，并在 Trace 中对比摘要 token 成本、答案一致性与召回准确性。

## 8. Interview Talking Points

我先区分了“历史可恢复”和“模型每轮必须读取全部历史”这两件事。LangGraph checkpoint 继续保留完整 thread 历史，保证会话恢复和审计能力；但在模型调用前，我通过可配置的最近消息窗口限制上下文增长，并用 Trace 记录裁剪前消息数与实际裁剪量。与此同时，history 接口增加 `agent_id`、`limit` 和 `include_tools`，让调用方按场景查看不同粒度的历史。这种做法先解决 token 与延迟的可控问题，再为后续摘要记忆或长期记忆保留演进空间。
