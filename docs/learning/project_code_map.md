# Campus AI Agent 项目代码地图

本文用于梳理 Campus AI Agent 当前项目结构、核心文件职责、模块依赖关系和新手阅读顺序。

## 1. 项目目录树

```text
campus-ai-agent
├── src
│   ├── run_service.py                 # FastAPI 后端启动入口
│   ├── run_client.py                  # 命令行 client 调用示例
│   ├── run_agent.py                   # 直接运行默认 LangGraph Agent 的示例
│   ├── streamlit_app.py               # Streamlit 前端入口
│   │
│   ├── agents                         # Agent 定义、注册、工具调用逻辑
│   │   ├── agents.py                  # Agent 注册中心
│   │   ├── research_assistant.py      # 默认校园智能助理 Agent
│   │   ├── rag_assistant.py           # RAG 专用 Agent
│   │   ├── chatbot.py                 # 基础聊天 Agent
│   │   ├── tools.py                   # Tool 工具定义
│   │   ├── campus_prompt.py           # Campus Agent 系统提示词
│   │   ├── safeguard.py               # 输入安全检查
│   │   ├── lazy_agent.py              # 懒加载 Agent 抽象
│   │   ├── command_agent.py           # LangGraph Command 示例
│   │   ├── interrupt_agent.py         # interrupt / resume 示例
│   │   ├── knowledge_base_agent.py    # AWS Bedrock Knowledge Base Agent
│   │   ├── langgraph_supervisor_agent.py
│   │   ├── langgraph_supervisor_hierarchy_agent.py
│   │   ├── bg_task_agent
│   │   │   ├── bg_task_agent.py
│   │   │   └── task.py
│   │   └── github_mcp_agent
│   │       └── github_mcp_agent.py
│   │
│   ├── service
│   │   ├── service.py                 # FastAPI 路由、流式响应、Agent 调用
│   │   └── utils.py                   # LangChain message 与 ChatMessage 转换
│   │
│   ├── client
│   │   └── client.py                  # 调用 FastAPI 服务的 Python client
│   │
│   ├── schema
│   │   ├── schema.py                  # API 请求/响应数据结构
│   │   ├── models.py                  # 模型枚举
│   │   └── task_data.py               # 后台任务 custom data schema
│   │
│   ├── core
│   │   ├── settings.py                # 环境变量与项目配置
│   │   └── llm.py                     # LLM 模型工厂
│   │
│   ├── memory
│   │   ├── __init__.py                # memory 初始化入口
│   │   ├── sqlite.py                  # SQLite checkpointer
│   │   ├── postgres.py                # Postgres checkpointer/store
│   │   └── mongodb.py                 # Mongo checkpointer
│   │
│   └── voice
│       ├── manager.py                 # Streamlit 语音集成层
│       ├── stt.py                     # STT 工厂
│       ├── tts.py                     # TTS 工厂
│       └── providers
│           ├── openai_stt.py
│           └── openai_tts.py
│
├── data
│   ├── campus
│   │   ├── course_schedule.json       # mock 课程表
│   │   ├── campus_events.json         # mock 校园活动
│   │   └── student_profile.json       # mock 学生画像
│   ├── knowledge_base                 # Markdown 校园制度知识库
│   └── vector_store
│       └── campus_policy              # Chroma 向量库
│
├── scripts
│   ├── build_campus_kb.py             # 构建校园制度 RAG 向量库
│   └── create_chroma_db.py            # 通用 Chroma 构建示例
│
├── tests                              # 单元测试、服务测试、集成测试
├── docs                               # 项目文档
├── docker                             # Dockerfile
├── compose.yaml                       # Docker Compose 配置
├── pyproject.toml                     # Python 依赖、工具配置
├── uv.lock                            # uv 锁定文件
├── langgraph.json                     # LangGraph Studio 配置
└── README.md
```

## 2. 项目启动入口

### `src/run_service.py`

后端 FastAPI 服务入口。

主要作用：

- 加载 `.env`
- 读取 `core.settings`
- 启动 `uvicorn`
- 挂载 `service:app`
- 根据 `MODE=dev` 判断是否开启 reload

运行方式：

```bash
python src/run_service.py
```

### `src/streamlit_app.py`

前端 Streamlit 应用入口。

主要作用：

