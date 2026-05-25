# Campus AI Agent 测试覆盖与演进地图

本文档分析当前项目 `tests/` 目录和 pytest 相关配置，说明现有测试已经保护了哪些能力、仍存在哪些验证空白，以及在继续做 RAG、Router、Trace、Fallback、Schema 和 Memory 优化前，建议补齐的测试体系。

## 1. 测试体系总体定位

当前项目已经形成了较清晰的分层测试结构：

- `agents/`：验证 Agent 注册、工具能力、工具路由提示词以及部分特殊 Agent。
- `rag/`：验证校园知识库 Markdown 加载、切分和 Chroma 建库。
- `service/`：验证 FastAPI 接口、SSE 流式响应、鉴权、生命周期和消息转换。
- `client/`：验证后端客户端的同步、异步和流式调用封装。
- `core/`：验证配置解析和不同模型 Provider 的初始化分支。
- `app/`：验证 Streamlit 页面交互逻辑。
- `voice/`：验证语音输入输出相关能力。
- `integration/`：通过 Docker 场景覆盖端到端运行链路。

整体来看，当前测试更擅长验证“单个工具能否工作”和“服务/client 接口契约是否成立”，但对默认 Agent 的完整图执行、RAG 实际召回质量、持久化 memory 行为、生产级异常链路仍需进一步加强。

## 2. pytest 配置

pytest 配置主要位于 `pyproject.toml`：

```toml
[tool.pytest.ini_options]
pythonpath = ["src"]
asyncio_default_fixture_loop_scope = "function"

[tool.pytest_env]
OPENAI_API_KEY = "sk-fake-openai-key"
```

| 配置项 | 作用 | 影响 |
| --- | --- | --- |
| `pythonpath = ["src"]` | 将 `src/` 加入导入路径 | 测试中可以直接导入 `agents`、`service`、`core` 等模块 |
| `asyncio_default_fixture_loop_scope = "function"` | 每个测试函数使用独立异步 event loop fixture 范围 | 减少异步测试之间的状态污染 |
| `OPENAI_API_KEY = "sk-fake-openai-key"` | 注入一个测试用 OpenAI Key | 使 import-time 的 `Settings()` 不会因没有任何 provider key 而报错 |

需要特别区分：

- `OPENAI_API_KEY = "sk-fake-openai-key"` 只是满足配置初始化条件，并不会自动把所有模型调用替换为 Fake Model。
- 只有显式使用 `FakeModelName.FAKE`、设置对应 Fake 配置，或者在测试中 mock 模型调用时，测试才不会访问真实模型服务。

根目录的 `tests/conftest.py` 还承担以下职责：

- 注册 `--run-docker` 参数。
- 注册 `docker` marker。
- 默认跳过标记为 Docker 的集成测试，只有显式指定 `--run-docker` 才运行。
- 提供环境变量清理 fixture，便于独立验证配置行为。

## 3. tests 目录结构

```text
tests/
├── conftest.py
├── agents/
│   ├── test_agent_loading.py
│   ├── test_campus_course_schedule_tool.py
│   ├── test_campus_events_tool.py
│   ├── test_campus_policy_tool.py
│   ├── test_day15_tool_call_flow.py
│   ├── test_github_mcp_agent.py
│   ├── test_lazy_agent.py
│   ├── test_study_plan_tool.py
│   └── test_tool_routing_prompt.py
├── app/
│   ├── conftest.py
│   └── test_streamlit_app.py
├── client/
│   ├── conftest.py
│   └── test_client.py
├── core/
│   ├── test_llm.py
│   └── test_settings.py
├── integration/
│   └── test_docker_e2e.py
├── rag/
│   └── test_build_campus_kb.py
├── service/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_service.py
│   ├── test_service_e2e.py
│   ├── test_service_lifespan.py
│   ├── test_service_message_generator.py
│   ├── test_service_streaming.py
│   └── test_utils.py
└── voice/
    ├── conftest.py
    ├── providers/
    │   ├── test_openai_stt.py
    │   └── test_openai_tts.py
    ├── test_manager.py
    ├── test_stt.py
    └── test_tts.py
```

## 4. 当前测试文件说明

