# Course Fast Path Optimization Comparison

## 1. Background

Phase 1 Trace 显示，即使是可以直接从本地课程表查询的问题，原链路仍会经过完整 LLM / Agent 工具调用流程。课程查询 Fast Path 的目标是：对于能够由规则路由和参数解析明确识别的课程问题，直接调用 `get_course_schedule`，减少模型耗时与 token 消耗，同时保留无法明确解析时的原 Agent 处理能力。

本对比仅使用两份 benchmark 中共同出现的 5 个课程问题，不扩展到活动、学习计划或校园制度问答。

## 2. Benchmark Setup

### Benchmark Sources

| 阶段 | Benchmark 文件 | Git commit hash | 样本数量 | Agent | Model |
| --- | --- | --- | ---: | --- | --- |
| Before | `docs/optimization/benchmark_runs/2026-05-25_before_course_fast_path_same_questions.md` | `5b426de` | 5 | `research-assistant` | `deepseek-chat` |
| After | `docs/optimization/benchmark_runs/2026-05-25_after_course_fast_path_same_questions.md` | `5b426de` | 5 | `research-assistant` | `deepseek-chat` |

两份 benchmark 均记录相同 commit hash；本文仅按两份已导出的 Trace 报告中可见的 before / after 行为与指标进行对比，不推断未记录的代码提交状态。

### Fixed Question Set

| 序号 | 相同测试问题 |
| ---: | --- |
| 1 | 我周一上午有什么课？ |
| 2 | 我周一有什么课？ |
| 3 | 我周二下午有什么课？ |
| 4 | 数据结构课在哪里上？ |
| 5 | 操作系统课在哪里上？ |

## 3. Before vs After Summary

| 指标 | Before | After | 变化 |
| --- | ---: | ---: | ---: |
| 平均 `total_latency_ms` | 3535.00 ms | 1.19 ms | 下降 3533.81 ms（99.97%） |
| 平均 `llm_time_ms` | 3502.92 ms | 0.00 ms | 下降 3502.92 ms |
| 平均 `tool_time_ms` | - | 0.74 ms | Before 未记录，无法计算变化 |
| 平均 `prompt_tokens` | 5329.00 | 0.00 | 节省 5329.00 |
| 平均 `completion_tokens` | 190.00 | 0.00 | 节省 190.00 |
| 平均 `total_tokens` | 5519.00 | 0.00 | 节省 5519.00 |
| `error_count` | 0 | 0 | 无新增已记录错误 |

### Tool Invocation Preservation

| 问题 | Before 是否记录 `get_course_schedule` | After 是否记录 `get_course_schedule` |
| --- | --- | --- |
| 我周一上午有什么课？ | - | 是 |
| 我周一有什么课？ | 是 | 是 |
| 我周二下午有什么课？ | 是 | 是 |
| 数据结构课在哪里上？ | - | 是 |
| 操作系统课在哪里上？ | 是 | 是 |

After 阶段的 5 个请求均明确记录了 `get_course_schedule`。Before 阶段有 3 个请求记录了该工具，另外 2 个请求的 `tool_calls` 字段为 `-`，因此不能基于 benchmark 推断其是否执行过工具。

## 4. Per-query Comparison

### 我周一上午有什么课？

| 字段 | Before | After |
| --- | --- | --- |
| `route` | `stream` | `course_schedule_fast_path` |
| `tool_calls` | - | `get_course_schedule` |
| `total_latency_ms` | 2582.25 | 0.66 |
| `llm_time_ms` | 2566.34 | 0 |
| `tool_time_ms` | - | 0.42 |
| `prompt_tokens` | 3160 | 0 |
| `completion_tokens` | 154 | 0 |
| `total_tokens` | 3314 | 0 |
| `error_message` | - | - |

### 我周一有什么课？

| 字段 | Before | After |
| --- | --- | --- |
| `route` | `stream` | `course_schedule_fast_path` |
| `tool_calls` | `get_course_schedule` | `get_course_schedule` |
| `total_latency_ms` | 4263.44 | 0.62 |
| `llm_time_ms` | 4221.41 | 0 |
| `tool_time_ms` | - | 0.48 |
| `prompt_tokens` | 5661 | 0 |
| `completion_tokens` | 272 | 0 |
| `total_tokens` | 5933 | 0 |
| `error_message` | - | - |

### 我周二下午有什么课？

