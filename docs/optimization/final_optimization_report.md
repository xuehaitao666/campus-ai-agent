# Campus AI Agent Final Optimization Report

## 1. Project Overview

Campus AI Agent 是一个面向校园服务场景的 AI Agent 项目，基于 FastAPI、Streamlit、LangGraph 与本地知识库实现统一问答入口。当前核心能力包括：

- 课程安排查询：按星期、时间段或课程名称查询本地课程表。
- 校园活动查询：按关键词、日期范围、活动类型和人群检索活动。
- 学习计划生成：结合学生画像与课程时间形成规则化学习安排。
- 校园制度问答：围绕请假、奖学金、宿舍、考试纪律等制度文档进行 RAG 检索与回答。
- 多轮会话：通过 thread 级 checkpoint 恢复历史上下文。
- 工具复用：通过只读 MCP Server Adapter 向外部 Agent / MCP Client 暴露校园查询工具。

本轮优化的主线不是继续堆叠功能，而是让系统具备可观测、可评估、可信回答、成本受控、故障可回退和能力可复用的工程基础。

## 2. Initial Problems

在优化前，项目已经能够完成多种校园任务，但存在以下工程问题：

| 问题 | 影响 |
| --- | --- |
| 功能较多但缺少统一优化主线 | 很难解释性能瓶颈、改动收益与系统演进顺序 |
| 缺少 Trace 与可提交 benchmark | 优化前后不能基于同题数据做客观比较 |
| 课程、活动等确定性查询仍走完整 LLM 链路 | 引入不必要的模型耗时与 token 成本 |
| RAG 请求重复初始化 embedding / Chroma / retriever | 制度问答检索阶段出现明显冷初始化开销 |
| RAG 缺少 no-answer 边界 | 没有依据或低相关时存在生成确定性制度结论的风险 |
| Chunk 与 metadata 不够结构化 | 来源只能粗略定位文件，不利于引用、评估和融合检索 |
| 单一路径向量检索对强制度关键词不够稳定 | “挂科 + 奖学金”等词面明确问题缺少关键词通道支持 |
| 检索候选可能过多进入模型上下文 | Prompt token 成本随 evidence 增长 |
| 外部模型调用缺少统一 timeout / retry / fallback | 模型瞬时故障会直接导致请求失败，且难以追踪 |
| 多轮历史可能持续增长 | 长会话模型上下文与 token 成本缺少上限 |
| API 返回主要依赖文本内容 | 来源、指标与 fallback 状态难以被客户端结构化消费 |
| 工具只能在项目主链路内使用 | 外部 Agent 缺少标准化、只读的复用出口 |

## 3. Optimization Roadmap

| Phase | 优化内容 | 解决的问题 | 涉及模块 | 验证方式 | 面试亮点 |
| --- | --- | --- | --- | --- | --- |
| Phase 1 | Agent Trace + Benchmark Run | 缺少可观测性与优化证据 | `core/tracing.py`, `service.py`, benchmark 导出脚本 | Trace JSONL、benchmark Markdown、测试 | 先度量再优化 |
| Phase 2.1 | Rule-based Router | 高确定性意图无低成本识别入口 | `core/router.py` | 路由纯函数测试 | 可解释路由与 fallback 边界 |
| Phase 2.2-2.4 | Course/Event Fast Path + 模板化响应 | 查表类请求仍耗费 LLM | `service.py`, query parsers, response templates | 同题课程 benchmark、service 测试 | 确定性请求零 token 响应 |
| Phase 3.1 | RAG Retriever Cache | RAG 资源重复初始化 | `agents/tools.py` | cache 测试、同题 benchmark | 区分必要检索与不必要初始化 |
| Phase 3.1.1 | Request-level Benchmark 导出 | child event 污染汇总样本 | `scripts/export_benchmark_run.py` | 导出脚本测试 | 数据对比口径治理 |
| Phase 3.2 | no-answer + source citation | 无依据时幻觉风险、来源不可核验 | `agents/tools.py`, `rag_assistant.py` | 空召回/低相关/引用测试 | 把可信度约束放到工具边界 |
| Phase 3.3 | 文档清洗 + heading-aware chunking + metadata | 索引语义边界与来源定位不足 | `rag/document_cleaner.py`, `rag/chunking.py`, build script | 建库与 retrieval quality 测试 | 在线质量从离线数据治理开始 |
| Phase 3.4 | Hybrid Retrieval: BM25 + Vector + RRF | 强关键词召回稳定性不足 | `rag/hybrid_retriever.py`, `agents/tools.py` | Vector/Hybrid 黄金问题集 | 用 RRF 融合异构检索通道 |
| Phase 3.5 | Prompt 拆分 + RAG Token Budget | Evidence context 成本缺少控制 | `core/token_budget.py`, `prompts/rag_prompts.py` | 同题 token benchmark、budget 测试 | 在保留来源下控制上下文成本 |
| Phase 4.1 | Model timeout / retry / fallback | 外部模型故障缺少恢复策略 | `core/settings.py`, `core/llm.py`, model fallback helper | fake model 失败路径测试 | 可配置、可追踪的一次降级 |
| Phase 4.2 | History 接口优化 + 上下文裁剪 | 历史接口粒度不足、对话上下文无限增长 | `schema.py`, `service.py`, `core/history.py` | 多轮历史/裁剪 Trace 测试 | 存完整历史，送模型有限窗口 |
| Phase 4.3 | `ChatMessage.custom_data` 扩展 | API 缺少结构化 evidence 与 metrics | `schema.py`, `service/utils.py`, `service.py` | 序列化、invoke、SSE 测试 | 保持兼容的结构化响应演进 |
| Phase 5.1 | Campus Tools MCP Server Adapter | 外部系统难以标准复用工具 | `mcp_server/` | MCP adapter 一致性与错误测试 | 不重构主链路的协议化开放 |