| 测试文件 | 主要验证对象 | 当前验证重点 |
| --- | --- | --- |
| `tests/agents/test_agent_loading.py` | `agents.py` | 静态 Agent、懒加载 Agent 的获取与异常处理 |
| `tests/agents/test_lazy_agent.py` | Lazy Agent 基类 | 加载前后状态和失败场景 |
| `tests/agents/test_github_mcp_agent.py` | GitHub MCP Agent | PAT 缺失、工具加载、MCP 失败和图创建 |
| `tests/agents/test_campus_course_schedule_tool.py` | `get_course_schedule` | 按星期、时间段、课程名和组合条件过滤 |
| `tests/agents/test_campus_events_tool.py` | `get_campus_events` | 按关键词、类型、受众和日期范围过滤 |
| `tests/agents/test_study_plan_tool.py` | `generate_study_plan` | 天数、目标、主题、避开上课时间、缺失画像字段 |
| `tests/agents/test_campus_policy_tool.py` | `query_campus_policy` | Fake Retriever 下的结构化答案、无结果与低相关拒答 |
| `tests/agents/test_tool_routing_prompt.py` | `research_assistant` prompt | 提示词是否包含工具选择和拒绝幻觉规则 |
| `tests/agents/test_day15_tool_call_flow.py` | 校园工具组合 | 工具注册及函数输出的基础串联验证 |
| `tests/rag/test_build_campus_kb.py` | `build_campus_kb.py` | Markdown 加载、chunk metadata、embedding 替身和 Chroma 写入 |
| `tests/service/test_service.py` | FastAPI service | `/invoke`、`/stream`、`/history`、`/info`、`/feedback` |
| `tests/service/test_auth.py` | 鉴权逻辑 | Bearer Token 有无及正确性 |
| `tests/service/test_service_lifespan.py` | lifespan | saver/store 初始化及注入 Agent |
| `tests/service/test_service_streaming.py` | 流式消息辅助逻辑 | AI message 构造与字段处理 |
| `tests/service/test_service_message_generator.py` | message generator | supervisor 场景下 Fake Model 输出处理 |
| `tests/service/test_service_e2e.py` | service 与 client | 自定义 StateGraph 下的流式工具消息链路 |
| `tests/service/test_utils.py` | 消息转换工具 | LangChain Human/AI/ToolMessage 到 `ChatMessage` |
| `tests/client/test_client.py` | `AgentClient` | invoke、stream、history、info、feedback 与错误响应 |
| `tests/core/test_settings.py` | `Settings` | 核心 key、默认值、Azure 配置和无 Provider 异常 |
| `tests/core/test_llm.py` | `get_model()` | 部分 Provider 与 Fake Model 创建 |
| `tests/app/test_streamlit_app.py` | Streamlit 页面 | 输入、流式/非流式消息、反馈和子 Agent 展示 |
| `tests/integration/test_docker_e2e.py` | Docker 集成 | Fake Model 场景下 app/service 启动链路 |
| `tests/voice/*` | Voice 模块 | STT/TTS provider 与 manager 行为 |

## 5. 当前覆盖总览表

