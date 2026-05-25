# Campus AI Agent Phase 2: Rule-based Router Optimization

## 为什么需要 Rule-based Router

Campus AI Agent 的部分用户问题具有高确定性，例如课程表查询、校园活动检索、学习计划生成与校园制度问答。对于这类问题，先用低成本、可解释的规则识别意图，可以为后续减少不必要的 LLM 路由消耗建立基础。

Rule-based Router 的价值包括：

- 规则命中原因和关键词可以直接解释、测试与回归。
- 明确意图可以独立统计命中率、误路由率与性能变化。
- 后续可以只对高置信度请求尝试快路径，低置信度请求仍保留原 Agent 能力。

## Phase 1 Trace 暴露的问题

Phase 1 的真实 Trace 样本中，简单课程问题 `我周一有什么课` 已经能够命中课程查询工具，但仍经过完整 LLM 链路：

| 指标 | 已观察值 |
| --- | ---: |
| `total_latency_ms` | 约 3839 ms |
| `llm_time_ms` | 约 3795 ms |
| `prompt_tokens` | 5659 |
| `completion_tokens` | 295 |
| `total_tokens` | 5954 |

这说明课程类高确定性问题仍承受了完整模型调用带来的延迟与 token 开销。Router 的第一目标不是立即改写链路，而是先稳定判断这类意图，为性能优化提供可靠入口。

## Phase 2.1 当前范围

本阶段新增 `src/core/router.py`，仅实现纯规则分类函数 `route_query()`，输出：

| 输出字段 | 含义 |
| --- | --- |
| `intent` | 分类结果：课程、活动、学习计划、制度问答、普通聊天或未知 |
| `confidence` | 规则命中的相对置信度，范围为 0 到 1 |
| `matched_keywords` | 触发本次决策的关键词 |
| `reason` | 可读的路由理由 |
| `route_source` | 当前固定为 `rule` |

当前支持的意图为：

| Intent | 值 | 示例 |
| --- | --- | --- |
| `COURSE` | `course_schedule` | 我周一上午有什么课？ |
| `EVENT` | `campus_event` | 这周有什么 AI 相关讲座？ |
| `STUDY_PLAN` | `study_plan` | 帮我制定一份 7 天学习计划。 |
| `POLICY` | `campus_policy` | 挂科了还能申请奖学金吗？ |
| `GENERAL` | `general_chat` | 你好，你能做什么？ |
| `UNKNOWN` | `unknown` | 什么是 LangGraph？ |

为避免明显误判，`AI` 单独出现不会触发活动意图；只有同时出现活动、讲座、比赛、报名、宣讲会等活动语境时，才会被视为活动相关关键词。

## 当前不改变的部分

Phase 2.1 只提供分类结果，不接入业务执行链路：

- 不修改 FastAPI `/invoke` 或 `/stream` 处理逻辑。
- 不直接调用课程、活动、学习计划或 RAG 工具。
- 不修改默认 Agent Graph 或 RAG Agent。
- 不改变 API 响应、SSE 流式协议或前端行为。

因此，当前线上请求耗时与 token 消耗不会因为本模块自动降低；其作用是建立可测试的分类基础。

## Phase 2.2 接入 Service 快路径

后续接入时可在 service 层谨慎引入高置信度快路径：

1. 在请求进入 Agent 前调用 `route_query()`，并将意图、置信度和规则命中信息写入 Trace。
2. 对置信度高且输出形式稳定的课程/活动查询先进行实验性快路径处理。
3. 对制度问答、复杂多意图请求和低置信度请求继续走现有 Agent/RAG 链路。
4. 保持原 API 与 SSE 协议不变，并为误路由、回退到 Agent 的场景建立测试。

接入前需要额外补充冲突问题集，例如同时包含课程、活动、制度或学习计划词的查询，确认优先级不会误伤用户意图。

## 如何用 Benchmark 对比优化效果

Phase 2.2 实施前后，应使用同一问题集、同一模型配置与相近运行环境分别导出 benchmark：

```bash
.venv/bin/python scripts/export_benchmark_run.py --name phase1_baseline --last 15
.venv/bin/python scripts/export_benchmark_run.py --name after_router --last 15
```

对比 `phase1_baseline` 与 `after_router` 时，重点关注：

| 比较维度 | 目标 |
| --- | --- |
| Router 分类准确性 | 高确定性课程/活动问题不发生误路由 |
| `average_total_latency_ms` | 快路径问题的总耗时下降 |
| `average_llm_time_ms` | 可直接处理的问题减少模型时间 |
| `average_prompt_tokens` / `average_total_tokens` | 简单查询减少 token 消耗 |
| `error_count` | 优化不能增加失败率 |
| RAG 来源召回 | 制度问答链路不得因 Router 接入而退化 |

结论应以真实 Trace 与固定回归问题集为依据；尚未运行的新场景保留为 TODO，不用推断数据代替采集。
