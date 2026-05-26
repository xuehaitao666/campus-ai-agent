# Campus AI Agent Final Optimization Report

## 1. Project Overview

Campus AI Agent 是面向大学校园场景的智能助理项目，以 FastAPI 提供 Agent API，以 Streamlit 提供交互界面，并通过 LangGraph 组织模型与工具调用。项目当前支持：

- 课程表查询与校园活动查询；
- 校园制度 RAG 问答，包括请假、奖学金、宿舍与考试制度；
- 学习计划生成；
- 多轮会话历史恢复与裁剪；
- 只读 Campus Tools MCP Server Adapter，供外部 MCP Client 复用课程、活动与制度查询工具；
- Docker 双服务本地运行方案，用于复现 FastAPI 与 Streamlit 环境。

本轮优化的主线不是增加展示功能，而是把一个可运行的校园 Agent 逐步建设为可观测、可评估、可回退、可扩展并可复现的工程系统。

## 2. Initial Problems

项目早期已经具备多个业务能力，但仍存在明显工程化缺口：

| Problem | Impact |
| --- | --- |
| 功能堆叠，缺少统一优化主线 | 很难判断应该优先优化性能、可信度还是稳定性 |
| 缺少 Trace 与 Benchmark | 无法用同题、同指标证明优化收益 |
| RAG 每次重复初始化 embedding / Chroma / retriever | 制度查询存在不必要的秒级检索开销 |
| 缺少 no-answer 机制 | 无依据或低相关召回时存在生成确定性制度结论的风险 |
| Chunk 与 metadata 不够结构化 | 引用、评估、调试与后续检索增强受限 |
| 检索召回和排序不够稳定 | 强制度关键词问题不能充分利用关键词信号 |
| Prompt / context token 不可控 | Hybrid 候选增多后可能把低价值文本继续送入模型 |
| 模型调用缺少 timeout / retry / fallback | 外部模型临时失败会直接影响用户请求 |
| 长对话历史可能无限增长 | 多轮上下文成本和延迟随会话不断增加 |
| API 返回缺少结构化 `custom_data` | 前端或调用方只能依赖回答文本，难以展示来源与指标 |
| 缺少容器化复现方式 | 本地交付与演示需要手工配置多进程环境 |

## 3. Optimization Roadmap

| Phase | 优化内容 | 解决的问题 | 涉及模块 | 验证方式 | 面试亮点 |
| --- | --- | --- | --- | --- | --- |
| Phase 1 | Agent Trace + Benchmark Run | 缺少测量与留痕 | `src/core/tracing.py`, `scripts/export_benchmark_run.py`, `docs/optimization/benchmark_runs/` | Trace JSONL、导出报告、服务测试 | 先建立可测基线，再做优化 |
| Phase 2.1 | Rule-based Router | 无法识别确定性查询 | `src/core/router.py` | Router 单元测试 | 用保守规则控制优化边界 |
| Phase 2.2-2.4 | Course/Event Fast Path + 响应模板 | 简单查询仍走完整 LLM 链路 | `src/service/service.py`, query parser, response templates | 同题 benchmark、service 测试 | 保留 fallback 的低成本直查 |
| Phase 3.1 | RAG Retriever Cache | 重复初始化成本 | `src/agents/tools.py` | Cache 测试、同题 benchmark | 区分必要检索与不必要初始化 |
| Phase 3.1.1 | Request-level Benchmark 导出 | Child event 污染统计口径 | `scripts/export_benchmark_run.py` | 导出脚本测试 | 用干净样本比较优化 |
| Phase 3.2 | No-answer + Source Citation | RAG 幻觉与不可追溯回答 | `src/agents/tools.py`, `src/agents/rag_assistant.py` | 空召回/低相关/引用测试 | 在工具层落实可信边界 |
| Phase 3.3 | 文档清洗、标题切分、metadata 增强 | Chunk 语义与引用信息不足 | `src/rag/document_cleaner.py`, `src/rag/chunking.py`, build script | Chunk/build/retrieval tests | 离线数据质量决定 RAG 上限 |
| Phase 3.4 | BM25 + Vector + RRF | 强关键词召回波动 | `src/rag/hybrid_retriever.py` | Hybrid 单测、黄金问题集 | 融合语义召回与精确关键词 |
| Phase 3.5 | Prompt 拆分 + Token Budget | Context/token 成本不可控 | `src/core/token_budget.py`, `src/prompts/rag_prompts.py` | Budget 测试、同题 benchmark | 控制进入 LLM 的证据规模 |
| Phase 3.6 | Optional RAG Reranker | 候选排序缺少 evidence 精选层 | `src/rag/reranker.py`, `src/agents/tools.py` | Reranker 与 retrieval quality 测试 | 召回、重排、预算职责分层 |
| Phase 4.1 | Timeout / Retry / Fallback | 模型服务故障缺少降级 | `src/core/settings.py`, `src/core/llm.py`, agent model call | Fake/mock model 测试 | 可靠性配置化并可追踪 |
| Phase 4.2 | History API + Context Trimming | 历史无限增长 | schema, service, agent model input | 多轮历史与裁剪测试 | 保留历史与限制模型上下文分离 |
| Phase 4.3 | `ChatMessage.custom_data` | 响应缺少结构化附加信息 | schema, service utils/service | JSON/SSE 序列化测试 | 兼容扩展来源与观测字段 |
| Phase 5.1 | MCP Server Adapter | 工具难以被外部 Agent 复用 | `src/mcp_server/` | MCP native consistency 测试 | 旁路标准化暴露，只读安全边界 |
| Phase 6 | Docker 工程落地 | 环境复现成本高 | `Dockerfile`, `docker-compose.yml`, deployment docs | Compose 结构检查、pytest；启动命令交付 | 将优化成果转为可运行交付物 |

