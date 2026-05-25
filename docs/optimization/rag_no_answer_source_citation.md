# Phase 3.2: RAG No-answer and Source Citation

## 1. Why RAG Needs No-answer

校园制度回答属于高可信度要求场景。对于请假、奖学金、宿舍管理和考试纪律等问题，模型如果在没有检索依据时补全流程、电话、办公室或网址，会比直接说明“不确定”更危险。

Phase 3.2 的目标是让工具层先判断当前检索结果是否足以支持回答：

- 有有效依据时，输出检索内容并附带可检查的来源。
- 没有文档或结果明显低相关时，直接输出 no-answer。
- 不改变向量库、chunk、embedding、召回算法或前端展示。

## 2. Why Prompt Alone Is Not Enough

Prompt 可以要求模型谨慎回答，但模型仍可能在空上下文、无关上下文或长对话干扰下生成貌似合理的制度结论。将 no-answer 前置到工具层有三个优势：

1. 工具输出本身已经表达“不可据此回答”，模型收到的不是空字符串。
2. `Database_Search` 与 `query_campus_policy` 两个入口遵循同一可信度边界。
3. Trace 可以直接记录是否由检索质量触发拒答，而不是事后猜测模型为什么没有回答。

`rag_assistant.py` 同时做了轻量 instructions 补充：工具返回 no-answer 时不得补充确定性制度结论；工具返回来源时，最终回答必须保留来源与 `chunk_id`。

## 3. Tool-level No-answer Design

### Trigger Conditions

工具层 no-answer 在以下情况触发：

| 条件 | 行为 |
| --- | --- |
| retriever 返回空列表 | 返回“当前知识库中没有找到明确依据” |
| 文档内容为空或过短 | 判为低相关并返回 no-answer |
| 问题中的关键制度词与文档内容 / `source` 没有交集 | 判为低相关并返回 no-answer |

轻量相关性判断由 `is_low_relevance(query, documents)` 完成。它优先检查“请假 / 奖学金 / 宿舍 / 考试”等领域词，避免仅凭“流程 / 材料”等通用词误放行无关文档；当问题没有明确领域词时，才使用通用词作为最低限度的依据检查。该判断只执行可测试的字符串规则，不加载 rerank 模型，也不依赖不稳定的 similarity score。

### No-answer Content

两个工具都会输出明确约束：

- 当前知识库中没有找到明确依据。
- 建议以学校官方通知或辅导员答复为准。
- 不得编造具体制度、电话、办公室、网址或其他知识库外信息。

`query_campus_policy_func()` 保留既有结构化政策回答版式；`database_search_func()` 返回面向 RAG Agent 的检索结论、说明与来源区。这样既能维持现有入口职责，也不会将空 context 继续交给模型自行判断。

## 4. Source Citation Design

有效检索结果必须保留来源定位信息，当前引用字段完全来自已有 metadata，不新增或猜测不存在的 section / heading：

```markdown
### 来源
- leave_policy.md | leave_policy.md::chunk-0001 | /kb/leave_policy.md
- exam_policy.md | exam_policy.md::chunk-0003
```

| 字段 | 来源 | 作用 |
| --- | --- | --- |
| `source` | chunk metadata | 标明制度文档文件名 |
| `chunk_id` | chunk metadata | 定位用于回答的文档切片 |
| `path` | metadata 存在时展示 | 辅助开发和本地核验 |

`Database_Search` 在格式化检索上下文后追加 `### 来源`；`query_campus_policy` 在其 `## 来源文档` 区中按相同的 `source | chunk_id | path` 方式展示依据。

## 5. Trace Enhancements

RAG retrieval 子事件以及当前请求聚合记录新增 / 复用了以下观测字段：

| 字段 | 说明 |
| --- | --- |
| `is_empty_result` | retriever 是否没有返回文档 |
| `is_low_relevance` | 工具层轻量规则是否判断结果不足以支持回答 |
| `no_answer_triggered` | 工具是否返回 no-answer |
| `returned_doc_count` | 实际检索返回的文档数量；低相关时仍可记录被拒绝的文档 |
| `source_list` | 检索结果中的来源文件列表 |
| `chunk_id_list` | 检索结果中的 chunk 列表 |
| `retrieved_docs` | 来源、路径与 chunk 的结构化明细 |

这里刻意区分了“检索为空”和“检索到了文档但判断为低相关”：两者都会拒答，但后续优化方向不同。

## 6. Current Boundary and Future Retrieval Work

当前低相关判断是保守、轻量、可解释的基线规则，它不能解决所有语义等价表达，也不能替代检索质量评估。Phase 3.2 明确不包含：

- BM25 或 Hybrid Retrieval。
- rerank 模型或 similarity score 阈值调参。
- Markdown 标题切分、chunk 策略与 metadata 扩展。
- 前端引用卡片或 Trace 展示。

后续可以在黄金问题集和 no-answer 问题集都建立后，单独评估 rerank / hybrid retrieval 是否同时改善召回与拒答准确性。

## 7. Test Coverage

| 测试文件 | 覆盖范围 |
| --- | --- |
| `tests/agents/test_database_search_tool.py` | 空结果拒答、低相关拒答、有效结果来源与 chunk、既有异常行为 |
| `tests/agents/test_campus_policy_tool.py` | 默认政策工具的结构化 no-answer、引用与拒答 Trace |
| `tests/agents/test_rag_assistant.py` | RAG graph 工具闭环、no-answer 工具结果进入模型、instructions 约束 |
| `tests/agents/test_rag_cache.py` | 缓存后 Trace 中低相关与 no-answer 标记不丢失 |
| `tests/rag/test_retrieval_quality.py` | 黄金问题仍召回期望制度来源 |

## 8. Benchmark Follow-up

no-answer 优化的 benchmark 需要同时观察正确拒答与正常召回，不应只看延迟。建议分别采集：

| 问题类别 | 示例 | 观察指标 |
| --- | --- | --- |
| 有依据问题 | 考试作弊有什么后果？ | `no_answer_triggered=false`、来源正确、延迟稳定 |
| 空召回问题 | 知识库不存在的制度问题 | `is_empty_result=true`、`no_answer_triggered=true` |
| 低相关问题 | 宿舍问题却召回课程介绍 | `is_low_relevance=true`、`no_answer_triggered=true` |

正式导出推荐只取 request-level trace：

```bash
.venv/bin/python scripts/export_benchmark_run.py \
  --name after_rag_no_answer_request_level \
  --request-last 5
```

## 9. Interview Talking Points

我在 RAG 优化中把“回答可信度”落实到了工具边界，而不是只依赖 prompt 提醒模型不要幻觉。向量检索为空或命中内容与制度问题明显不相关时，工具会直接返回 no-answer，明确提示以官方通知或辅导员答复为准，并禁止编造电话、办公室和网址；当存在有效依据时，输出必须携带 `source` 与 `chunk_id`，让回答可以回溯到具体片段。同时我将 `is_low_relevance` 和 `no_answer_triggered` 纳入 Trace，并保留黄金问题召回测试，为后续引入 rerank 或 Hybrid Retrieval 建立可比较的可信度基线。