- 初始化页面
- 创建 `AgentClient`
- 获取 `/info`
- 展示 Agent 和模型选择
- 接收用户输入
- 调用后端 `/stream` 或 `/invoke`
- 渲染 AI 消息、工具调用、反馈、语音

运行方式：

```bash
streamlit run src/streamlit_app.py
```

### `src/run_client.py`

命令行 client 示例。

主要作用：

- 创建 `AgentClient`
- 调用后端 invoke / stream
- 演示同步和异步调用方式

### `src/run_agent.py`

绕过 FastAPI 和 Streamlit，直接运行默认 Agent 的示例。

主要用于理解 LangGraph Agent 本身如何被调用。

### `compose.yaml`

Docker Compose 启动入口。

包含：

- `postgres`
- `agent_service`
- `streamlit_app`

运行方式：

```bash
docker compose watch
```

## 3. 后端 FastAPI 相关文件

### `src/service/service.py`

后端最核心文件。

负责：

- 创建 `FastAPI` app
- 定义 API 路由
- 初始化 lifespan
- 初始化 memory checkpointer / store
- 加载所有 Agent
- 把请求转换成 LangGraph 输入
- 调用 Agent
- 处理流式 SSE 响应
- 处理 feedback 和 history

核心接口：

```text
GET  /info
POST /invoke
POST /{agent_id}/invoke
POST /stream
POST /{agent_id}/stream
POST /history
POST /feedback
GET  /health
```

关键函数：

- `lifespan()`：服务启动时初始化数据库、store、Agent
- `_handle_input()`：把用户输入包装成 LangGraph 所需格式
- `invoke()`：非流式调用 Agent
- `message_generator()`：流式调用 Agent，并生成 SSE
- `stream()`：返回 `StreamingResponse`
- `history()`：读取指定 thread 的历史消息

### `src/service/utils.py`

负责 LangChain message 与项目内部 `ChatMessage` 的转换。

主要函数：

- `langchain_to_chat_message()`
- `convert_message_content_to_string()`
- `remove_tool_calls()`

这是后端流式返回和前端渲染之间的桥。

## 4. 前端 Streamlit 相关文件

### `src/streamlit_app.py`

前端主文件。

核心职责：

- 页面配置
- 连接 FastAPI 后端
- 管理 `user_id`
- 管理 `thread_id`
- 管理聊天历史
- 展示侧边栏设置
- 调用 `AgentClient`
- 渲染流式消息
- 渲染工具调用状态
- 渲染自定义后台任务消息
- 提交反馈
- 集成语音输入输出

核心函数：

- `main()`
- `draw_messages()`
- `handle_feedback()`
- `handle_sub_agent_msgs()`
- `get_or_create_user_id()`

### `src/voice/*`

语音相关模块，主要供 Streamlit 使用。

- `voice/manager.py`：Streamlit 语音 UI 集成
- `voice/stt.py`：语音转文本工厂
- `voice/tts.py`：文本转语音工厂
- `voice/providers/openai_stt.py`：OpenAI Whisper STT 实现
- `voice/providers/openai_tts.py`：OpenAI TTS 实现

## 5. Agent 定义、注册、调用相关文件

### `src/agents/agents.py`

Agent 注册中心。

负责：

- 定义默认 Agent：`DEFAULT_AGENT = "research-assistant"`
- 注册所有 Agent
- 提供 `get_agent()`
- 提供 `load_agent()`
- 提供 `get_all_agent_info()`

FastAPI 后端通过这里根据 `agent_id` 获取真正的 LangGraph graph。

### `src/agents/research_assistant.py`

默认校园智能助理 Agent。

这是当前项目最重要的 Agent 文件。

它定义了一个 LangGraph `StateGraph`：

```text
guard_input
    ↓
安全则进入 model
    ↓
如果模型产生 tool_calls
    ↓
tools
    ↓
回到 model
    ↓
没有工具调用则 END
```

核心能力：

- 课程查询
- 校园活动查询
- 学习计划生成
- 校园制度 RAG 问答
- WebSearch
- Calculator
- Weather

### `src/agents/rag_assistant.py`

RAG 专用 Agent。

主要绑定 `Database_Search` 工具，适合专门分析校园制度知识库问答流程。

### `src/agents/chatbot.py`

基础对话 Agent。

结构简单，适合新手理解 LangGraph `@entrypoint()` 模式。

### `src/agents/safeguard.py`

输入安全检查模块。