## 4. Key Technical Optimizations

### 4.1 Trace + Benchmark

Phase 1 引入请求级 `TraceRecord` 与 JSONL 落盘，把一次 Agent 调用的 `trace_id`、请求标识、路由、工具调用、检索来源、总耗时、模型耗时、工具耗时、token、fallback 与错误信息连接起来。随后提供 Markdown benchmark 导出机制，让性能结论不依赖口头描述。

Phase 3.1.1 进一步解决 RAG 子事件会混入 request summary 的问题，加入 request-level 筛选和 `--request-last` 导出方式。后续严肃对比应以 request-level 相同问题集为准。

### 4.2 Rule-based Router + Fast Path

Router 将课程查询、校园活动、学习计划、制度问答、普通聊天与未知请求区分开来。对于能可靠解析参数的课程与活动问题，service 直接调用已有工具，而不进入完整 LLM + LangGraph 工具调用闭环。

这一设计有两个关键约束：

- Fast Path 复用原工具能力，不复制课程或活动业务逻辑；
- 非目标意图或无法解析参数时，继续 fallback 到原 Agent 链路。

模板化响应为不调用 LLM 的直查结果提供稳定 Markdown 输出，同时不恢复 token 开销。

### 4.3 RAG Retriever Cache

制度查询原本会重复初始化 embedding、Chroma 与 retriever。缓存优化只缓存可复用资源，仍要求每个 query 执行真实 `retriever.invoke(query)`；知识库更新后可通过 `clear_rag_cache()` 或服务重启失效缓存。

这一阶段没有改回答内容、prompt 或召回策略，因而能够较清晰地将检索耗时变化归因于重复初始化消除。

### 4.4 No-answer + Source Citation

RAG 可信度约束落在工具层，而非只交给 prompt：

- 空召回或轻量规则判定低相关时，直接返回“当前知识库中没有找到明确依据”的 no-answer；
- no-answer 提示用户以学校官方通知或辅导员答复为准，并明确不得编造制度、电话、办公室或网址；
- 有有效 evidence 时，回答保留 `source` 与 `chunk_id` 引用。

这样即使模型层发生波动，制度回答的证据边界也更清晰。

### 4.5 Metadata + Heading-aware Chunking

离线建库从简单固定长度切分演进为保留 Markdown 标题语义的切分流程，并增加文档清洗。每个 chunk 可携带：

- `source`
- `path`
- `chunk_id`
- `section`
- `heading_path`
- `policy_type`

这些字段同时服务于引用展示、黄金问题评估、Hybrid 去重、Reranker 特征以及结构化 API 输出。

### 4.6 Hybrid Retrieval

Hybrid Retrieval 采用三段式设计：

1. Vector retrieval 提供语义召回；
2. BM25 以轻量中文 bigram 捕捉制度关键词；
3. RRF 按排名融合两路候选，并以 `chunk_id` 去重。

结果 metadata 记录 `retrieval_source`、`hybrid_score`、`vector_rank` 与 `bm25_rank`。RRF 的价值在于无需强行比较不同量纲的 vector score 与 BM25 score。

### 4.7 RAG Reranker

Phase 3.6 在 Hybrid Retrieval 与 Token Budget 之间引入默认关闭的可选 reranker。第一版采用轻量规则打分，不下载大型模型，综合：