## 4. Key Technical Optimizations

### Trace + Benchmark

Phase 1 在 `/invoke` 与 `/stream` 请求上建立 Trace，关联 `trace_id`、`run_id`、会话、Agent、模型、工具调用、RAG 文档、耗时、token 与异常信息，并将记录写为 JSONL。之后新增 benchmark 导出脚本，把最近 Trace 汇总为可提交 Markdown。

RAG 优化阶段进一步发现原始 `--last` 可能混入 `rag_retrieval` child event，因此导出机制增加 request-only / request-last 选择模式。正式前后对比可以只统计 request-level 数据，避免把子事件当成用户请求。

这一阶段的价值在于：后续优化不再依赖印象，而是有固定问题集、可追踪记录和一致指标口径。

### Fast Path

Phase 2 为确定性高、数据源固定的课程与活动查询增加轻量路径：

1. Rule-based Router 识别 `course_schedule` 与 `campus_event` 意图。
2. Parser 从问题中提取课程或活动筛选条件。
3. 能明确执行时，service 直接调用原有 native tool。
4. 使用 Markdown 模板返回稳定响应，不调用 LLM。
5. 无法解析或非目标意图时，继续 fallback 到原 Agent 链路。

这一设计没有替换 Agent，也没有复制课程/活动业务逻辑；优化的是 LLM 参与确定性查表请求的必要性。

### RAG Retriever Cache

Phase 3.1 明确区分了 RAG 的两类成本：

- 必要成本：每个新 query 都必须执行实际检索。
- 不必要成本：每次请求重复初始化 embedding、Chroma 与 retriever。

实现使用进程内缓存复用 embedding 与 retriever，并提供 `clear_rag_cache()` 供知识库重建或测试隔离时清理缓存。查询本身仍每次执行，不改变用户问题对应的检索行为。

### no-answer + source citation

校园制度属于高可信回答场景。Phase 3.2 将 no-answer 放在工具层而不只依赖 prompt：

- 空检索结果直接返回“当前知识库中没有找到明确依据”。
- 内容过短或制度关键词完全不匹配时，按低相关结果拒答。
- no-answer 明确建议以学校官方通知或辅导员答复为准，并禁止编造制度细节、电话、办公室和网址。
- 有有效证据时，保留 `source` 与 `chunk_id` 来源引用。

工具层约束意味着即便模型存在生成倾向，也不会收到空白或明显无关的上下文后自由补制度结论。

### Metadata + Heading-aware Chunking

Phase 3.3 将优化延伸到离线建库：

- 对 Markdown 做保守清洗：统一换行、删除行尾空格、压缩过量空行，同时保留标题、列表与表格。
- 先依据 `#` / `##` / `###` 标题形成章节级片段，长章节再继续固定长度切分。
- Chunk metadata 增强为 `source`、`path`、`chunk_id`、`section`、`heading_path` 与 `policy_type`。

这让回答可以定位到制度章节，为来源展示、检索质量分析和后续融合检索提供结构化基础。

### Hybrid Retrieval

Phase 3.4 为制度强关键词场景增加 BM25 通道：

- Vector retrieval 负责语义相似召回。
- BM25 使用轻量中文 bigram 处理“请假”“奖学金”“宿舍”“晚归”“作弊”等明确关键词。
- RRF 使用排名而非原始分数融合两路结果，避免向量分数与 BM25 分数尺度不一致。
- 结果按 `chunk_id` 去重，并记录 `retrieval_source`、`hybrid_score`、`vector_rank` 与 `bm25_rank`。

