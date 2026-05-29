# Skill Evaluation Benchmark

> 状态：已完成 | 关联文件：`scripts/evaluate_skills.py`、`data/evaluation/skill_eval_cases.json`

## 1. 为什么需要 Skill Evaluation Benchmark

Campus AI Agent 的 Skill Layer 依赖两个组件协同工作：

1. **Router**（`route_query`）：将用户自然语言问题分类为 `RouteIntent`
2. **SkillRegistry**：将 `RouteIntent` 映射到具体的 Skill（course_query、event_query、policy_qa、study_plan）

这两个组件的正确性直接影响快路径命中率。Benchmark 提供了一组固定问题集，可以在每次代码变更后快速验证"路由有没有退化""Skill 匹配有没有错位"，无需启动 FastAPI 服务或调用 LLM。

## 2. 评估对象

| 对象 | 说明 |
|---|---|
| `route_query` | 关键词匹配的分类准确性 |
| `SkillRegistry` | intent → Skill 的映射正确性 |
| `expected_skill` | 给定问题是否匹配到正确的 Skill |
| `expected_fast_path` | 给定问题是否应该走快路径 |

## 3. 为什么不调用 LLM / RAG / FastAPI

- **LLM**：评估 Router + Registry 不需要模型推理。调用 LLM 会增加延迟、token 消耗，且引入非确定性。
- **RAG**：本 benchmark 只评估路由层，不评估工具执行质量。RAG 检索质量由 `tests/rag/` 下的专项测试覆盖。
- **FastAPI**：Router 和 Registry 都是纯 Python 函数，可以直接调用，无需网络开销。

## 4. 指标说明

| 指标 | 说明 | 期望值 |
|---|---|---|
| `route_accuracy` | `predicted_intent == expected_intent` 的比例 | ≥ 90% |
| `skill_accuracy` | `predicted_skill == expected_skill` 的比例 | ≥ 90% |
| `fast_path_accuracy` | `predicted_fast_path == expected_fast_path` 的比例 | ≥ 90% |
| `fast_path_hit_rate` | 预测为 fast_path=True 的比例 | ≈ 期望比例 |
| `fallback_rate` | 预测为 fast_path=False 的比例 | 越低越好，但必须包含 general/unknown 类问题 |

## 5. 如何运行

```bash
# 默认运行
uv run python scripts/evaluate_skills.py

# 自定义 cases 文件
uv run python scripts/evaluate_skills.py --cases data/evaluation/skill_eval_cases.json

# CI 门禁：route_accuracy 低于 0.8 则失败
uv run python scripts/evaluate_skills.py --fail-under-route-accuracy 0.8 --fail-under-skill-accuracy 0.8
```

## 6. 如何解读报告

报告输出到 `docs/optimization/benchmark_runs/`，包含 JSON 和 Markdown 两个文件。

**Markdown 报告结构**：

- **Section 1 Summary**：总览指标
- **Section 2 Per-category**：按 course / event / policy / study / general 分类统计
- **Section 3 Per-skill**：每个 Skill 的期望数和实际命中数
- **Section 4 Failure Cases**：错误样例清单（包含 expected vs predicted 对比）
- **Section 5 Case-level**：逐条结果表

如果所有指标 100%，报告显示 "No failures."

## 7. 局限性

| 局限 | 说明 |
|---|---|
| 只评估路由和 Skill 匹配 | 不评估工具真实执行质量（RAG 检索精度、学习计划内容质量等） |
| 不评估 LLM 回答质量 | 本 benchmark 跳过 LLM，无法评估 Agent 路径下的回答 |
| 固定问题集 | 21 条 case 覆盖了主要场景，但不可能穷举所有用户表达 |
| 关键词 Router 的固有限制 | 例如"今天天气怎么样？"中的"今天"会命中 COURSE 关键词。这是 Router 本身的局限，不是 Skill Layer 的问题 |

## 8. 后续扩展

- **接入真实 fast path execution**：在 benchmark 中实际调用 handler，验证工具执行不崩溃
- **接入 Trace JSONL 汇总**：从生产 trace 中自动提取问题集，覆盖真实用户表达
- **统计 avg_latency_by_skill**：按 Skill 统计平均延迟
- **统计 zero_llm_token_rate**：统计快路径节省的 token 比例