- query 与正文词项重合；
- query 与 `section` / `heading_path` 重合；
- query 与 `policy_type` 匹配；
- 原有 `hybrid_score` 辅助信号。

重排结果保留所有来源 metadata，并加入 `rerank_score`。若重排失败，则安全退回原候选排序并记录 `rerank_error`。当前这一能力通过单测和黄金来源 top-k 验证，尚无独立 before/after latency 或 rank benchmark。

### 4.8 Token Budget

Hybrid Retrieval 提升召回后，不应无上限将候选内容填入 prompt。Token Budget 将“已召回 documents”与“进入 LLM 的 context”区分开来，默认限制：

| Limit | Value |
| --- | ---: |
| 最大 context 文档数 | `5` |
| 总格式化 context 字符数 | `6000` |
| 单 chunk 字符数 | `1500` |

上下文筛选保留 `source`、`chunk_id`、`section`、`heading_path` 与 `policy_type`，no-answer 判定仍位于预算裁剪之前，避免安全提示被误裁。

### 4.9 Model Fallback

模型可靠性层统一引入 timeout、provider retry、temperature 与可选 fallback 配置。主模型成功时不额外调用；主模型失败且开启 fallback 时，仅尝试一次不同的候补模型；候补也失败时返回稳定失败路径，避免循环重试。

Trace 可记录 `primary_model`、`fallback_model`、`fallback_triggered`、`model_error`、`model_error_type` 与尝试次数，为后续恢复率和模型成本分析提供入口。

### 4.10 History Trimming

History API 支持 `agent_id`、`limit` 与 `include_tools`，让调用方可以选择读取指定 Agent 的最近历史，并决定是否保留工具中间消息。

模型调用前另设 `HISTORY_MAX_MESSAGES` 最近消息窗口：checkpoint 仍能保存完整会话用于恢复，但每次进入模型的上下文不会无限增长。Trace 记录历史消息数量与裁剪数量，使成本变化可以观测。

### 4.11 `ChatMessage.custom_data`

`content` 适合人类阅读，不适合作为结构化数据通道。项目在保持旧消息兼容的情况下，通过 `ChatMessage.custom_data` 传递：

- `retrieved_docs` 与 `source_citations`
- `metrics`
- `tool_execution`
- `model_fallback`

这为后续前端来源卡片、调试面板与 API 消费者提供了稳定入口，又避免当前阶段大改 schema 与前端。

### 4.12 MCP Server Adapter

MCP 接入采用旁路 Adapter，而不是重构主 Agent。第一版只读暴露：

| MCP Tool | Native Function |
| --- | --- |
| `get_course_schedule` | `get_course_schedule_func` |
| `get_campus_events` | `get_campus_events_func` |
| `query_campus_policy` | `query_campus_policy_func` / 既有制度查询能力 |

Adapter 返回 JSON 可序列化 envelope 与耗时，失败不暴露 traceback；安全边界明确不包含 shell、文件写入、删除、邮件或任意网络副作用。MCP server 采用 stdio transport，不改变 FastAPI / Streamlit / LangGraph 主流程。

### 4.13 Docker Deployment

Phase 6 新增基于 `python:3.11-slim` 与 `uv` 的统一镜像，并通过 `docker-compose.yml` 提供两个最小服务：

- `backend`：FastAPI，端口 `8080`；
- `frontend`：Streamlit，端口 `8501`，通过容器网络访问 backend。

`./data` 与 `./logs` 作为 volume 持久化向量库、SQLite checkpoint 与 Agent Trace；`.env` 以只读挂载进入容器而不写入镜像。MCP stdio 服务不作为长驻 Web 服务加入主 compose。

## 5. Quantitative Results

### 5.1 Course Fast Path

数据来源：`course_fast_path_comparison.md` 与对应 before/after 五题 benchmark。测试问题为五个完全相同的课程查询。

| Metric | Before: Full Agent Chain | After: Course Fast Path | Change |
| --- | ---: | ---: | ---: |
| 平均 `total_latency_ms` | `3535.00 ms` | `1.19 ms` | 下降 `3533.81 ms` (`99.97%`) |
| 平均 `llm_time_ms` | `3502.92 ms` | `0.00 ms` | 下降 `3502.92 ms` |
| 平均 `prompt_tokens` | `5329.00` | `0.00` | 节省 `5329.00` |
| 平均 `total_tokens` | `5519.00` | `0.00` | 节省 `5519.00` |