| 模块或能力 | 是否已覆盖 | 覆盖程度 | 说明 |
| --- | --- | --- | --- |
| Agent 注册与加载 | 是 | 中 | 覆盖 registry、lazy agent、GitHub MCP Agent |
| `research_assistant.py` | 部分 | 偏弱 | 验证 prompt 和 tools 列表，未完整执行默认 StateGraph |
| `rag_assistant.py` | 否 | 弱 | 未找到直接测试 |
| 课程查询工具 | 是 | 强 | 主过滤条件与无匹配结果均覆盖 |
| 校园活动工具 | 是 | 中强 | 主过滤条件覆盖，但日期依赖系统日期 |
| 学习计划工具 | 是 | 中强 | 规则生成和部分容错覆盖 |
| `query_campus_policy` | 是 | 中 | Fake Retriever 验证结果格式和拒答，不验证真实召回 |
| `Database_Search` | 否 | 弱 | RAG Agent 实际使用的工具未直接测试 |
| `calculator` | 否 | 弱 | 未找到直接测试 |
| RAG 建库脚本 | 是 | 中 | 覆盖加载、切片、metadata 和 Chroma 基础写入 |
| `/invoke` | 是 | 中强 | 覆盖主要请求配置、错误和 interrupt |
| `/stream` | 是 | 中 | 覆盖 token/final/interrupt，但复杂 SSE 事件不足 |
| `/history` | 是 | 基础 | mock state 下读取与转换 |
| `/info` | 是 | 基础 | 基础响应存在验证 |
| `AgentClient` | 是 | 中强 | 同步、异步、流式和错误接口覆盖 |
| `schema.py` | 间接 | 偏弱 | 依赖接口测试使用，缺少独立 schema 契约测试 |
| `service/utils.py` | 是 | 基础 | 主消息类型覆盖，复杂 content 和 tool call 清理不足 |
| `settings.py` | 是 | 中 | 覆盖核心和 Azure，多个 Provider 分支缺口明显 |
| `llm.py` | 是 | 中 | 覆盖部分 Provider 与 Fake，缺 Provider/cache/failure 分支 |
| memory/checkpointer/store | 部分 | 弱 | 验证注入和 mock history，未验证真实后端持久化 |
| Streamlit 前端 | 是 | 中 | mock client 场景下主要界面流覆盖 |
| Voice | 是 | 中 | provider 与 manager 测试存在 |
| Docker 端到端 | 是 | 基础 | 可选运行，覆盖范围受环境和开关限制 |

## 6. Agents 与 Tools 的覆盖情况

### 6.1 是否覆盖了 Agents

当前确实覆盖了部分 Agent 相关行为：

- Agent 注册、获取和加载异常。
- Lazy Agent 和 GitHub MCP Agent 的加载逻辑。
- 默认 `research-assistant` 的工具声明和提示词规则。

但默认 Agent 的核心执行图仍缺少真正的行为验证：

- 未直接验证 `guard_input -> model -> tools -> model -> END` 链路。
- 未直接验证 `safeguard_input()` 和 unsafe 分支。
- 未直接验证 `pending_tool_calls()` 的分支判断。
- 未验证 Fake Tool Calling Model 驱动 `ToolNode(tools)` 实际执行并回到模型节点。

### 6.2 是否覆盖了校园工具

| 工具 | 测试覆盖 | 评价 |
| --- | --- | --- |
| `get_course_schedule` | 已覆盖 | 过滤规则覆盖较完整 |
| `get_campus_events` | 已覆盖 | 主逻辑覆盖，但存在日期稳定性问题 |
| `generate_study_plan` | 已覆盖 | 能说明它是规则生成逻辑，并验证部分容错 |
| `query_campus_policy` | 已覆盖 | 通过 fake retriever 验证格式化与拒答策略 |
| `database_search` / `Database_Search` | 未覆盖 | 这是 `rag_assistant` 依赖的重要工具空白 |
| `calculator` | 未覆盖 | 数学表达式和非法输入缺少单元测试 |

### 6.3 活动日期测试的稳定性风险

`get_campus_events` 的 `date_range` 基于运行当天的 `date.today()` 计算。测试数据中的活动日期与具体自然日绑定，因此随着时间经过，诸如“最近”的测试可能变得不稳定。

更稳健的测试方式应当：

- monkeypatch 工具模块中的 `date.today()`。
- 使用临时 JSON 数据构造固定边界日期。
- 覆盖“今天”“明天”“本周”“最近”的边界行为。

## 7. RAG 测试覆盖情况

### 7.1 建库脚本已覆盖内容

`tests/rag/test_build_campus_kb.py` 已验证：

- 从目录递归读取 Markdown 文档。
- 非 Markdown 文件不会作为当前知识库输入。
- 文档 metadata 中保留 `source` 和 `path`。
- chunk 生成后附加 `chunk_id`。
- 可替换本地 embedding 实现以避免真实模型下载或调用。
- Chroma 能保存并对基础文本执行相似度查询。

### 7.2 RAG 问答工具已覆盖内容

`tests/agents/test_campus_policy_tool.py` 通过 fake retriever 验证了：

- 制度回答包含固定结构部分。
- 来源信息可以进入输出。
- 没有检索结果时不随意编造答案。
- 检索内容与问题低相关时能够输出依据不足提示。
- 输出中不会凭空补充联系方式、网址或办理窗口。

