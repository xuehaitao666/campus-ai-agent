# RAG Retriever Cache Optimization Comparison

## 1. Background

Phase 3.1 针对校园制度 RAG 的重复初始化成本进行了优化：用户每次提出新问题时，向量检索本身仍然必须执行，但 embedding、Chroma 与 retriever 不需要在同一服务进程中重复初始化。本次对比关注缓存加入后，检索链路耗时是否下降，以及返回的制度来源是否保持稳定。

## 2. Benchmark Setup and Comparison Boundary

本对比使用以下两份原始 benchmark：

| 阶段 | Benchmark 文件 | Request Sample Size | Child Event Count | Valid Trace Records |
| --- | --- | ---: | ---: | ---: |
| Before | `docs/optimization/benchmark_runs/2026-05-25_before_rag_retriever_cache_same_questions.md` | `2` | `3` | `5` |
| After | `docs/optimization/benchmark_runs/2026-05-25_after_rag_retriever_cache_same_questions.md` | `3` | `2` | `5` |

两份文件都是 `5 valid trace records`，但记录中包含 RAG child event，并非五条可直接逐题对齐的 request-level 样本。由于 before 的 request sample size 为 `2`，after 的 request sample size 为 `3`，严格同题对比只基于两条重合问题：

- 考试作弊有什么后果？
- 如果我因为生病缺考怎么办？

After 中的“宿舍晚归会怎么处理？”没有对应 before request 样本，因此仅用于补充观察检索来源，不参与严格前后性能下降计算。

此外，before 文件中展示的 `git commit hash: 8d083e0` 可能是导出脚本运行时所在的 commit，不一定精确对应 trace 产生时的旧业务代码版本。因此本文依据 trace 中的实际指标与内容进行比较，不将该 hash 单独作为版本差异证明。

## 3. Summary

以下 Summary 指标按两份 benchmark 文件各自已经汇总的 request 样本展示。由于请求数量不同，该表用于观察整体运行结果，不替代后文的两条同题严格对比。

| Metric | Before | After | Change |
| --- | ---: | ---: | ---: |
| `average_total_latency_ms` | `24804.17` | `7174.04` | 下降 `17630.13 ms` |
| `average_tool_time_ms` | `16876.32` | `40.81` | 下降 `16835.51 ms` |
| `average_retrieval_time_ms` | `16876.32` | `40.80` | 下降 `16835.52 ms` |
| `average_total_tokens` | `13133.00` | `12334.33` | 下降 `798.67` tokens |

缓存优化直接针对的是工具与检索阶段初始化开销。`average_total_tokens` 的变化记录如上，但 LLM token 并不是本阶段的优化目标，且两侧 request 样本并不完全一致，不应据此归因于 retriever cache。

## 4. Same-query Comparison

### 考试作弊有什么后果？

| Field | Before | After | Observation |
| --- | --- | --- | --- |
| `retrieved_docs` | `exam_policy.md (chunk-0003)`、`leave_policy.md (chunk-0003)`、`exam_policy.md (chunk-0001)`、`exam_policy.md (chunk-0002)`、`scholarship_policy.md (chunk-0001)` | `exam_policy.md (chunk-0003)`、`leave_policy.md (chunk-0003)`、`exam_policy.md (chunk-0001)`、`exam_policy.md (chunk-0002)`、`scholarship_policy.md (chunk-0001)` | 来源与顺序一致，核心来源均包含 `exam_policy.md` |
| `total_latency_ms` | `22952.16` | `6725.16` | 下降 `16227.00 ms` |
| `llm_time_ms` | `7206.21` | `6653.69` | 记录到波动，本次不作为主要优化目标 |
| `tool_time_ms` | `15714.98` | `36.60` | 从秒级降至毫秒级 |
| `retrieval_time_ms` | `15714.98` | `36.57` | 下降 `15678.41 ms`，约 `99.8%` |
| `prompt_tokens` | `11620` | `11821` | After 增加 `201` |
| `completion_tokens` | `464` | `467` | After 增加 `3` |
| `total_tokens` | `12084` | `12288` | After 增加 `204` |
| `error_message` | `-` | `-` | 无错误 |

### 如果我因为生病缺考怎么办？

| Field | Before | After | Observation |
| --- | --- | --- | --- |
| `retrieved_docs` | `leave_policy.md (chunk-0002)`、`leave_policy.md (chunk-0003)`、`exam_policy.md (chunk-0002)`、`exam_policy.md (chunk-0003)`、`leave_policy.md (chunk-0001)` | `leave_policy.md (chunk-0003)`、`leave_policy.md (chunk-0002)`、`exam_policy.md (chunk-0002)`、`exam_policy.md (chunk-0003)`、`leave_policy.md (chunk-0001)` | 来源集合保持，均包含 `leave_policy.md` 与 `exam_policy.md` |
| `total_latency_ms` | `26656.18` | `8529.20` | 下降 `18126.98 ms` |
| `llm_time_ms` | `8586.53` | `8452.54` | 基本仍由模型生成阶段占据主要耗时 |
| `tool_time_ms` | `18037.67` | `39.85` | 从秒级降至毫秒级 |
| `retrieval_time_ms` | `18037.67` | `39.85` | 下降 `17997.82 ms`，约 `99.8%` |
| `prompt_tokens` | `13613` | `13818` | After 增加 `205` |
| `completion_tokens` | `569` | `582` | After 增加 `13` |
| `total_tokens` | `14182` | `14400` | After 增加 `218` |
| `error_message` | `-` | `-` | 无错误 |