After 样本均命中 `course_schedule_fast_path`，且仍调用 `get_course_schedule`，说明降低成本的同时保留了原领域工具能力。

### 5.2 Campus Event Fast Path

`after_phase2_fast_path_templates` benchmark 记录了两条活动 Fast Path 实测样本：

| Query | Route | Tool | `total_latency_ms` | `llm_time_ms` | `total_tokens` |
| --- | --- | --- | ---: | ---: | ---: |
| 这周有什么 AI 相关讲座？ | `campus_event_fast_path` | `get_campus_events` | `1.21 ms` | `0` | `0` |
| 最近有没有比赛可以报名？ | `campus_event_fast_path` | `get_campus_events` | `0.85 ms` | `0` | `0` |

现有文档中没有相同活动问题的 before benchmark，因此这里只陈述 after 实测结果，不计算严格下降比例。

### 5.3 RAG Retriever Cache

缓存 benchmark 的 before request 样本为 2、after request 样本为 3；严格同题比较基于两条重合制度问题。

| Overlapping-query Metric | Before | After | Change |
| --- | ---: | ---: | ---: |
| 平均 `retrieval_time_ms` | `16876.33 ms` | `38.21 ms` | 下降约 `99.8%` |
| 平均 `total_latency_ms` | `24804.17 ms` | `7627.18 ms` | 下降约 `69.3%` |

召回来源未出现明显退化：

- “考试作弊有什么后果？” before / after 均召回 `exam_policy.md`；
- “如果我因为生病缺考怎么办？” before / after 均召回 `leave_policy.md` 与 `exam_policy.md`；
- after 中“宿舍晚归会怎么处理？”召回 `dormitory_policy.md`。

该阶段优化目标是检索初始化成本，而非 LLM token；总耗时仍会受生成阶段波动影响。

### 5.4 RAG Token Budget

数据来源：五个相同 RAG 问题的 request-level before/after benchmark。

| Metric | Before | After | Change |
| --- | ---: | ---: | ---: |
| 平均 `prompt_tokens` | `10809.60` | `10680.60` | 下降 `129.00` (`1.2%`) |
| 平均 `completion_tokens` | `498.60` | `432.60` | 下降 `66.00` (`13.2%`) |
| 平均 `total_tokens` | `11308.20` | `11113.20` | 下降 `195.00` (`1.7%`) |
| 平均 `total_latency_ms` | `11274.15 ms` | `9681.98 ms` | 下降 `1592.17 ms` (`14.1%`) |

五题核心来源仍保留；本阶段的主要目标是控制 evidence context 和 token，而不是承诺总延迟必然降低。

### 5.5 RAG Reranker

当前没有已导出的 reranker before/after benchmark，因此不编造 `rerank_latency_ms` 或 `expected_source_rank` 改善数据。现阶段已通过：

- Reranker 排序、top-k、metadata 保留与异常降级单元测试；
- 启用 reranker 后黄金问题的正确制度来源仍位于 top-k；
- Trace 字段已具备 `rerank_latency_ms`、重排输入/输出数量和重排来源记录能力。

正式定量评估应在相同制度问题集上分别采集关闭与开启 reranker 的 request-level benchmark。

## 6. Testing Strategy

项目优化采用“功能安全网 + 性能证据”两层验证：

| Verification Layer | Coverage |
| --- | --- |
| 单元测试 | Router、parser、模板、token budget、chunking、Hybrid、Reranker、settings、fallback 等纯逻辑 |
| Agent/Tool 测试 | 工具调用闭环、Database Search、no-answer、source citation、RAG Agent |
| RAG 黄金问题集 | 校园制度问题的正确 `source` / `policy_type` 召回，包含 Vector、Hybrid 与 Reranker 场景 |
| Benchmark request-level 导出 | 排除 child event 后比较相同问题的 latency 与 token |
| Fake/mock model | 验证 timeout / fallback 成功、失败与不循环重试路径，不调用真实模型 API |
| History 测试 | `thread_id` 隔离、`agent_id`、`limit`、`include_tools` 与模型上下文裁剪 |
| Schema/SSE 测试 | `custom_data` JSON 序列化、invoke/stream 兼容与结构化来源透传 |
| MCP consistency 测试 | MCP adapter 与 native 工具同输入结果一致、只读工具注册与安全错误 envelope |
| Docker 校验 | `docker-compose.yml` 双服务结构已校验；当前执行环境未安装 Docker，实际 `compose build/up` 命令已交付文档 |

本次收口后的本地测试运行结果为：

```text
326 passed, 2 skipped, 9 warnings
```