原 no-answer 与来源引用逻辑继续位于融合结果之后，因此增强召回的同时保留可信回答边界。

### Token Budget

Hybrid Retrieval 提升召回候选后，并不应将所有 evidence 无限制传入 LLM。Phase 3.5 增加：

- 拆分后的 RAG prompt 约束；
- 按当前排序保留高优先级 evidence 的上下文选择；
- 默认最多 `5` 个文档、总 context `6000` 字符、单 chunk `1500` 字符；
- `context_docs_count`、`context_chars`、`estimated_context_tokens` 与 `dropped_context_docs_count` Trace 指标。

预算只控制进入模型的有效上下文，不改变检索排序，也不裁剪 no-answer 的关键安全提示。

### Model Fallback

Phase 4.1 为模型层增加可靠性边界：

- 统一配置 `MODEL_TIMEOUT_SECONDS`、`MODEL_MAX_RETRIES` 与 `MODEL_TEMPERATURE`。
- 通过 `ENABLE_MODEL_FALLBACK` 和 `FALLBACK_MODEL` 显式开启候补模型。
- 主模型失败后最多尝试一次不同的 fallback model。
- 相同模型不会循环调用，候补失败会返回稳定错误。
- Trace 记录 primary/fallback model、触发状态、错误类型和尝试次数。

该策略保持保守：默认关闭 fallback，不进行动态模型评分或无边界重试。

### History Trimming

Phase 4.2 区分了“历史应可恢复”与“模型必须读取全部历史”：

- `/history` 新增 `agent_id`、`limit` 与 `include_tools`。
- `HISTORY_MAX_MESSAGES` 默认限制送入模型的最近非 system 消息数为 `20`。
- System message 与最新用户输入始终保留。
- Checkpoint 中的完整历史不被删除。
- Trace 记录裁剪前消息数、裁剪数量和配置上限。

这一策略先控制多轮 token 增长，同时避免过早引入摘要正确性或长期记忆召回的新风险。

### `custom_data`

Phase 4.3 使用 `ChatMessage.custom_data` 建立兼容的结构化输出通道，当前可携带：

- `retrieved_docs`
- `source_citations`
- `metrics`
- `tool_execution`
- `model_fallback`

回答正文与原有 SSE 外层协议保持不变；现有前端仍可只显示 `content`，未来前端可选择展示引用、性能指标或 fallback 状态。该方式避免了从 Markdown 正文反解析结构化证据。

### MCP Server Adapter

Phase 5.1 增加旁路、只读 MCP server `campus-ai-agent-tools`，暴露：

| MCP Tool | Native Function |
| --- | --- |
| `get_course_schedule` | `get_course_schedule_func` |
| `get_campus_events` | `get_campus_events_func` |
| `query_campus_policy` | `query_campus_policy_func` |

Adapter 不复制业务逻辑，仅封装 JSON 可序列化结果、`transport="mcp"`、`latency_ms` 与安全错误 envelope。主 FastAPI、Streamlit 与 LangGraph 流程没有改为强制使用 MCP。

## 5. Quantitative Results

### Course Fast Path: Same Five Questions

来源：`course_fast_path_comparison.md`，基于五个相同课程问题的 before / after benchmark。

| 指标 | Before | After | 变化 |
| --- | ---: | ---: | ---: |
| 平均 `total_latency_ms` | `3535.00 ms` | `1.19 ms` | 下降 `3533.81 ms`，约 `99.97%` |
| 平均 `llm_time_ms` | `3502.92 ms` | `0.00 ms` | 下降 `3502.92 ms` |
| 平均 `prompt_tokens` | `5329.00` | `0.00` | 节省 `5329.00` |
| 平均 `completion_tokens` | `190.00` | `0.00` | 节省 `190.00` |
| 平均 `total_tokens` | `5519.00` | `0.00` | 节省 `5519.00` |

After 的五条课程请求均命中 `course_schedule_fast_path`，且仍记录了 `get_course_schedule` 工具调用。这表明系统移除的是不必要的 LLM 环节，而不是课程查询能力。

活动 Fast Path 已有命中后的真实记录：`这周有什么 AI 相关讲座？` 和 `最近有没有比赛可以报名？` 均为 `campus_event_fast_path`，`llm_time_ms=0`、`total_tokens=0`。由于没有保存完全同题的 before 活动 benchmark，本文不计算活动前后下降比例。

### RAG Retriever Cache: Strict Overlapping Queries

