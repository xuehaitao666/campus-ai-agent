# RAG 后续改造待办

本文档记录当前 Campus AI Agent RAG 实现中已经发现的不足，以及后续可以逐步改造的位置。当前仅作为后续开发备忘，不代表已经实现。

## 一、默认 Agent 未自动进入 RAG

### 当前问题

当前默认 Agent 是 `research-assistant`，不是 `rag-assistant` 或 `knowledge-base-agent`。用户直接询问请假、奖学金、宿舍、考试纪律等制度问题时，默认链路不一定会进入 RAG 检索。

### 后续可修改位置

- `src/agents/agents.py`
- `src/agents/research_assistant.py`
- `src/streamlit_app.py`

### 改造方向

- 方案一：将校园制度检索工具接入默认 `research-assistant`。
- 方案二：前端根据用户选择切换到 `rag-assistant`。
- 方案三：新增路由 Agent，根据问题类型分发到课程、活动、学习计划或 RAG Agent。

## 二、本地 RAG 建库脚本不支持 Markdown

### 当前问题

`scripts/create_chroma_db.py` 当前只支持 `.pdf` 和 `.docx` 文件，会跳过 `data/knowledge_base/*.md` 校园制度文档。

### 后续可修改位置

- `scripts/create_chroma_db.py`
- `data/knowledge_base/`

### 改造方向

- 增加 Markdown 文档加载逻辑。
- 支持加载 `student_handbook.md`、`scholarship_policy.md`、`leave_policy.md`、`dormitory_policy.md`、`exam_policy.md`。
- 保留 Markdown 标题层级，方便后续回答时引用章节来源。

## 三、本地 RAG 未保留来源 metadata

### 当前问题

`Database_Search` 当前通过 `format_contexts()` 只返回 `doc.page_content`，没有返回文件名、标题、章节、页码或 chunk id。最终回答很难稳定包含来源。

### 后续可修改位置

- `src/agents/tools.py`
- `scripts/create_chroma_db.py`

### 改造方向

- 入库时写入 metadata：
  - `source`
  - `title`
  - `section`
  - `file_name`
  - `chunk_id`
- 检索返回时把 metadata 拼入上下文。
- 让回答可以显示类似 `来源：leave_policy.md > 六、常见问题 > Q1`。

## 四、Database_Search 工具描述仍偏通用

### 当前问题

`database_search_func()` 的描述仍是公司手册相关表达，不够贴合 Campus AI Agent 的校园制度知识库。

### 后续可修改位置

- `src/agents/tools.py`

### 改造方向

- 将工具描述改为校园制度知识库检索工具。
- 明确覆盖：
  - 请假流程
  - 奖学金评定
  - 宿舍管理
  - 考试纪律
  - 学生手册

## 五、Chroma 路径写死

### 当前问题

本地 Chroma 向量库路径固定为 `./chroma_db`，不方便区分开发、测试、校园制度专用库或其他知识库。

### 后续可修改位置

- `src/agents/tools.py`
- `scripts/create_chroma_db.py`
- `.env` 或 `src/core/settings.py`

### 改造方向

- 增加环境变量，例如 `CAMPUS_RAG_DB_PATH`。
- 将校园制度知识库放到独立目录，例如 `./chroma_db/campus_policy`。
- 测试环境使用临时 Chroma 路径，避免污染正式库。

## 六、Retriever 每次调用都会重新加载

### 当前问题

`database_search_func()` 每次调用都会执行 `load_chroma_db()`，重新初始化 embedding 和 Chroma retriever。

### 后续可修改位置

- `src/agents/tools.py`

### 改造方向

- 对 retriever 做缓存。
- 在服务启动时加载一次。
- 增加异常处理，向用户返回更明确的“知识库未初始化”提示。

## 七、缺少空检索和低相关度判断

### 当前问题

当前本地 RAG 检索后直接返回拼接文本，没有判断是否真的命中相关内容。如果检索结果质量较差，模型可能仍尝试回答。

### 后续可修改位置

- `src/agents/tools.py`
- `src/agents/rag_assistant.py`

### 改造方向

- 使用带分数的 similarity search。
- 设置最低相关度阈值。
- 当没有明确依据时统一返回：

```text
当前知识库中没有找到明确依据，建议以学校官方通知或辅导员答复为准
```

## 八、来源信息没有结构化返回

### 当前问题

当前 `ChatMessage` 没有单独的 citations 字段，来源只能混在普通回答文本里。前端也没有单独展示来源卡片。

### 后续可修改位置

- `src/schema/schema.py`
- `src/service/utils.py`
- `src/streamlit_app.py`
- `src/agents/tools.py`

### 改造方向

- 在响应 schema 中增加 `sources` 或 `citations`。
- 后端将检索来源结构化返回。
- 前端在回答下方展示来源文件、章节和片段。

## 九、AWS Knowledge Base 依赖外部配置

### 当前问题

`knowledge-base-agent` 依赖 `AWS_KB_ID`。embedding、索引、数据同步都在 AWS 侧，当前本地项目无法直接看到或测试这些配置。

### 后续可修改位置

- `src/agents/knowledge_base_agent.py`
- `.env`
- 部署文档

### 改造方向

- 增加环境变量检查和友好错误提示。
- 增加 AWS KB 配置文档。
- 增加 mock retriever 测试，避免本地开发必须依赖 AWS。

## 十、缺少校园制度 RAG 专项测试

### 当前问题

当前已有工具测试和 Agent 注册测试，但还没有完整覆盖校园制度 RAG 问答的测试。

### 后续可修改位置

- `tests/agents/`
- `tests/service/`
- `data/knowledge_base/`

### 改造方向

新增测试问题：

- 请假流程是什么？
- 生病请假需要什么材料？
- 挂科后还能评奖学金吗？
- 奖学金申请条件是什么？
- 宿舍晚归会怎么处理？
- 宿舍可以使用大功率电器吗？
- 考试作弊有什么后果？
- 如果因为生病缺考怎么办？
- 当前知识库查不到的问题是否能明确说明没有依据？

## 十一、建议后续实施顺序

1. 让 `scripts/create_chroma_db.py` 支持 Markdown。
2. 为 `data/knowledge_base/*.md` 建立校园制度 Chroma 库。
3. 优化 `Database_Search` 工具描述和返回格式。
4. 在检索结果中加入来源 metadata。
5. 将校园制度 RAG 工具接入默认 Agent 或新增路由 Agent。
6. 增加空检索和低相关度判断。
7. 增加 RAG 专项测试。
8. 优化前端来源展示。

## 十二、阶段备注

当前这些内容只是后续改造清单。现阶段不要直接假设校园制度 RAG 已经完成接入；在未完成 Markdown 加载、向量库重建和 Agent 路由前，涉及校园制度的问题仍应提示以知识库依据或学校官方通知为准。