### Overlapping-query Aggregate

下表只计算两条前后均存在的问题，因此比整体 Summary 更适合衡量本次缓存改动的效果。

| Metric | Before Average | After Average | Reduction |
| --- | ---: | ---: | ---: |
| `retrieval_time_ms` | `16876.33` | `38.21` | 下降 `16838.12 ms`，约 `99.8%` |
| `total_latency_ms` | `24804.17` | `7627.18` | 下降 `17176.99 ms`，约 `69.3%` |

## 5. Retrieval Quality Check

缓存改变的是资源初始化复用方式，而不是查询、chunk、embedding 策略或回答 prompt。原始记录中的来源信息显示，本次可观察样本没有出现明显召回退化：

| Query | Before Retrieved Sources | After Retrieved Sources | Check |
| --- | --- | --- | --- |
| 考试作弊有什么后果？ | 包含 `exam_policy.md` | 包含 `exam_policy.md` | 核心考试制度来源保持 |
| 如果我因为生病缺考怎么办？ | 包含 `leave_policy.md` 与 `exam_policy.md` | 包含 `leave_policy.md` 与 `exam_policy.md` | 跨制度来源保持 |
| 宿舍晚归会怎么处理？ | `-`，无可比 before 样本 | 包含 `dormitory_policy.md` | After 结果符合该问题预期来源 |

这一检查只能说明 benchmark 中已观察的来源未明显退化；更系统的召回质量保护仍应依靠黄金问题集测试与后续扩大样本评估。

## 6. Key Findings

1. 本次优化的主要收益集中在 `tool_time_ms` 与 `retrieval_time_ms`：两条重合问题的平均 `retrieval_time_ms` 从约 `16876.33 ms` 降到约 `38.21 ms`，下降约 `99.8%`。
2. RAG retriever cache 将检索阶段从秒级优化到了毫秒级，说明此前重复初始化 embedding / Chroma / retriever 是显著的不必要成本。
3. LLM 生成时间和 token 消耗不是本次优化目标。本次没有调整 prompt、回答流程或模型，因此不能将 token 波动解释为缓存效果。
4. `total_latency_ms` 已明显下降，但仍受 LLM 生成耗时波动影响：同题平均总耗时下降约 `69.3%`，并未像 retrieval 阶段一样接近归零。
5. `retrieved_docs` 所显示的关键来源在可比较样本中保持稳定，缓存提升性能的同时未在这些记录中表现出召回来源退化。

## 7. Limitations

1. 本次 benchmark 不是完整五题的 request-level 对齐：before 只有 `2` 条 request，after 有 `3` 条 request，且两份文件均混有 child event。
2. 本文只对“考试作弊有什么后果？”与“如果我因为生病缺考怎么办？”两条重合问题计算严格前后下降；额外新增问题不得用于推导 before/after 提升比例。
3. `before` 文件中的 git commit hash 可能反映导出脚本所在 commit，而非 trace 生成时的历史业务实现版本。
4. 后续可优化 `export_benchmark_run.py`，支持仅导出最近 `N` 条 request-level trace，从而直接构造完全对齐的问题集对比。
5. 后续可在 benchmark 输出中显式记录 `rag_cache_hit` / `rag_load_time_ms`，进一步区分冷启动、缓存命中和真实向量检索耗时。

## 8. Interview Talking Points

在 RAG 性能优化中，我先区分了必要成本和不必要成本：必要成本是每次用户提出新 query 后都必须执行真实检索，不必要成本是每次请求都重复初始化 embedding、Chroma 和 retriever。基于 Trace，我发现检索链路原本有明显秒级耗时，于是只对初始化资源做缓存，保留每次 `retriever.invoke(query)` 和既有回答逻辑。对于两条严格同题样本，平均 `retrieval_time_ms` 从约 `16876.33 ms` 降至约 `38.21 ms`，下降约 `99.8%`，实现了从秒级到毫秒级的优化。同时，我通过 `source_list` / `retrieved_docs` 对比召回来源：考试作弊问题仍包含 `exam_policy.md`，生病缺考问题仍包含 `leave_policy.md` 与 `exam_policy.md`，说明在现有样本中性能提升没有以明显召回质量下降为代价。