如果配置了 Groq API，会调用 safeguard 模型检测 prompt injection。没有配置时默认放行。

### `src/agents/lazy_agent.py`

懒加载 Agent 抽象类。

用于需要异步初始化的 Agent，例如 GitHub MCP Agent。

### `src/agents/github_mcp_agent/github_mcp_agent.py`

GitHub MCP Agent。

如果配置 `GITHUB_PAT`，启动时会连接 GitHub MCP 服务并加载工具。

## 6. Tool 工具定义和注册相关文件

### `src/agents/tools.py`

项目工具定义的核心文件。

当前主要工具：

#### `Calculator`

基于 `numexpr` 的数学计算工具。

#### `get_course_schedule`

读取：

```text
data/campus/course_schedule.json
```

用于课程表查询。

支持参数：

- `day`
- `time_period`
- `course_name`

#### `get_campus_events`

读取：

```text
data/campus/campus_events.json
```

用于校园活动查询。

支持参数：

- `keyword`
- `date_range`
- `event_type`
- `target_audience`

#### `generate_study_plan`

读取：

```text
data/campus/student_profile.json
data/campus/course_schedule.json
```

用于生成学习计划。

支持参数：

- `goal`
- `days`
- `available_time`
- `focus_topics`

#### `query_campus_policy`

基于本地 Chroma 向量库检索校园制度。

读取：

```text
data/vector_store/campus_policy
```

用于请假、奖学金、宿舍、考试纪律等制度问答。

#### `database_search`

RAG assistant 使用的通用知识库检索工具。

### Tool 注册位置

工具本身在 `tools.py` 中定义，但是否被 Agent 使用，要看具体 Agent 是否绑定。

例如 `research_assistant.py` 中：

```python
tools = [
    web_search,
    calculator,
    get_course_schedule,
    get_campus_events,
    generate_study_plan,
    query_campus_policy,
]
```

然后通过：

```python
bound_model = model.bind_tools(tools)
```

注册到模型。

## 7. RAG 相关文件

### `src/agents/tools.py`

RAG 查询逻辑在这里：

- `create_campus_policy_embeddings()`
- `load_chroma_db()`
- `query_campus_policy_func()`
- `database_search_func()`

### `src/agents/rag_assistant.py`

RAG Agent 定义。

绑定 `Database_Search` 工具，用于专门的知识库问答。

### `scripts/build_campus_kb.py`

当前校园知识库向量库构建脚本。

输入：

```text
data/knowledge_base/*.md
```

输出：

```text
data/vector_store/campus_policy
```

主要流程：

```text
读取 Markdown
    ↓
切分文本 chunk
    ↓
生成 HuggingFace embeddings
    ↓
写入 Chroma
```

### `data/knowledge_base`

校园制度原始 Markdown 文档。

包括：

- 请假制度
- 奖学金制度
- 宿舍制度
- 考试制度
- 学生手册

### `data/vector_store/campus_policy`

已经构建好的 Chroma 向量库。

### `docs/RAG_Assistant.md`

RAG assistant 使用说明。

注意：其中部分内容仍保留通用模板痕迹，比如 PDF/DOCX 和 `create_chroma_db.py`，而当前校园制度 RAG 更核心的是 `build_campus_kb.py`。

## 8. schema / config / client / tests 职责

### `src/schema`

定义项目的数据协议。

#### `schema/schema.py`

API 请求和响应结构：

- `UserInput`
- `StreamInput`
- `ChatMessage`
- `ToolCall`
- `ServiceMetadata`
- `AgentInfo`
- `Feedback`
- `ChatHistory`

FastAPI、Client、Streamlit 都依赖这里。

#### `schema/models.py`

模型枚举。

包括：

- OpenAI
- Anthropic
- Google
- VertexAI
- Groq
- AWS
- Ollama
- DeepSeek
- OpenRouter
- Fake

#### `schema/task_data.py`

后台任务 Agent 的自定义消息结构。

主要给 `bg-task-agent` 和 Streamlit custom message 渲染使用。

### `src/core`

项目配置和模型工厂。

#### `core/settings.py`

负责读取 `.env` 和环境变量。

包括：

- 服务 host/port
- API key
- 默认模型
- 可用模型
- 数据库类型
- Postgres / Mongo / SQLite 配置
- LangSmith / Langfuse 配置
- MCP 配置

