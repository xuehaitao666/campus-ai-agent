# Campus AI Agent Phase 1: Performance Baseline

## Phase 1 目标

Phase 1 的目标是在不改变 Agent 回答、路由、检索和前端协议的前提下，建立最小可用的性能观测基础：

- 为每次 `/invoke` 与 `/stream` 请求生成 `trace_id`。
- 将请求与 `run_id`、`thread_id`、`user_id`、`agent_id`、模型名称关联。
- 记录请求总耗时，并尽可能记录模型与 RAG 检索耗时。
- 将 Trace 以 JSONL 形式写入 `logs/agent_trace.jsonl`，便于后续离线统计。
- 保留当前测试安全网，以同一问题集对比后续优化前后的指标变化。

本阶段不包含 Router、Prompt 拆分、RAG 缓存、Hybrid Retrieval、Fallback Model 或前端 Trace 展示。

## 测试环境

| 项目 | 当前核查信息 |
| --- | --- |
| 核查日期 | 2026-05-25 |
| Trace 文件 | `logs/agent_trace.jsonl` |
| 已有记录数 | 167 条：`request` 163 条，`rag_retrieval` 4 条 |
| 接口样本 | `/stream` 与测试过程产生的 `/invoke` |
| 可观察模型样本 | `deepseek-chat` |
| RAG 数据源 | `data/knowledge_base/*.md` 与本地 Chroma 向量库 |
| 单元测试隔离方式 | fake agent / fake retriever / 临时 JSONL 路径 |

当前日志同时包含自动化测试请求与少量真实 Agent 流式运行样本，因此可用于验证 Trace 字段完整性和取得第一批观测值，但还不能视为经过严格控制的性能压测结果。

### JSONL 完整性核查

对当前 `logs/agent_trace.jsonl` 的全部 167 条记录进行字段核查后：

- 要求的 20 个核心字段在每条记录中均存在，缺失字段数为 `0`。
- `request` 记录均已写入 `run_id` 与 `total_latency_ms`。
- 已观察到 3 条请求记录可提供 `llm_time_ms` 及 token usage。
- 已观察到 2 条请求记录回填 `tool_time_ms`，以及 4 条记录携带 `retrieved_docs`。
- 已观察到 8 条异常路径记录写入 `error_message`。
- RAG 初始化/检索子事件可独立记录 `retrieval_time_ms`，因此 `rag_retrieval` 事件的 `total_latency_ms` 按设计为 `null`。

## 测试问题集

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

## 当前 Trace 字段说明

| 字段 | 当前采集位置 | 含义 |
| --- | --- | --- |
| `trace_id` | service | 请求与 RAG 子事件的关联标识 |
| `run_id` | service | LangGraph/LangChain 执行标识 |
| `thread_id` / `user_id` | service | 会话与用户维度关联信息 |
| `agent_id` / `model_name` | service | 执行 Agent 与模型信息 |
| `query` / `route` | service 或 RAG event | 用户问题与调用路径，如 `invoke`、`stream`、`query_campus_policy` |
| `tool_calls` | Agent model node / RAG 工具 | 已观察到的工具名与参数 |
| `retrieved_docs` | RAG 工具 | 检索片段的 `source`、`path`、`chunk_id` |
| `total_latency_ms` | service | 请求级总耗时 |
| `llm_time_ms` | 两个校园 Agent 的 model node | 模型节点累计耗时 |
| `tool_time_ms` | RAG 工具 | 当前为 RAG 查询工具耗时 |
| `retrieval_time_ms` | RAG 工具 | retriever 初始化或查询耗时 |
| token 字段 | AI message metadata | prompt、completion 与 total token |
| `fallback_triggered` | 预留字段 | 是否发生 fallback |
| `error_message` | service / RAG 工具 | 异常信息 |
| `created_at` | tracing module | UTC ISO 时间戳 |

### JSONL 事件说明

`logs/agent_trace.jsonl` 当前包含两类记录：

| `event_type` | 含义 |
| --- | --- |
| `request` | 一次 `/invoke` 或 `/stream` 请求的总体记录 |
| `rag_retrieval` | 某次 RAG retriever 初始化或检索执行的子事件 |

RAG 子事件与请求通过相同的 `trace_id` 关联。`load_chroma_db` 的初始化事件不会被解释为空检索结果；真正的查询事件会填写 `returned_doc_count`、`source_list`、`chunk_id_list` 与 `is_empty_result`。

