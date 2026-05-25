# RAG Token Budget Optimization Comparison

## 1. Background

Hybrid Retrieval 通过 Vector + BM25 + RRF 提高了校园制度强关键词问题的召回稳定性，但召回到的候选 chunk 不应无边界进入 LLM 上下文。过多或过长 evidence 会增加 prompt token 成本，也可能增加生成阶段的噪声。

Phase 3.5 的目标是控制实际送入模型的 RAG context，同时保留 `source` / `chunk_id` 以支撑可追溯回答。本对比关注 token 变化与来源保留情况；总延迟受模型生成波动影响，并非本阶段唯一评价标准。

## 2. Benchmark Setup

对比文件：

- Before: `docs/optimization/benchmark_runs/2026-05-25_before_rag_token_budget_same_questions.md`
- After: `docs/optimization/benchmark_runs/2026-05-25_after_rag_token_budget_same_questions.md`

| Item | Before | After |
| --- | --- | --- |
| Git commit hash | `c37f3ca` | `7c9cc28` |
| Model | `deepseek-chat` | `deepseek-chat` |
| Agent | `research-assistant` | `research-assistant` |
| Selection mode | `request-last` | `request-last` |
| Requested request count | `5` | `5` |
| Actual request count | `5` | `5` |
| Child events included in sample | `0` | `0` |
| Skipped child events | `4` | `4` |

严格比较以下五个相同 RAG 问题：

1. 请假流程是什么？
2. 挂科了还能申请奖学金吗？
3. 宿舍晚归会怎么处理？
4. 考试作弊有什么后果？
5. 如果我因为生病缺考怎么办？

两份导出文件均未展示 `context_docs_count`、`context_chars`、`estimated_context_tokens` 或 `dropped_context_docs_count` 列，因此本文对这些字段标为 `-`，不推断其数值。

## 3. Before vs After Summary

| Metric | Before | After | Change |
| --- | ---: | ---: | ---: |
| `average_prompt_tokens` | `10809.60` | `10680.60` | 下降 `129.00` (`1.2%`) |
| `average_completion_tokens` | `498.60` | `432.60` | 下降 `66.00` (`13.2%`) |
| `average_total_tokens` | `11308.20` | `11113.20` | 下降 `195.00` (`1.7%`) |
| `average_total_latency_ms` | `11274.15` | `9681.98` | 下降 `1592.17 ms` (`14.1%`) |
| `average_llm_time_ms` | `7706.12` | `6015.14` | 下降 `1690.98 ms` (`21.9%`) |
| `average_retrieval_time_ms` | `66.99` | `65.61` | 下降 `1.38 ms` (`2.1%`) |

本次样本中，平均 `prompt_tokens` 与平均 `total_tokens` 均下降，但幅度较温和。该结果说明 token budget 在当前五题上没有增加上下文成本，并出现了小幅收敛；由于导出文件未包含 context budget 细分字段，不能仅凭本表量化具体裁剪了多少 evidence。

平均总延迟在本次运行中下降，但本阶段主要目标是控制 prompt/context token。LLM 输出长度与生成速度会波动，因此不能将一次 latency 变化简单归因于 token budget，也不能将总延迟未显著下降视为失败。

## 4. Per-query Comparison

所有五条记录在 before 与 after 中均为 `route=stream`、`tool_calls=query_campus_policy`、`error_message=-`。

### Token and Latency Results

| Query | Prompt Tokens Before | Prompt Tokens After | Change | Total Tokens Before | Total Tokens After | Change | Total Latency Before (ms) | Total Latency After (ms) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 请假流程是什么？ | `6186` | `6184` | `-2` | `6578` | `6544` | `-34` | `24323.23` | `23782.24` |
| 挂科了还能申请奖学金吗？ | `8389` | `8351` | `-38` | `8809` | `8740` | `-69` | `6978.20` | `6183.56` |
| 宿舍晚归会怎么处理？ | `10678` | `10605` | `-73` | `11179` | `11077` | `-102` | `7786.88` | `5769.30` |
| 考试作弊有什么后果？ | `13119` | `12987` | `-132` | `13690` | `13416` | `-274` | `8180.06` | `5523.10` |
| 如果我因为生病缺考怎么办？ | `15676` | `15276` | `-400` | `16285` | `15789` | `-496` | `9102.38` | `7151.71` |

五个问题的 `prompt_tokens` 均未上升，其中“如果我因为生病缺考怎么办？”下降最多，为 `400` tokens。

### Runtime Fields

| Query | LLM Time Before (ms) | LLM Time After (ms) | Retrieval Time Before (ms) | Retrieval Time After (ms) | Context Budget Fields |
| --- | ---: | ---: | ---: | ---: | --- |
| 请假流程是什么？ | `6774.77` | `5766.02` | `187.43` | `172.66` | `-` |
| 挂科了还能申请奖学金吗？ | `6900.52` | `6093.57` | `37.34` | `53.46` | `-` |
| 宿舍晚归会怎么处理？ | `7716.53` | `5699.00` | `37.86` | `32.84` | `-` |
| 考试作弊有什么后果？ | `8108.42` | `5442.42` | `35.84` | `32.89` | `-` |
| 如果我因为生病缺考怎么办？ | `9030.35` | `7074.70` | `36.47` | `36.21` | `-` |