### 7.3 当前 RAG 测试缺口

目前验证的是“处理已给定检索结果的回答逻辑”，尚未充分验证“真实知识库能否检索到正确内容”：

- 没有黄金问题集和预期 source/chunk 命中测试。
- 没有真实 embedding + Chroma 数据下的召回质量评估。
- 没有 `rag_assistant.py` 通过 `Database_Search` 完成整条问答链路的测试。
- 没有无结果、低相关、向量库损坏、embedding 加载失败等 Agent 级测试。
- 没有增量索引、重复文档、文档更新后旧 chunk 清理的测试。
- 没有基于标题、制度类型、章节等增强 metadata 的检索过滤测试。

## 8. research_assistant 与 rag_assistant 覆盖情况

| 文件 | 当前被测内容 | 尚未覆盖内容 |
| --- | --- | --- |
| `src/agents/research_assistant.py` | tools 注册、prompt 中的工具路由规范和回答约束 | 模型调用、工具调用图循环、安全拦截、剩余步数处理、实际 SSE 输出 |
| `src/agents/rag_assistant.py` | 未找到直接测试 | `Database_Search` 调用、知识库约束 prompt、检索无结果、图执行和流式输出 |

这里是当前测试体系中非常关键的一层空白：工具函数测试已经不错，但“Agent 是否在正确问题下正确选择工具，并把工具结果变成最终回答”还没有被系统验证。

## 9. Service API 覆盖情况

### 9.1 已覆盖接口

`tests/service/test_service.py` 等文件已经覆盖：

| 接口或能力 | 覆盖情况 |
| --- | --- |
| `/invoke` | 正常调用、自定义 Agent、model 透传、非法 model、agent_config、interrupt |
| `/stream` | token 流、最终消息、关闭 token 流、interrupt |
| `/history` | mock 历史状态读取与消息转换 |
| `/info` | 服务信息响应 |
| `/feedback` | 反馈提交流程 |
| 鉴权 | 未配置 secret、正确 token、错误 token |
| lifespan | saver/store 创建及向 agents 注入 |

### 9.2 Service 层仍缺少的验证

- 默认 `research-assistant` 配合真实 Fake Tool Calling 模型的 `/invoke` 与 `/stream` 链路。
- `rag-assistant` 经 service 路由的检索链路。
- SSE 中 custom、error、复杂 tool event 的完整契约。
- 真实 checkpointer 中 `/history` 的多轮恢复行为。
- 请求超时、模型失败、工具失败、检索失败时 HTTP/SSE 错误形式。
- 新增 trace、citation 或 latency 字段后的响应兼容性。

## 10. Client 测试覆盖情况

`tests/client/test_client.py` 已覆盖：

- client 初始化和认证 header。
- 同步 `invoke()`。
- 异步 `ainvoke()`。
- 同步 `stream()`。
- 异步 `astream()`。
- `retrieve_info()`。
- `get_history()`。
- `acreate_feedback()`。
- 请求失败时的错误处理。

后续如果响应协议增强，client 侧仍建议补充：

- SSE malformed event 和未知 event 类型。
- error event 的展示与抛出规则。
- 空 token、断线重连或中途终止的处理。
- `user_id`、`agent_config`、新增 trace 参数是否正确透传。
- 含 citation、retrieved docs 或结构化工具结果的消息反序列化。

## 11. Schema 与消息转换覆盖情况

### 11.1 当前覆盖

`tests/service/test_utils.py` 重点验证：

- `HumanMessage` 转换为 human 类型 `ChatMessage`。
- `AIMessage` 转换为 ai 类型 `ChatMessage`。
- `ToolMessage` 转换为 tool 类型 `ChatMessage`。
- AI tool calls 的保留。
- `run_id` 等相关字段处理。
- 不支持的消息类型异常。

接口和 client 测试也间接使用了 `UserInput`、`StreamInput`、`ChatMessage`、`ChatHistory` 等 schema。

### 11.2 缺口