测试通过 `.venv/bin/pytest -q` 执行；当前运行环境未提供 `uv` 命令。Warnings 主要来自已有 LangGraph / Starlette 弃用提示与测试 mock 资源告警，不属于本阶段新增失败。

## 7. Engineering Value

| Value | Result |
| --- | --- |
| 可观测 | Trace 记录路由、工具、检索、模型、历史裁剪、fallback 与 reranker 事件 |
| 可评估 | 固定问题集、黄金召回测试与 request-level benchmark 可验证优化效果 |
| 可追溯 | RAG 回答保留 `source` / `chunk_id`，API 可传递结构化 citations |
| 可回退 | Fast Path 未命中回原 Agent；reranker 异常回原排序；模型失败可配置 fallback |
| 可控 token 成本 | 确定性 Fast Path 跳过 LLM，RAG Token Budget 限制 evidence context，历史窗口避免无限膨胀 |
| 可扩展接口 | `custom_data` 为来源、指标和未来 UI 展示保留兼容通道 |
| 可被 MCP 复用 | 只读校园工具可由外部 MCP Client 调用，无需侵入主 Agent 流程 |
| 可容器化复现 | FastAPI / Streamlit 可通过统一 Docker 镜像与 compose 在本地复现 |

## 8. Interview Talking Points

1. 我没有一开始就盲目改架构，而是先补 Trace 与 Benchmark，让优化前后能通过固定问题集和真实指标对比。
2. Trace 显示简单课程查询仍经过完整 LLM 链路，因此我以保守 Router + Fast Path 处理确定性问题，并保留原 Agent fallback；五个同题课程请求的平均耗时从 `3535.00 ms` 降至 `1.19 ms`，平均 token 从 `5519` 降至 `0`。
3. 对 RAG 性能我区分了必要成本和不必要成本：每次 query 的检索是必要的，重复初始化 embedding / Chroma / retriever 是不必要的；缓存后两条同题样本平均检索耗时从约 `16.9 s` 降到约 `38 ms`。
4. 我把 RAG 可信度约束放在工具边界：空召回或低相关直接 no-answer，有证据则保留 `source` 与 `chunk_id`，避免只靠 prompt 约束幻觉。
5. 我将 Markdown 文档清洗、heading-aware chunking 和 metadata 增强作为离线质量基础，让 citation、检索评估、Hybrid 去重与后续排序使用同一套可解释字段。
6. 针对校园制度强关键词场景，我组合 Vector、BM25 与 RRF：语义召回和精确词召回各司其职，融合时不强行比较不同分数尺度。
7. Hybrid 提高召回后，我又将“候选召回”“证据重排”“上下文预算”拆成独立层；Reranker 默认关闭且异常可降级，Token Budget 则在保留引用的前提下控制输入成本。
8. 系统可靠性方面，我统一配置 timeout/retry/fallback，并通过 mock model 测试失败链路；这让外部模型波动可以恢复、可以追踪、也不会无限重试。
9. 多轮会话中，我区分完整历史存储与每轮模型上下文：history 可以恢复和筛选，模型只消费最近窗口，避免 token 随会话无限增长。
10. 在集成与交付层，我用 `custom_data` 提供兼容的结构化响应，用只读 MCP Adapter 开放工具复用，再用 Docker 将 FastAPI、Streamlit、数据与 Trace 的本地运行方式标准化。

## 9. Limitations and Future Work

当前系统仍有明确的演进空间：

- Reranker 第一版是轻量可配置 heuristic，实现稳定、无大模型依赖，但后续可在评估集足够后替换或增加 CrossEncoder，并比较排序质量与延迟代价。
- 当前尚未做长期记忆或摘要记忆；现阶段仅通过窗口裁剪控制上下文增长。
- MCP 当前是只读旁路 server adapter，主 LangGraph Agent 尚未作为 MCP client 消费外部工具。
- `custom_data` 当前为灵活的 `dict`，后续可升级为 `RetrievedDocument`、`MessageMetrics`、`ToolExecution` 等强类型 schema。
- Docker 方案是本地工程复现入口，不是生产级云部署；目前没有 Nginx、HTTPS、Kubernetes、secrets manager 或弹性扩缩容。
- 后续可继续建设增量索引、权限与审计控制、CI/CD、线上监控告警以及模型/token 成本看板。

最终而言，本项目已从一个具备校园问答功能的 Agent 原型，演进为拥有性能证据、可信 RAG 边界、故障降级、结构化响应、工具复用出口和本地交付路径的工程化系统。