### Retrieved Sources and Chunks

| Query | Before `retrieved_docs` | After `retrieved_docs` | Source / Chunk Preservation |
| --- | --- | --- | --- |
| 请假流程是什么？ | `leave_policy.md::chunk-0010`, `leave_policy.md::chunk-0005`, `exam_policy.md::chunk-0008`, `leave_policy.md::chunk-0001`, `student_handbook.md::chunk-0008` | Same five source/chunk entries | 保留 |
| 挂科了还能申请奖学金吗？ | `scholarship_policy.md::chunk-0009`, `::chunk-0005`, `::chunk-0012`, `::chunk-0010`, `::chunk-0013` | 相同五个 `scholarship_policy.md` chunks，顺序调整 | 保留 |
| 宿舍晚归会怎么处理？ | `dormitory_policy.md::chunk-0004`, `::chunk-0012`, `::chunk-0010`, `::chunk-0009`, `::chunk-0003` | Same five source/chunk entries | 保留 |
| 考试作弊有什么后果？ | `exam_policy.md::chunk-0010`, `::chunk-0008`, `::chunk-0003`, `::chunk-0009`, `scholarship_policy.md::chunk-0006` | Same five source/chunk entries | 保留 |
| 如果我因为生病缺考怎么办？ | `exam_policy.md::chunk-0005`, `leave_policy.md::chunk-0009`, `exam_policy.md::chunk-0012`, `exam_policy.md::chunk-0011`, `leave_policy.md::chunk-0004` | `exam_policy.md::chunk-0011`, `leave_policy.md::chunk-0009`, `leave_policy.md::chunk-0004`, `leave_policy.md::chunk-0012`, `exam_policy.md::chunk-0006` | 核心来源 `exam_policy.md` 与 `leave_policy.md` 均保留 |

## 5. Retrieval Quality Check

基于导出的 `retrieved_docs`，after 中核心预期制度来源没有明显退化：

| Query | Expected Source | After Evidence |
| --- | --- | --- |
| 请假流程是什么？ | `leave_policy.md` | 包含多个 `leave_policy.md` chunks |
| 挂科了还能申请奖学金吗？ | `scholarship_policy.md` | 五个结果均来自 `scholarship_policy.md` |
| 宿舍晚归会怎么处理？ | `dormitory_policy.md` | 五个结果均来自 `dormitory_policy.md` |
| 考试作弊有什么后果？ | `exam_policy.md` | 包含多个 `exam_policy.md` chunks |
| 如果我因为生病缺考怎么办？ | `exam_policy.md` 或 `leave_policy.md` | 两类来源均保留 |

两份 benchmark 都保留了 `source` 与 `chunk_id` 信息；after 中没有出现错误信息。本文只能说明这五个样本中的来源召回保持稳定，不能替代更大问题集上的严格质量评估。

## 6. Key Findings

1. `average_prompt_tokens` 从 `10809.60` 降至 `10680.60`，平均减少 `129.00` tokens。
2. `average_total_tokens` 从 `11308.20` 降至 `11113.20`，平均减少 `195.00` tokens。
3. 五个同题样本的 `prompt_tokens` 全部下降或基本持平，没有因引入预算而增加输入 token。
4. `source` / `chunk_id` 在 after 记录中继续存在，五题的核心制度来源均保留。
5. 本阶段优化重点是控制进入 LLM 的 evidence context，而非优化检索耗时；`average_retrieval_time_ms` 基本处于相近范围。
6. 本轮 `average_total_latency_ms` 下降 `1592.17 ms`，但仍应谨慎解释：总耗时受 LLM 生成波动、completion 长度及运行环境影响。

## 7. Limitations

- 两份 benchmark 没有导出 `context_docs_count`、`context_chars`、`estimated_context_tokens` 与 `dropped_context_docs_count`，因此本文不能展示实际裁剪比例。
- 当前 token budget 使用轻量字符/token 估算策略，而不是模型专属 tokenizer。
- 五题样本能够验证核心来源保留，但不足以覆盖所有复杂制度查询和跨文档回答场景。
- 后续可在 benchmark 导出中加入 context budget 字段，并使用 `tiktoken` 或目标模型 tokenizer 对预算与真实 `prompt_tokens` 做更精确校准。

## 8. Interview Talking Points

在完成 Hybrid Retrieval 后，我发现提升召回并不意味着可以把所有候选片段直接塞入模型上下文，否则会继续承担不必要的 prompt token 成本。于是我在不改变检索排序和 no-answer 安全逻辑的前提下，引入了 RAG token budget：只将排名靠前且在预算内的 evidence 交给模型，同时保留 `source` 与 `chunk_id` 以保证回答可追溯。通过相同五个制度问题的 request-level benchmark，对比后平均 `prompt_tokens` 从 `10809.60` 降到 `10680.60`，平均 `total_tokens` 从 `11308.20` 降到 `11113.20`；五题核心制度来源仍然保留。这个结果说明优化方向不是牺牲检索可信度换 token，而是在保证来源可核验的前提下控制上下文成本。