- 缺少对 `schema.py` 中每个 Pydantic 模型的独立序列化、校验和默认值测试。
- `convert_message_content_to_string()` 对列表内容、模型特有 block 内容的行为缺少直接测试。
- `remove_tool_calls()` 对流式 Anthropic 风格 `tool_use` block 的过滤缺少直接测试。
- 后续若加入 `trace_id`、`latency_ms`、`retrieved_docs`、`source_citations`，当前缺少回归契约的测试基础。

## 12. Settings 与 LLM 配置覆盖情况

### 12.1 `settings.py`

`tests/core/test_settings.py` 已覆盖：

- HTTP URL 校验辅助逻辑。
- 部分默认设置。
- 没有任何 LLM Provider key 时抛错。
- OpenAI、Anthropic、Vertex 和多 Provider 场景。
- `BASE_URL`。
- `is_dev`。
- Azure API key 与 deployment 配置校验。

尚缺少：

- DeepSeek、Google、Groq、AWS Bedrock、Ollama、OpenRouter、Compatible OpenAI、Fake Model 的完整 settings 分支。
- database 后端选择配置。
- tracing 环境变量配置。
- `.env.example` 与实际 Settings 字段一致性的契约验证。

### 12.2 `llm.py`

`tests/core/test_llm.py` 已覆盖：

- OpenAI。
- Anthropic。
- Groq 普通与 safeguard 分支。
- Ollama。
- Fake Model。
- 非法模型名。

尚缺少：

- DeepSeek。
- Google 与 Vertex。
- AWS Bedrock。
- OpenRouter。
- OpenAI Compatible。
- Azure。
- `@cache` 是否复用同一模型对象。
- key/base URL/deployment 缺失时的报错路径。
- timeout、retry、temperature、streaming 参数契约。
- 未来 fallback 与成本统计逻辑。

## 13. Memory、Checkpointer、Store 与 History 覆盖情况

当前 memory 相关测试主要出现在 service 边界：

- `test_service_lifespan.py` 使用 fake saver/store 验证初始化后注入 Agent。
- `test_service.py` 通过 mock graph state 验证 `/history` 输出。
- `test_service_e2e.py` 使用 `MemorySaver` 验证自定义图与消息流。

但没有直接验证：

- `src/memory/sqlite.py` 的真实 checkpointer 行为。
- `src/memory/postgres.py` 的连接池、setup 与持久化行为。
- `src/memory/mongodb.py` 的连接 URL 和 saver 行为。
- `DATABASE_TYPE` 对 saver/store 后端选择的完整分支。
- Mongo 选择下 saver 与 in-memory store 的组合行为。
- 同一 `thread_id` 的多轮对话恢复。
- 不同 `thread_id` 的消息隔离。
- 同一 `user_id` 跨线程长期记忆读取。
- 记忆裁剪、删除和数据保留策略。

这意味着当前项目能说明“memory 被接入了服务”，还不能通过测试充分说明“多轮状态与长期记忆在真实后端可靠运行”。

## 14. Fake Model 在测试中的作用

项目中的 Fake Model 用于让测试避开真实大模型依赖：

- `src/core/llm.py` 中的 `FakeToolModel` 继承 Fake Chat Model，并实现 `bind_tools()`，以兼容工具绑定场景。
- `tests/core/test_llm.py` 验证 Fake Model 可以被创建。
- 部分 service 测试使用自定义 fake 或 mock agent 输出稳定消息。
- Docker 端到端场景可通过 Fake Model 降低对外部服务的依赖。

Fake Model 当前最大的价值是：

- 测试不依赖 API key 额度、外部网络和模型输出随机性。
- 可重复验证流式输出与基础接口协议。
- 为未来验证工具路由 StateGraph 提供合适基础。

不过，当前还没有充分利用 Fake Model 来驱动默认 `research_assistant` 或 `rag_assistant` 的真实工具调用循环。后续可设计一个会先返回 tool call、收到 `ToolMessage` 后再返回最终答案的 fake model，用来覆盖真正的 Agent 图链路。

## 15. 当前测试体系最大的空白

### 15.1 Agent 完整执行行为未被保护

已有测试验证了工具函数和提示词，但没有真正验证默认 Agent 在用户请求下：

- 是否选择正确工具。
- 是否执行 `ToolNode`。
- 是否将工具结果交回模型。
- 是否在安全、失败、步数不足等情况下正确退出。

### 15.2 RAG 召回质量未被度量