来源：`rag_retriever_cache_comparison.md`。原 before / after 样本均包含 child event，严格对比仅使用两个重合 request-level 问题。

| 指标 | Before Average | After Average | 变化 |
| --- | ---: | ---: | ---: |
| `retrieval_time_ms` | `16876.33 ms` | `38.21 ms` | 下降约 `99.8%` |
| `total_latency_ms` | `24804.17 ms` | `7627.18 ms` | 下降约 `69.3%` |

单题检索阶段表现：

| 问题 | Before `retrieval_time_ms` | After `retrieval_time_ms` | 下降 |
| --- | ---: | ---: | ---: |
| 考试作弊有什么后果？ | `15714.98 ms` | `36.57 ms` | 约 `99.8%` |
| 如果我因为生病缺考怎么办？ | `18037.67 ms` | `39.85 ms` | 约 `99.8%` |

来源检查显示：考试作弊问题 before/after 都包含 `exam_policy.md`；生病缺考问题 before/after 都包含 `leave_policy.md` 与 `exam_policy.md`。在已观察样本中，缓存没有表现出明显来源退化。

### RAG Token Budget: Request-level Five-question Comparison

来源：`rag_token_budget_comparison.md`。两侧都使用 `request-last`，各包含同一组 `5` 条 request-level 制度问题。

| 指标 | Before | After | 变化 |
| --- | ---: | ---: | ---: |
| 平均 `prompt_tokens` | `10809.60` | `10680.60` | 下降 `129.00`，约 `1.2%` |
| 平均 `completion_tokens` | `498.60` | `432.60` | 下降 `66.00`，约 `13.2%` |
| 平均 `total_tokens` | `11308.20` | `11113.20` | 下降 `195.00`，约 `1.7%` |
| 平均 `total_latency_ms` | `11274.15 ms` | `9681.98 ms` | 下降 `1592.17 ms`，约 `14.1%` |

五题 after 记录仍保留核心期望来源：`leave_policy.md`、`scholarship_policy.md`、`dormitory_policy.md`、`exam_policy.md`，跨制度缺考问题仍保留考试与请假来源。本阶段目标主要是控制 context / prompt token；总延迟仍会受到模型生成波动影响。

### Optimizations Verified by Tests and Trace

以下能力已有测试或 Trace 字段验证，但当前没有可引用的独立 before/after 性能数字，因此不作量化收益推断：

| 能力 | 已验证内容 |
| --- | --- |
| no-answer + citation | 空召回/低相关拒答、来源与 `chunk_id` 保留 |
| Heading-aware metadata | chunk metadata 字段完整，policy type 与来源评估通过 |
| Hybrid Retrieval | Vector 与 Hybrid 黄金问题来源测试通过 |
| Model fallback | 主模型成功、关闭 fallback、一次降级、双失败与 Trace 路径均有 fake model 测试 |
| History trimming | `agent_id` / `limit` / `include_tools` 与裁剪计数 Trace 测试通过 |
| `custom_data` | `/invoke` 与 `/stream` 结构化元数据兼容测试通过 |
| MCP Adapter | native tool 内容一致性、安全错误 envelope 与只读注册清单测试通过 |

## 6. Testing Strategy

### Unit and Contract Tests

优化过程采用按风险面补测试的策略：

- Router、parser 与 response template 使用纯函数测试保护规则边界。
- Fast Path 使用 service 测试确认命中时不调用原 Agent / LLM，fallback 行为保持不变。
- RAG 工具使用 fake retriever，覆盖来源、空结果、低相关、缓存和异常路径。
- Fallback 使用 fake model / monkeypatch，避免依赖真实模型 API。
- History、schema 与 SSE 使用 mock agent 验证接口兼容和序列化行为。
- MCP adapter 比较同输入下 native function 与 adapter 内容，验证只读工具与可控错误格式。

### RAG Retrieval Quality Golden Set

`tests/rag/test_retrieval_quality.py` 建立了校园制度黄金问题集，围绕：

- 请假流程；
- 奖学金与挂科；
- 宿舍晚归；
- 考试作弊；
- 生病缺考。

该测试检查 top-k 中是否包含期望 source，并在 metadata / Hybrid 阶段继续验证制度类型与融合结果。当前测试中 vector baseline 的 `correct_doc_recall` 断言为 `1.0`，Hybrid 模式也对关键制度问题保留期望来源断言。

### Benchmark Discipline

Trace JSONL 与 Markdown benchmark 支持：

- 固定问题集前后对比；
- `request-last` 排除 RAG child event；
- 记录 latency、token、tool call、retrieved docs 与错误字段；
- 保留 commit、样本数量和选择方式信息。

