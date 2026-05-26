# Schema `custom_data` Extension

## 1. Motivation

`ChatMessage.content` 适合承载面向用户的自然语言或 Markdown 回答，但不适合继续承担结构化信息的解析职责。例如，RAG 来源引用如果只能从 Markdown 文本中反向解析，前端难以稳定地展示来源卡片，API 消费方也难以可靠地统计检索文档和性能指标。

Phase 4.3 在不改变现有内容格式的前提下，使用现有 `ChatMessage.custom_data` 作为可选的结构化扩展通道：

- 旧客户端仍然读取 `type`、`content`、`tool_calls` 和 `run_id`；
- 新客户端可以逐步消费来源、指标和工具状态；
- `/invoke` 与 `/stream` 的既有响应外层结构不变。

## 2. Why `custom_data`

当前阶段选择 `dict[str, Any]` 的 `custom_data`，而不是立即新增一批强类型响应模型，原因是：

1. 兼容已有 Streamlit 渲染流程，未知字段不会影响文字回答展示。
2. 可以复用 Phase 1-4 已积累的请求 Trace，而无需重构 Agent Graph 或 ToolNode。
3. 能先验证哪些字段真正对前端和 benchmark 有价值，再稳定为强类型 schema。

`ChatMessage.custom_data` 使用独立的默认字典，旧消息没有附加数据时序列化结果仍然有效。

## 3. Recommended Structure

当前 service 响应边界支持以下结构：

```json
{
  "retrieved_docs": [
    {
      "source": "exam_policy.md",
      "chunk_id": "exam_policy.md::chunk-0001",
      "section": "作弊处理",
      "heading_path": "考试纪律 > 作弊处理",
      "policy_type": "exam",
      "retrieval_source": "vector+bm25",
      "hybrid_score": 0.03
    }
  ],
  "source_citations": [
    {
      "source": "exam_policy.md",
      "chunk_id": "exam_policy.md::chunk-0001",
      "section": "作弊处理"
    }
  ],
  "metrics": {
    "total_latency_ms": 1200.0,
    "retrieval_time_ms": 30.0,
    "prompt_tokens": 700,
    "trimmed_message_count": 2
  },
  "tool_execution": [
    {
      "tool_name": "Database_Search",
      "status": "success",
      "latency_ms": 30.0
    }
  ],
  "model_fallback": {
    "primary_model": "gpt-5-nano",
    "fallback_model": "claude-haiku-4-5",
    "fallback_triggered": true,
    "model_error": "primary timed out"
  }
}
```

响应仅输出当前 Trace 中可获得的值；缺少的 metadata 不会被编造。

## 4. Field Groups

### `retrieved_docs`

用于表达 RAG 检索得到的 evidence chunk，可包含：

- `source`
- `chunk_id`
- `section`
- `heading_path`
- `policy_type`
- `retrieval_source`
- `hybrid_score`

工具原有 Markdown 来源内容保持不变，结构化数据是补充层。

### `source_citations`

用于轻量展示引用，当前保留：

- `source`
- `chunk_id`
- `section`

后续前端可用它构建来源列表，而无需解析回答正文。

### `metrics`

来自当前请求 Trace 的可用指标，包括：

- `total_latency_ms`
- `llm_time_ms`
- `tool_time_ms`
- `retrieval_time_ms`
- `prompt_tokens`
- `completion_tokens`
- `total_tokens`
- `context_docs_count`
- `context_chars`
- `estimated_context_tokens`
- `dropped_context_docs_count`
- `history_message_count`
- `trimmed_message_count`

### `tool_execution`

当前为最小可用工具执行摘要列表，包含工具名称、状态、可用耗时和错误信息。它复用已有 Trace，不改变 `ToolNode` 的运行协议。

### `model_fallback`

当模型调用链具备可靠性信息时，可包含：

- `primary_model`
- `fallback_model`
- `fallback_triggered`
- `model_error`

这使 API 消费方能够区分正常回答与由候补模型完成的回答。

## 5. Compatibility

兼容性策略如下：

- `custom_data` 是可选附加字段，默认 `{}`。
- LangChain `additional_kwargs["custom_data"]` 与 `response_metadata["custom_data"]` 会被保留。
- service 从 Trace 附加的数据不会覆盖消息本身已经提供的同名数据。
- `/invoke` 仍返回一个 `ChatMessage`。
- `/stream` 仍发送原有 `message` event 与 `data: [DONE]`，仅在 message 内容对象中增加可选结构化信息。
- 本阶段不修改前端 UI；旧渲染逻辑可以继续只显示 `content`。

## 6. Current Limitations

`dict[str, Any]` 便于快速兼容扩展，但缺少严格字段验证和 OpenAPI 自描述能力。工具执行信息目前也是请求 Trace 的轻量摘要，不是逐 node 的完整执行事件流。

后续可逐步升级为：

- `RetrievedDocument`
- `SourceCitation`
- `MessageMetrics`
- `ToolExecutionInfo`
- `ModelFallbackInfo`

并将 `ChatMessage.custom_data` 替换为这些可选强类型结构的组合，同时继续提供向后兼容的序列化输出。

## 7. Interview Talking Points

我没有把来源和性能信息继续塞进回答文本后再让前端反解析，而是利用已有 `custom_data` 建立兼容的结构化响应通道。RAG 内容和来源 Markdown 保持可读，API 同时提供 evidence chunk、citation、Trace metrics、工具执行和 fallback 状态。这样不需要重构 Agent Graph 或立刻修改前端，就能为后续来源展示、调试面板和成本分析建立稳定的数据基础；等字段经过实际使用验证后，再升级为强类型 schema。