RAG 测试目前偏向代码机制与答案模板，没有黄金问答集、召回命中率、来源正确性、拒答准确性等质量指标。

### 15.3 Memory 的真实持久化与隔离行为未被验证

项目支持 SQLite、Postgres、Mongo 多种 checkpointer/store 形态，但测试未建立真实 conversation lifecycle 的信心。

### 15.4 生产级错误与可观测能力未被验证

模型超时、工具异常、检索失败、SSE 中断、fallback、trace 和来源引用等后续关键能力，目前没有现成的回归保护层。

## 16. 不同优化方向开始前应补的测试

### 16.1 做 RAG 优化前

- 建立校园制度黄金问题集，定义问题到预期 `source`、章节或 `chunk_id` 的映射。
- 测试真实建库后 top-k 是否命中期望内容。
- 测试无答案问题是否拒答而非编造。
- 测试低相关文档、多个相近制度、跨章节回答。
- 测试 metadata 增强后基于制度类型/章节过滤。
- 测试增量建库、重复写入和文档删除后的索引一致性。
- 测试 `Database_Search` 和 `rag_assistant` 完整链路。

### 16.2 做 Router 优化前

- 建立意图到工具的用例表：课程、活动、学习计划、制度、普通聊天、混合意图。
- 验证普通概念问答不会误触工具。
- 验证多工具问题的选择顺序或组合策略。
- 使用可触发 tool call 的 fake model 跑通 StateGraph 和 ToolNode。
- 对安全拦截、工具失败后回退回答建立测试。

### 16.3 做 Trace 优化前

- 验证请求级 `run_id` / `trace_id` 能进入最终响应和流式 event。
- 验证 model/tool/retrieval 节点耗时记录。
- 验证 RAG 检索的 source、chunk、score 等记录可追溯。
- 验证异常路径仍能落 trace 并带错误阶段信息。
- 验证 SSE 多事件共享同一 trace 标识。

### 16.4 做 Fallback 与异常兜底前

- 模型 timeout、鉴权失败和 provider 不可用时的 fallback 测试。
- 工具 JSON 文件缺失、字段不完整、读取失败场景。
- Chroma 路径不存在、embedding 初始化失败、检索异常场景。
- 服务的 HTTP 错误与 SSE error event 契约。
- Agent 不可加载、非法 agent/model 参数的用户友好返回。

### 16.5 做 Schema 扩展前

- 为所有请求和响应 schema 增加独立序列化/反序列化测试。
- 增加 history 和 stream 中扩展字段向后兼容测试。
- 增加结构化工具结果、citation 和 retrieved documents 的解析测试。
- 增加 client 与 Streamlit 对新消息类型的展示测试。

### 16.6 做 Memory 优化前

- 验证同一 `thread_id` 下第二轮请求能读取第一轮消息。
- 验证不同线程之间消息不串联。
- 验证同一 `user_id` 跨线程的长期 store 数据使用方式。
- 对 SQLite 建立可运行的持久化集成测试。
- 对 Postgres/Mongo 建立可选 Docker 集成测试。
- 测试历史裁剪、清理、过期和删除策略。

## 17. 推荐新增测试文件列表

