# Campus AI Agent Phase 1: Performance Baseline

## Phase 1 目标

Phase 1 的目标是在不改变 Agent 回答、路由、检索和前端协议的前提下，建立最小可用的性能观测基础：

- 为每次 `/invoke` 与 `/stream` 请求生成 `trace_id`。
- 将请求与 `run_id`、`thread_id`、`user_id`、`agent_id`、模型名称关联。
- 记录请求总耗时，并尽可能记录模型与 RAG 检索耗时。
- 将 Trace 以 JSONL 形式写入 `logs/agent_trace.jsonl`，便于后续离线统计。
- 保留当前测试安全网，以同一问题集对比后续优化前后的指标变化。

本阶段不包含 Router、Prompt 拆分、RAG 缓存、Hybrid Retrieval、Fallback Model 或前端 Trace 展示。

## 当前测试问题集

### 课程类问题

| 问题 | 预期工具或行为 | 观察重点 |
| --- | --- | --- |
| 我周一上午有什么课？ | `get_course_schedule` | 总耗时、工具调用是否发生 |
| 数据结构在哪里上？ | `get_course_schedule` | 总耗时、工具输出稳定性 |

### 活动类问题

| 问题 | 预期工具或行为 | 观察重点 |
| --- | --- | --- |
| 最近有什么 AI 相关讲座？ | `get_campus_events` | 总耗时、工具调用是否发生 |
| 最近有没有适合软件工程学生的活动？ | `get_campus_events` | 总耗时、结果数量变化 |

### 学习计划类问题

| 问题 | 预期工具或行为 | 观察重点 |
| --- | --- | --- |
| 帮我制定一份 7 天 AI Agent 学习计划。 | `generate_study_plan` | 总耗时、模型耗时 |
| 结合我的课程表安排本周学习。 | `generate_study_plan` | 总耗时、工具调用稳定性 |

### 制度 RAG 类问题

| 问题 | 期望召回来源 | 观察重点 |
| --- | --- | --- |
| 请假流程是什么？ | `leave_policy.md` | 检索耗时、来源命中 |
| 挂科还能申请奖学金吗？ | `scholarship_policy.md` | 检索耗时、来源命中 |
| 宿舍晚归怎么处理？ | `dormitory_policy.md` | 检索耗时、来源命中 |
| 考试作弊有什么后果？ | `exam_policy.md` | 检索耗时、来源命中 |
| 生病缺考怎么办？ | `exam_policy.md` 或 `leave_policy.md` | 多来源问题召回稳定性 |

## 需要记录的指标

| 指标 | 当前采集位置 | Phase 1 状态 |
| --- | --- | --- |
| `trace_id` | service | 已记录 |
| `run_id` | service | 已记录 |
| `thread_id` / `user_id` | service | 已记录 |
| `agent_id` / `model_name` | service | 已记录 |
| `query` / `route` | service 或 RAG event | 已记录 |
| `total_latency_ms` | service | 已记录 |
| `llm_time_ms` | `research_assistant` / `rag_assistant` model node | 已记录；仅这两个图内生效 |
| `tool_time_ms` | RAG 工具 | 已记录；当前仅覆盖 RAG 检索工具 |
| `retrieval_time_ms` | RAG 工具 | 已记录 |
| `retrieved_docs` | RAG 工具 | 已记录 `source`、`path`、`chunk_id` |
| `tool_calls` | Agent model node 与 RAG 工具 | 尽可能记录 |
| token usage | 可用的模型 metadata | 模型未返回时为 `null` |
| `fallback_triggered` | 预留字段 | 当前始终为 `false` |
| `error_message` | service / RAG 工具 | 异常时记录 |

## JSONL 事件说明

`logs/agent_trace.jsonl` 当前包含两类记录：

| `event_type` | 含义 |
| --- | --- |
| `request` | 一次 `/invoke` 或 `/stream` 请求的总体记录 |
| `rag_retrieval` | 某次 RAG retriever 初始化或检索执行的子事件 |

RAG 子事件与请求通过相同的 `trace_id` 关联。`load_chroma_db` 的初始化事件不会被解释为空检索结果；真正的查询事件会填写 `returned_doc_count`、`source_list`、`chunk_id_list` 与 `is_empty_result`。

## 当前 Baseline 表格模板

| 类别 | 问题 | agent_id | route | tool_calls | retrieved_sources | total_latency_ms | llm_time_ms | retrieval_time_ms | prompt_tokens | completion_tokens | error_message |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| 课程 | 我周一上午有什么课？ | `research-assistant` | `invoke` |  |  |  |  |  |  |  |  |
| 活动 | 最近有什么 AI 相关讲座？ | `research-assistant` | `invoke` |  |  |  |  |  |  |  |  |
| 学习计划 | 帮我制定一份 7 天 AI Agent 学习计划。 | `research-assistant` | `invoke` |  |  |  |  |  |  |  |  |
| 制度 RAG | 请假流程是什么？ | `rag-assistant` | `invoke` |  |  |  |  |  |  |  |  |
| 制度 RAG | 生病缺考怎么办？ | `rag-assistant` | `invoke` |  |  |  |  |  |  |  |  |

## 后续优化如何对比

1. 固定问题集、运行环境、模型配置与 top-k 配置，先收集 Phase 1 数据。
2. 每个问题重复执行多次，统计总耗时和检索耗时的均值、P50、P95。
3. RAG 优化时，同时对比 `correct_doc_recall` 与延迟，避免只提升速度却损失正确来源召回。
4. 缓存优化时，区分冷启动与热请求，单独比较 retriever 初始化耗时。
5. Router 或 Prompt 优化时，对比工具选择准确性、LLM 耗时和 token 用量。
6. 异常兜底优化时，统计 `error_message` 分类与失败率，并确保 SSE/API 契约不回退。

当前 baseline 的重点是先让性能变化可以被记录和比较，而不是提前判断哪种优化方案最好。