## 当前已经能自动记录的字段

| 字段 | 当前真实日志验证结果 |
| --- | --- |
| `trace_id`、`run_id`、`thread_id`、`user_id` | `request` 记录已写入 |
| `agent_id`、`model_name`、`query`、`route` | 已写入；可区分 `invoke` / `stream` 和 RAG 子事件 |
| `total_latency_ms` | 全部 163 条 `request` 记录有值 |
| `llm_time_ms` | 实际执行校园 Agent model node 的样本已有值 |
| `tool_calls` | 真实课程/RAG 工具调用样本已有值 |
| `retrieved_docs`、`retrieval_time_ms` | RAG 检索样本已有来源与耗时 |
| `prompt_tokens`、`completion_tokens`、`total_tokens` | `deepseek-chat` 样本可读取 usage metadata |
| `error_message` | 异常路径可以记录 |
| `created_at` | 所有事件均写入 |

## 当前仍为 TODO 的字段

| 字段或能力 | 当前现状 | TODO |
| --- | --- | --- |
| `llm_time_ms` | fake agent、static agent 或未接入 model node 的 Agent 为 `null` | TODO：按需统一其他 Agent 节点计时 |
| `tool_time_ms` | 仅 RAG 查询工具目前能回填；课程、活动、学习计划工具为 `null` | TODO：后续统一普通工具计时 |
| `retrieval_time_ms` / `retrieved_docs` | 非 RAG 请求为 `null` / 空列表，符合当前语义 | 无需强行填充 |
| `prompt_tokens` / `completion_tokens` / `total_tokens` | mock 响应或不携带 usage metadata 的 provider 为 `null` | TODO：扩大 provider token metadata 覆盖 |
| `fallback_triggered` | 字段存在但当前恒为 `false` | TODO：实现 Fallback 后采集触发状态 |
| `route` | 请求与 RAG 子事件已有值 | TODO：若后续新增 Router，再扩展为业务意图路由 |

## 真实 Trace 示例

以下记录来自 `logs/agent_trace.jsonl` 中已实际运行的课程查询样本，不是模拟数据：

```json
{
  "query": "我周一有什么课",
  "route": "stream",
  "agent_id": "research-assistant",
  "model_name": "deepseek-chat",
  "tool_calls": [{"name": "get_course_schedule", "args": {"day": "周一"}}],
  "total_latency_ms": 3839.20,
  "llm_time_ms": 3794.81,
  "prompt_tokens": 5659,
  "completion_tokens": 295,
  "total_tokens": 5954
}
```

该样本说明，即使是课程表可直接查询的简单问题，当前仍会经过完整 LLM 工具调用与回答链路。

## 手动测试记录表

后续进行同批问题的手动采集时，按以下模板逐次登记；没有真实运行结果的项继续保持 `TODO`，不以推断补值。

| 测试日期 | 类别 | 问题 | agent_id | model_name | route | tool_calls | retrieved_sources | total_latency_ms | llm_time_ms | retrieval_time_ms | total_tokens | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| TODO | 课程 | 我周一上午有什么课？ | `research-assistant` | TODO | `invoke` | TODO | 不适用 | TODO | TODO | 不适用 | TODO | 待采集 |
| TODO | 活动 | 最近有什么 AI 相关讲座？ | `research-assistant` | TODO | `invoke` | TODO | 不适用 | TODO | TODO | 不适用 | TODO | 待采集 |
| TODO | 学习计划 | 帮我制定一份 7 天 AI Agent 学习计划。 | `research-assistant` | TODO | `invoke` | TODO | 不适用 | TODO | TODO | 不适用 | TODO | 待采集 |
| TODO | RAG 制度 | 请假流程是什么？ | `rag-assistant` | TODO | `invoke` | TODO | TODO | TODO | TODO | TODO | TODO | 待采集 |

下表中已有数值来自 2026-05-25 核查到的真实 Trace 样本；`待采集` 表示当前日志还没有该固定问题的可对比样本。

## 课程类 baseline

