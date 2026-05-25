# Campus Event Fast Path Optimization

## 为什么活动查询适合 Fast Path

校园活动查询与课程查询一样，存在一类意图明确、参数有限、数据源固定的问题，例如“这周有什么 AI 相关讲座？”或“最近有没有比赛可以报名？”。这些请求可以从文本中提取关键词、日期范围和活动类型，并直接查询本地校园活动数据，无需先由 LLM 选择工具再整理结果。

Phase 2.3 的目标是对明确活动查询减少完整 LLM / Agent 链路的延迟与 token 开销，同时保留原有 Agent 作为无法确认意图或无法解析参数时的兜底。

## 和课程 Fast Path 的关系

| 能力 | 课程 Fast Path | 活动 Fast Path |
| --- | --- | --- |
| 规则意图 | `course_schedule` | `campus_event` |
| 直接调用工具 | `get_course_schedule` | `get_campus_events` |
| 输出协议 | 保持 `ChatMessage` / SSE 不变 | 保持 `ChatMessage` / SSE 不变 |
| Trace route | `course_schedule_fast_path` | `campus_event_fast_path` |
| Fallback | 原 Agent 链路 | 原 Agent 链路 |

两个 Fast Path 都只替代高确定性请求的模型路由过程，不替换已有工具数据能力，也不改变未命中请求的通用 Agent 行为。

## Fast Path 触发条件

活动 Fast Path 仅在下列条件同时满足时执行：

1. `route_query()` 将问题识别为 `EVENT`。
2. `parse_event_query()` 能解析出至少一个工具可用过滤参数：`keyword`、`date_range` 或 `event_type`。

当前参数解析范围：

| 用户表达 | 工具参数 |
| --- | --- |
| `AI` / `人工智能` | `keyword="AI"` |
| `软件工程` | `keyword="软件工程"` |
| `报名` | `keyword="报名"` |
| `宣讲会` | `keyword="宣讲"` |
| `讲座` | `event_type="讲座"` |
| `比赛` / `竞赛` | `event_type="比赛"` |
| `社团` | `event_type="社团"` |
| `招聘会` | `event_type="招聘"` |
| `这周` / `本周` / `最近` / `今天` / `明天` | 同值 `date_range` |

例如：

- `这周有什么 AI 相关讲座？` 会直接调用 `get_campus_events(keyword="AI", date_range="这周", event_type="讲座")`。
- `最近有没有比赛可以报名？` 会直接调用 `get_campus_events(keyword="报名", date_range="最近", event_type="比赛")`。

## Fallback 逻辑

以下情况继续进入原 Agent / LangGraph 链路：

- 问题没有被规则分类为校园活动，例如 `AI 是什么？`。
- 问题虽然提到活动，但无法解析出可用于查询的有效过滤条件，例如 `有什么活动推荐？`。
- 学习计划或校园制度等拥有更高优先级的明确意图问题。

本阶段没有接入学习计划或 RAG Fast Path，也没有修改前端展示与 SSE 协议。

## Trace 记录

命中活动 Fast Path 的请求会继续生成请求级 Trace，并记录：

| Trace 字段 | Fast Path 记录值 |
| --- | --- |
| `route` | `campus_event_fast_path` |
| `tool_calls` | `get_campus_events` 与解析出的参数 |
| `total_latency_ms` | 服务请求总耗时 |
| `tool_time_ms` | 本地活动查询工具耗时 |
| `llm_time_ms` | `0` |
| `prompt_tokens` / `completion_tokens` / `total_tokens` | `0` |
| `error_message` | 正常请求为 `null` |

## 后续 Benchmark 对比

在实施前后应使用完全相同的活动问题集分别导出 benchmark，例如：

```bash
.venv/bin/python scripts/export_benchmark_run.py --name before_event_fast_path_same_questions --last 5
.venv/bin/python scripts/export_benchmark_run.py --name after_event_fast_path_same_questions --last 5
```

建议至少固定比较以下问题：

| 问题 | 预期活动过滤 |
| --- | --- |
| 这周有什么 AI 相关讲座？ | `AI`、`这周`、`讲座` |
| 最近有没有比赛可以报名？ | `报名`、`最近`、`比赛` |
| 最近有什么软件工程相关活动？ | `软件工程`、`最近` |
| 这周有哪些社团活动？ | `这周`、`社团` |
| 最近有招聘会吗？ | `最近`、`招聘` |

对比时重点查看 `route`、`tool_calls`、`total_latency_ms`、`llm_time_ms` 与 token 字段，并保留至少一组 fallback 问题确认普通对话仍由原 Agent 处理。