需要注意：早期 retriever cache benchmark 尚未使用完全 request-level 对齐数据，因此最终报告只引用其两条严格重合问题；Token Budget benchmark 已使用五条 request-level 同题对比。

### Latest Full Test Run

在 Phase 5.1 完成后的最新一次全量 pytest 回归记录为：

```text
315 passed, 2 skipped, 9 warnings
```

警告主要来自既有依赖弃用提示与测试 mock 行为，不影响上述通过结论。

## 7. Engineering Value

| 价值 | 体现 |
| --- | --- |
| 可观测 | 每次请求与 RAG 子事件具备 Trace、耗时、token、来源与错误信息 |
| 可评估 | 固定问题集、黄金召回测试与 request-level benchmark 支持前后比较 |
| 可追溯 | RAG 回答保留 `source`、`chunk_id`、section metadata，并能进入结构化响应 |
| 可回退 | Fast Path 解析不足时回到原 Agent；模型故障时支持受控 fallback |
| 成本受控 | 查表请求跳过 LLM；Retriever 复用；RAG context 与历史上下文均有预算 |
| 可信度增强 | 工具层 no-answer 与来源引用降低无依据制度回答风险 |
| 接口可扩展 | `custom_data` 为未来来源卡片、指标面板与调试能力提供兼容承载层 |
| 能力可复用 | MCP Adapter 将三个只读校园工具标准化开放给外部 Agent |

## 8. Interview Talking Points

1. 我没有先凭经验改代码，而是先实现 Trace 与 benchmark，通过真实样本确认课程查询的主要成本来自完整 LLM 链路。
2. 对课程和活动这类确定性请求，我使用保守规则路由和参数解析建立 Fast Path；解析不明确时仍回退 Agent，兼顾性能与正确性。
3. 五个相同课程问题优化后，平均总耗时从 `3535.00 ms` 降到 `1.19 ms`，平均总 token 从 `5519` 降到 `0`，并继续调用原课程工具。
4. 在 RAG 性能优化中，我区分每次必须执行的检索和不应重复承担的初始化；缓存后两条严格同题样本的平均检索耗时从约 `16.9s` 降至约 `38ms`。
5. 对制度问答，我把 no-answer 做在工具边界而非只写 prompt，避免没有依据时模型自行补流程、联系方式或制度结论。
6. 我从离线索引质量入手增加 Markdown 清洗、标题感知切分与 metadata，使来源可以追踪到文档片段与章节，而不是只有文件名。
7. 对强关键词制度问题，我用 BM25 补充向量检索，并通过 RRF 融合不同分数尺度的排名；黄金问题集保护召回来源不退化。
8. Hybrid Retrieval 后我进一步控制送入模型的 evidence context。五题 request-level benchmark 中，平均 prompt tokens 下降 `129`，同时保留核心来源。
9. 在可靠性上，我实现了统一 timeout/retry/temperature 配置和一次受控 model fallback，并将失败与降级信息写入 Trace。
10. 我把完整历史恢复与模型上下文成本分开：checkpoint 不丢历史，模型仅接收有限窗口；再通过 `custom_data` 和只读 MCP Adapter 为前端展示与外部复用准备扩展接口。

## 9. Limitations and Future Work

当前系统仍有明确的下一阶段空间：

| 局限 | 后续方向 |
| --- | --- |
| Hybrid Retrieval 尚未引入 reranker | 在黄金问题集与 no-answer 集上评估轻量 reranker，对 Hybrid top-N 重排 |
| Token 预算为轻量估算 | 按实际模型接入 tokenizer，并对预算与真实 token 做校准 |
| 尚未支持长期记忆或摘要记忆 | 在保留最近窗口基础上，引入可评估的用户画像或摘要层 |
| 知识库重建仍以全量流程为主 | 增加增量索引、变更检测与缓存自动失效策略 |
| `custom_data` 当前为 `dict[str, Any]` | 演进为 `RetrievedDocument`、`MessageMetrics`、`ModelFallbackInfo` 等强类型 schema |
| MCP 当前是旁路 server adapter | 后续可让主 Agent 作为可配置 MCP client，并加入 `trace_id` 透传与 adapter overhead benchmark |
| 部署侧观测仍以本地 Trace/benchmark 为主 | 接入运行监控、错误率与成本仪表盘、告警策略 |
| MCP 与业务 API 权限边界尚为基础版 | 引入鉴权、工具级授权、审计日志与调用配额控制 |

下一步应继续沿用本项目已经建立的原则：先定义风险与指标，再用固定测试集和 request-level benchmark 验证收益，避免仅为了增加功能而扩大系统复杂度。