| 问题 | agent_id | route | tool_calls | total_latency_ms | llm_time_ms | prompt_tokens | completion_tokens | total_tokens |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 我周一有什么课 | `research-assistant` | `stream` | `get_course_schedule(day=周一)` | 3839.20 | 3794.81 | 5659 | 295 | 5954 |
| 我周一上午有什么课？ | `research-assistant` | `invoke` | 待采集 | 待采集 | 待采集 | 待采集 | 待采集 | 待采集 |

## 活动类 baseline

| 问题 | agent_id | route | tool_calls | total_latency_ms | llm_time_ms | token usage |
| --- | --- | --- | --- | ---: | ---: | --- |
| 最近有什么 AI 相关讲座？ | `research-assistant` | `invoke` | 待采集 | 待采集 | 待采集 | 待采集 |
| 最近有没有适合软件工程学生的活动？ | `research-assistant` | `invoke` | 待采集 | 待采集 | 待采集 | 待采集 |

## 学习计划类 baseline

| 问题 | agent_id | route | tool_calls | total_latency_ms | llm_time_ms | token usage |
| --- | --- | --- | --- | ---: | ---: | --- |
| 帮我制定一份 7 天 AI Agent 学习计划。 | `research-assistant` | `invoke` | 待采集 | 待采集 | 待采集 | 待采集 |
| 结合我的课程表安排本周学习。 | `research-assistant` | `invoke` | 待采集 | 待采集 | 待采集 | 待采集 |

## RAG 制度问答 baseline

| 问题 | agent_id | route | retrieved_sources | total_latency_ms | llm_time_ms | retrieval_time_ms | tokens |
| --- | --- | --- | --- | ---: | ---: | ---: | --- |
| 如果我数据结构不及格，还可以评奖学金吗 | `research-assistant` | `stream` | `scholarship_policy.md`, `exam_policy.md`, `leave_policy.md` | 23800.39 | 6083.19 | 17670.46 | 7311 |
| 挂科了还能申请奖学金吗？ | `research-assistant` | `stream` | `scholarship_policy.md`, `leave_policy.md`, `student_handbook.md`, `exam_policy.md` | 19582.78 | 8845.88 | 10699.57 | 9217 |
| 请假流程是什么？ | `rag-assistant` | `invoke` | 待采集 | 待采集 | 待采集 | 待采集 | 待采集 |
| 生病缺考怎么办？ | `rag-assistant` | `invoke` | 待采集 | 待采集 | 待采集 | 待采集 | 待采集 |

## 当前观察到的性能问题

### 简单课程查询仍消耗完整 LLM 链路

真实样本 `我周一有什么课` 已命中 `get_course_schedule(day=周一)`，但仍记录到：

- `total_latency_ms` 约 `3839 ms`
- `llm_time_ms` 约 `3794 ms`
- `prompt_tokens` 为 `5659`
- `completion_tokens` 为 `295`
- `total_tokens` 为 `5954`

这说明简单、规则明确的课程查询当前仍依赖完整 LLM 选择工具并组织回复，LLM 时间几乎占据总耗时，且系统 prompt 与上下文带来了较高 token 消耗。后续 Phase 2 可以评估 `Rule-based Router + 模板化响应`：对高确定性的课程、活动等请求减少 LLM 调用或缩短 LLM 链路，并以本表中的延迟和 token 作为对比基线。

### RAG 检索已有明显冷启动开销信号

已采集的两个奖学金制度问题都正确召回了 `scholarship_policy.md`，但请求中的 `retrieval_time_ms` 分别约为 `17670 ms` 和 `10700 ms`。这只是当前真实样本的观察信号，尚不足以直接判定优化方案；后续需要固定问题集并区分冷启动、热请求后再作结论。

## 后续优化阶段如何对比

1. 固定问题集、运行环境、模型配置与 top-k 配置，先收集 Phase 1 数据。
2. 每个问题重复执行多次，统计总耗时和检索耗时的均值、P50、P95。
3. RAG 优化时，同时对比 `correct_doc_recall` 与延迟，避免只提升速度却损失正确来源召回。
4. 缓存优化时，区分冷启动与热请求，单独比较 retriever 初始化耗时。
5. Router 或 Prompt 优化时，对比工具选择准确性、LLM 耗时和 token 用量。
6. 异常兜底优化时，统计 `error_message` 分类与失败率，并确保 SSE/API 契约不回退。

当前 baseline 的重点是先让性能变化可以被记录和比较，而不是提前判断哪种优化方案最好。