| 优先级 | 推荐文件 | 目标 |
| --- | --- | --- |
| P0 | `tests/agents/test_research_assistant_graph.py` | 验证默认 Agent 真实 StateGraph 工具循环与安全分支 |
| P0 | `tests/agents/test_rag_assistant.py` | 验证 RAG Agent 绑定工具、检索调用和拒答链路 |
| P0 | `tests/agents/test_database_search_tool.py` | 覆盖 `Database_Search` 工具成功、无结果和失败情况 |
| P0 | `tests/rag/test_retrieval_quality.py` | 使用黄金问题集验证召回内容与来源 |
| P0 | `tests/service/test_multiturn_history.py` | 验证 thread_id 下的多轮消息状态恢复 |
| P1 | `tests/agents/test_calculator_tool.py` | 覆盖数学表达式、常量和错误输入 |
| P1 | `tests/agents/test_tool_error_handling.py` | 覆盖 JSON、检索器和工具执行异常 |
| P1 | `tests/rag/test_incremental_indexing.py` | 覆盖增量、去重、更新和删除场景 |
| P1 | `tests/memory/test_memory_selection.py` | 覆盖 DATABASE_TYPE 后端选择 |
| P1 | `tests/memory/test_sqlite_checkpoint.py` | 覆盖本地可执行持久化链路 |
| P1 | `tests/core/test_model_fallback.py` | 覆盖模型失败与 fallback 策略 |
| P1 | `tests/service/test_trace_metadata.py` | 覆盖 trace 和耗时扩展字段 |
| P2 | `tests/schema/test_schema.py` | 独立验证请求、响应与扩展 schema 契约 |
| P2 | `tests/service/test_extended_message_serialization.py` | 覆盖来源引用和结构化内容序列化 |
| P2 | `tests/client/test_extended_stream_events.py` | 覆盖新增 SSE 事件和错误事件 |
| P2 | `tests/memory/test_postgres_store.py` | 可选容器场景验证 Postgres 存储 |
| P2 | `tests/memory/test_mongodb_saver.py` | 可选容器场景验证 Mongo checkpoint |

## 18. 建议的测试演进顺序

新手继续阅读和补测试时，可以按下面顺序推进：

1. 先读工具测试：`test_campus_course_schedule_tool.py`、`test_campus_events_tool.py`、`test_study_plan_tool.py`、`test_campus_policy_tool.py`，理解业务规则如何被验证。
2. 再读 `test_tool_routing_prompt.py` 和 `test_day15_tool_call_flow.py`，理解默认 Agent 目前测试到哪里为止。
3. 阅读 `test_service.py`、`test_service_e2e.py` 和 `test_utils.py`，建立请求、消息转换和流式返回视角。
4. 阅读 `test_client.py` 与 `test_streamlit_app.py`，把接口数据如何回到 UI 串起来。
5. 阅读 `test_build_campus_kb.py`，理解 RAG 建库当前能测试什么。
6. 阅读 `test_settings.py` 与 `test_llm.py`，理解测试如何隔离模型 Provider 配置。
7. 最后新增 Agent Graph、RAG 召回质量和 Memory 多轮状态测试，这三部分最能提升优化时的安全感。

## 19. 面试表达

可以这样介绍当前测试体系：

> 当前项目的测试按照应用层次组织，覆盖 Agent 工具、FastAPI 服务、Python Client、模型配置、RAG 建库、Streamlit 界面和语音能力。工具层已经对课程查询、校园活动、学习计划和制度问答主要规则路径进行了单元测试；服务层覆盖了 `/invoke`、`/stream`、`/history`、`/info`、`/feedback` 以及认证；client 层覆盖同步、异步、流式和错误请求；RAG 建库层覆盖 Markdown 加载、chunk metadata 与 Chroma 持久化。测试通过 mock agent、fake retriever 和 fake model 来避免依赖真实外部 API。

还可以主动补充目前的不足与规划：

> 当前测试更偏模块级和接口级验证，默认 Agent 与 RAG Agent 的真实图路由、真实检索质量、持久化多轮记忆，以及 Trace 和 Fallback 仍需增强。后续优先补充三个方向：第一，用支持 tool call 的 fake model 跑通 Agent 图执行；第二，建设校园制度黄金问题集并验证召回来源；第三，基于 thread_id 与 user_id 补充多轮状态和长期记忆隔离测试。这样可以让后续的 Router、RAG 和可观测性优化都有可靠的回归保护。

## 20. 总结

当前测试体系已经能保护不少基础业务能力：

- 校园工具主要规则路径可验证。
- FastAPI 和 Client 的核心交互契约具备测试。
- 建库脚本和部分模型配置分支已建立测试基础。
- Streamlit 与语音模块也有相应验证。

接下来最值得优先补足的不是重复增加简单函数测试，而是覆盖真正影响 Agent 质量的三条主链路：

1. 默认 Agent 与 RAG Agent 的完整图执行和工具调用。
2. 真实校园制度知识库的检索质量与拒答可靠性。
3. thread/user 维度的多轮状态和长期记忆持久化行为。

这些测试补齐后，项目进行性能优化、RAG 优化、Prompt/Router 优化以及异常兜底改造时，就会拥有更稳固、可度量的验证基础。