| 字段 | Before | After |
| --- | --- | --- |
| `route` | `stream` | `course_schedule_fast_path` |
| `tool_calls` | `get_course_schedule` | `get_course_schedule` |
| `total_latency_ms` | 4377.70 | 0.58 |
| `llm_time_ms` | 4333.93 | 0 |
| `tool_time_ms` | - | 0.43 |
| `prompt_tokens` | 6757 | 0 |
| `completion_tokens` | 168 | 0 |
| `total_tokens` | 6925 | 0 |
| `error_message` | - | - |

### 数据结构课在哪里上？

| 字段 | Before | After |
| --- | --- | --- |
| `route` | `stream` | `course_schedule_fast_path` |
| `tool_calls` | - | `get_course_schedule` |
| `total_latency_ms` | 2834.51 | 3.67 |
| `llm_time_ms` | 2815.72 | 0 |
| `tool_time_ms` | - | 2.09 |
| `prompt_tokens` | 3534 | 0 |
| `completion_tokens` | 152 | 0 |
| `total_tokens` | 3686 | 0 |
| `error_message` | - | - |

### 操作系统课在哪里上？

| 字段 | Before | After |
| --- | --- | --- |
| `route` | `stream` | `course_schedule_fast_path` |
| `tool_calls` | `get_course_schedule` | `get_course_schedule` |
| `total_latency_ms` | 3617.11 | 0.42 |
| `llm_time_ms` | 3577.21 | 0 |
| `tool_time_ms` | - | 0.28 |
| `prompt_tokens` | 7533 | 0 |
| `completion_tokens` | 204 | 0 |
| `total_tokens` | 7737 | 0 |
| `error_message` | - | - |

## 5. Key Findings

1. Before 阶段的五个课程查询均通过 `stream` 路由并记录了显著的 `llm_time_ms` 与 token 使用，表明请求仍处于完整 LLM / Agent 链路中。
2. After 阶段的五个相同课程查询均命中 `course_schedule_fast_path`，平均总耗时从 `3535.00 ms` 降至 `1.19 ms`，下降 `3533.81 ms`，约 `99.97%`。
3. After 阶段五个问题均继续调用 `get_course_schedule`，说明优化绕过的是 LLM / Agent 选择与组织链路，而不是课程数据查询能力本身。
4. After 阶段 `llm_time_ms` 均为 `0`，平均 `total_tokens` 从 `5519.00` 降为 `0.00`，平均节省 `5519.00` tokens。
5. 两组样本均没有记录 `error_message`，在该固定问题集中未观察到 fast path 引入错误。
6. Fast Path 的实现边界仍然重要：无法解析出课程过滤参数或并非课程查询的问题会继续回退原 Agent 链路；这项行为由实现与测试保护，但不属于这五条命中样本的性能数据。

## 6. Limitations

- 当前优化仅覆盖可明确解析的课程查询，没有覆盖校园活动、学习计划或 RAG 制度问答。
- 本次每个问题只有一条 before 和一条 after 样本，适合说明方向性收益，尚不足以给出稳定的 P50、P95 或并发性能结论。
- Before benchmark 的 `tool_time_ms` 均为 `-`，无法对工具自身耗时做严格前后比较。
- Before benchmark 中两个问题的 `tool_calls` 为 `-`；本文只陈述日志中可见的工具调用证据，不补写缺失行为。
- 两份 benchmark 都记录 commit hash 为 `5b426de`；如果后续需要严格审计代码版本与性能样本对应关系，应在每次运行前确认工作区状态并分别导出报告。

## 7. Interview Talking Points

在这个项目中，我先用 Trace 建立了可比较的性能基线，发现简单课程查询仍会进入完整 LLM / Agent 工具调用链路：五个固定课程问题的平均耗时约 `3535 ms`，平均消耗 `5519` tokens。随后我实现了一个保守的规则路由 Fast Path，只对能够解析出星期、时间段或课程名的明确课程查询直接调用原有 `get_course_schedule` 工具；无法解析或非课程问题仍回退原 Agent，不牺牲通用能力。用同一组五个问题复测后，所有请求都命中 `course_schedule_fast_path` 并保留课程工具调用，平均总耗时降到 `1.19 ms`，LLM 耗时和 token 消耗降为 `0`。这个优化的关键不是简单绕过模型，而是用 Trace、固定问题集和 fallback 边界证明：在确定性场景中可以显著降低成本，同时保留系统正确性与可扩展路径。