#### `core/llm.py`

根据模型枚举创建对应 LangChain Chat Model。

核心函数：

```python
get_model(model_name)
```

所有主要 Agent 都通过它拿模型。

### `src/client`

#### `client/client.py`

Python client，封装对 FastAPI 的调用。

核心能力：

- `retrieve_info()`
- `invoke()`
- `ainvoke()`
- `stream()`
- `astream()`
- `get_history()`
- `acreate_feedback()`

Streamlit 前端主要通过它访问后端。

### `tests`

测试目录覆盖比较完整。

主要分类：

- `tests/agents`：工具、Agent loading、tool routing 测试
- `tests/service`：FastAPI 接口、流式响应、认证、lifespan 测试
- `tests/client`：AgentClient 测试
- `tests/core`：settings 和 llm 测试
- `tests/rag`：知识库构建测试
- `tests/voice`：STT / TTS / VoiceManager 测试
- `tests/app`：Streamlit app 相关测试
- `tests/integration`：Docker 端到端测试

## 9. 文件之间的大致依赖关系

### 前端调用链

```text
src/streamlit_app.py
    ↓
src/client/client.py
    ↓
FastAPI HTTP API
    ↓
src/service/service.py
    ↓
src/agents/agents.py
    ↓
具体 Agent graph
    ↓
LLM / tools / RAG / memory
```

### 后端 Agent 调用链

```text
src/service/service.py
    ↓ get_agent(agent_id)
src/agents/agents.py
    ↓
src/agents/research_assistant.py
    ↓ bind_tools(...)
src/agents/tools.py
    ↓
data/campus/*.json
data/vector_store/campus_policy
```

### 模型调用链

```text
Agent 文件
    ↓
core.get_model(...)
    ↓
src/core/llm.py
    ↓
src/core/settings.py
    ↓
.env / environment variables
```

### RAG 构建链路

```text
data/knowledge_base/*.md
    ↓
scripts/build_campus_kb.py
    ↓
HuggingFaceEmbeddings
    ↓
Chroma
    ↓
data/vector_store/campus_policy
```

### RAG 查询链路

```text
用户制度问题
    ↓
research_assistant
    ↓
query_campus_policy
    ↓
load_chroma_db()
    ↓
data/vector_store/campus_policy
    ↓
返回检索片段
    ↓
LLM 组织回答
```

### 记忆链路

```text
src/service/service.py lifespan()
    ↓
memory.initialize_database()
memory.initialize_store()
    ↓
SQLite / Postgres / Mongo
    ↓
agent.checkpointer
agent.store
```

## 10. 后续重点理解文件

### 性能优化必须重点理解

1. `src/service/service.py`

原因：

- 负责 FastAPI 请求处理
- 负责流式响应
- 负责 Agent 调用
- 负责 lifespan 初始化
- 是并发、延迟、错误处理的核心位置

2. `src/client/client.py`

原因：

- 控制 HTTP 调用方式
- 控制流式解析
- 影响前端响应体验

3. `src/streamlit_app.py`

原因：

- 负责 UI 渲染和状态管理
- 流式 token 渲染性能、工具状态渲染、rerun 行为都在这里

4. `src/core/llm.py`

原因：

- 控制模型初始化
- 有 `@cache`
- 模型 streaming、temperature、provider 配置都在这里

5. `src/memory/*`

原因：

- checkpointer/store 会影响多轮对话性能
- Postgres 连接池配置会影响服务稳定性

### RAG 优化必须重点理解

1. `scripts/build_campus_kb.py`

原因：

- 控制文档加载
- 控制 chunk size
- 控制 chunk overlap
- 控制 embedding model
- 控制 metadata

2. `src/agents/tools.py`

原因：

- `load_chroma_db()`
- `query_campus_policy_func()`
- 相关性判断
- 来源格式化
- no answer 策略

3. `src/agents/rag_assistant.py`

原因：

- 专门的 RAG Agent
- 适合实验不同 RAG prompt 和工具调用策略

4. `data/knowledge_base/*.md`

原因：

- RAG 质量首先取决于原始知识库质量
- Markdown 标题结构、条款表达、来源信息都会影响检索效果

5. `data/vector_store/campus_policy`

原因：

- 当前 Chroma 存储位置
- 优化 embedding 或 chunk 后需要重建

### Prompt 优化必须重点理解

1. `src/agents/campus_prompt.py`

原因：

- Campus AI Agent 的基础角色设定
- 控制回答边界、语气、工具使用倾向

2. `src/agents/research_assistant.py`

原因：

- 默认 Agent 的完整 system instructions 在这里拼接
- 工具选择规则在这里
- 课程、活动、学习计划、制度问答的回答格式在这里

3. `src/agents/rag_assistant.py`

原因：

- RAG 专用 prompt
- 控制“只基于知识库回答”的行为

4. `src/agents/safeguard.py`

原因：

- 输入安全 prompt
- prompt injection 检测规则

5. `src/agents/langgraph_supervisor_agent.py`

原因：

- 多 Agent 调度 prompt
- 子 Agent 角色分工

## 11. 新手推荐阅读顺序

### 第一阶段：先理解项目怎么跑

1. `README.md`
2. `pyproject.toml`
3. `src/run_service.py`
4. `src/streamlit_app.py`
5. `compose.yaml`

目标：知道项目如何启动，前后端分别是什么。

### 第二阶段：理解一次用户请求怎么走

1. `docs/architecture/request_flow.md`
2. `src/streamlit_app.py`
3. `src/client/client.py`
4. `src/service/service.py`
5. `src/schema/schema.py`

目标：理解用户输入如何从前端到后端，再到 Agent。

### 第三阶段：理解 Agent 系统

1. `src/agents/agents.py`
2. `src/agents/research_assistant.py`
3. `src/agents/campus_prompt.py`
4. `src/agents/tools.py`

目标：理解默认校园智能助理如何选择工具、调用模型、返回结果。

### 第四阶段：理解本地校园数据工具

1. `data/campus/course_schedule.json`
2. `data/campus/campus_events.json`
3. `data/campus/student_profile.json`
4. `src/agents/tools.py`

目标：理解课程查询、活动查询、学习计划生成的 mock 数据来源。

### 第五阶段：理解 RAG

1. `data/knowledge_base/*.md`
2. `scripts/build_campus_kb.py`
3. `src/agents/tools.py`
4. `src/agents/rag_assistant.py`
5. `docs/RAG_Assistant.md`

目标：理解知识库如何构建、如何检索、如何交给 Agent 回答。

### 第六阶段：理解模型和配置

1. `src/core/settings.py`
2. `src/core/llm.py`
3. `.env`

目标：理解模型 provider、默认模型、API key、数据库配置。

### 第七阶段：理解记忆和多轮对话

1. `src/memory/__init__.py`
2. `src/memory/sqlite.py`
3. `src/memory/postgres.py`
4. `src/service/service.py` 中的 `lifespan()` 和 `_handle_input()`

目标：理解 `thread_id`、`user_id`、checkpointer、store 的作用。

### 第八阶段：通过测试反向理解行为

1. `tests/agents/test_campus_course_schedule_tool.py`
2. `tests/agents/test_campus_events_tool.py`
3. `tests/agents/test_study_plan_tool.py`
4. `tests/agents/test_campus_policy_tool.py`
5. `tests/service/test_service_streaming.py`
6. `tests/client/test_client.py`

目标：用测试确认每个模块的预期行为。

## 12. 总结

当前 Campus AI Agent 的主线可以概括为：

```text
Streamlit 前端
    ↓
AgentClient
    ↓
FastAPI Service
    ↓
Agent Registry
    ↓
research-assistant
    ↓
LLM + Tools
    ↓
本地 mock 数据 / Chroma RAG / WebSearch / Calculator
```

其中最重要的几个文件是：

```text
src/streamlit_app.py
src/client/client.py
src/service/service.py
src/agents/agents.py
src/agents/research_assistant.py
src/agents/tools.py
src/agents/campus_prompt.py
src/core/settings.py
src/core/llm.py
scripts/build_campus_kb.py
```

如果后续要做性能优化，重点看：

```text
src/service/service.py
src/client/client.py
src/streamlit_app.py
src/core/llm.py
src/memory/*
```

如果后续要做 RAG 优化，重点看：

```text
scripts/build_campus_kb.py
src/agents/tools.py
src/agents/rag_assistant.py
data/knowledge_base/*
```

如果后续要做 Prompt 优化，重点看：

```text
src/agents/campus_prompt.py
src/agents/research_assistant.py
src/agents/rag_assistant.py
src/agents/safeguard.py
```
