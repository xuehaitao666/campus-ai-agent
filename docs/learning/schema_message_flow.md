# Schema 与消息转换流程分析

本文分析 `src/schema/schema.py` 和 `src/service/utils.py` 中的数据结构与消息转换逻辑。

这两个文件解决的是同一个核心问题：

```text
LangGraph / LangChain 内部消息
    ↓
转换成项目统一的 API 消息格式
    ↓
通过 FastAPI / SSE 返回给 client
    ↓
Streamlit 前端根据 type 渲染
```

## 1. schema.py 的整体作用

`src/schema/schema.py` 是项目的 API 数据协议层。

它定义了：

- 前端请求后端时使用的请求体
- 后端返回给前端的响应体
- Agent 元信息
- 工具调用结构
- 用户反馈结构
- 聊天历史结构

简单说：

```text
schema.py 定义“前后端通信时数据长什么样”
```

FastAPI、AgentClient、Streamlit 都依赖这里的 schema。

## 2. 核心 schema 总览表

| Schema | 类型 | 作用 |
| --- | --- | --- |
| `AgentInfo` | Pydantic Model | 描述一个可用 Agent |
| `ServiceMetadata` | Pydantic Model | `/info` 返回服务元信息 |
| `UserInput` | Pydantic Model | 非流式 `/invoke` 请求体 |
| `StreamInput` | Pydantic Model | 流式 `/stream` 请求体 |
| `ToolCall` | TypedDict | 表示一次工具调用 |
| `ChatMessage` | Pydantic Model | 前后端统一聊天消息格式 |
| `Feedback` | Pydantic Model | 用户反馈请求体 |
| `FeedbackResponse` | Pydantic Model | 反馈接口响应 |
| `ChatHistoryInput` | Pydantic Model | 查询聊天历史请求体 |
| `ChatHistory` | Pydantic Model | 聊天历史响应体 |

## 3. 请求 schema 和响应 schema 的区别

### 请求 schema

请求 schema 表示“前端发给后端的数据”。

主要有：

```text
UserInput
StreamInput
ChatHistoryInput
Feedback
```

例如用户提问时：

```text
message
model
thread_id
user_id
agent_config
```

会被封装成 `UserInput` 或 `StreamInput`。

### 响应 schema

响应 schema 表示“后端返回给前端的数据”。

主要有：

```text
ChatMessage
ServiceMetadata
ChatHistory
FeedbackResponse
```

其中 `ChatMessage` 是最核心的消息响应格式。

## 4. UserInput 定义了哪些字段？

`UserInput` 是普通调用 Agent 的基础请求体。

字段如下：

| 字段 | 类型 | 作用 | 使用时机 |
| --- | --- | --- | --- |
| `message` | `str` | 用户输入内容 | 每次用户提问 |
| `model` | `AllModelEnum | None` | 指定使用哪个 LLM | 前端选择模型后传入 |
| `thread_id` | `str | None` | 多轮对话线程 ID | 恢复或延续同一会话 |
| `user_id` | `str | None` | 用户 ID | 跨线程识别同一用户 |
| `agent_config` | `dict[str, Any]` | 额外 Agent 配置 | 传递自定义 Agent 参数 |

后端在 `src/service/service.py` 的 `_handle_input()` 中使用这些字段。

典型用途：

```text
message -> HumanMessage
model -> RunnableConfig.configurable["model"]
thread_id -> 对话记忆 checkpointer
user_id -> 长期记忆 store
agent_config -> 额外传给 Agent 的配置
```

## 5. StreamInput 和 UserInput 有什么关系？

`StreamInput` 继承自 `UserInput`。

```python
class StreamInput(UserInput):
    stream_tokens: bool = True
```

也就是说，`StreamInput` 拥有 `UserInput` 的所有字段，并额外增加：

| 字段 | 类型 | 作用 |
| --- | --- | --- |
| `stream_tokens` | `bool` | 是否流式返回 LLM token |

区别：

```text
UserInput     -> /invoke，非流式
StreamInput   -> /stream，流式
```

## 6. ChatMessage 是什么？

`ChatMessage` 是项目统一的聊天消息格式。

它用于把 LangChain / LangGraph 内部消息转换成前端能理解的结构。

字段包括：

| 字段 | 类型 | 作用 |
| --- | --- | --- |
| `type` | `"human" | "ai" | "tool" | "custom"` | 消息类型 |
| `content` | `str` | 消息文本内容 |
| `tool_calls` | `list[ToolCall]` | AI 消息中的工具调用 |
| `tool_call_id` | `str | None` | ToolMessage 对应的工具调用 ID |
| `run_id` | `str | None` | 本次运行 ID，用于反馈和追踪 |
| `response_metadata` | `dict[str, Any]` | 模型响应元数据 |
| `custom_data` | `dict[str, Any]` | 自定义事件数据 |

### ChatMessage 支持的类型

```text
human   # 用户消息
ai      # AI 回复或 AI 工具调用请求
tool    # 工具执行结果
custom  # 自定义事件，例如后台任务状态
```

前端 `draw_messages()` 就是根据 `msg.type` 来决定怎么渲染。

## 7. ToolCall 是什么？

`ToolCall` 是一个 `TypedDict`，用于表示模型发起的一次工具调用。

字段包括：

| 字段 | 类型 | 作用 |
| --- | --- | --- |
| `name` | `str` | 工具名称 |
| `args` | `dict[str, Any]` | 工具参数 |
| `id` | `str | None` | 工具调用 ID |
| `type` | 可选 `"tool_call"` | 工具调用类型标记 |

例如模型可能返回：

```python
{
    "name": "get_course_schedule",
    "args": {
        "day": "周一",
        "time_period": "上午"
    },
    "id": "call_xxx",
    "type": "tool_call"
}
```

这个结构会被放到：

```python
ChatMessage.tool_calls
```

前端看到 `tool_calls` 后，会渲染工具调用状态和工具输入参数。

## 8. ServiceMetadata / AgentInfo / Feedback / ChatHistory 的作用

### `AgentInfo`

描述一个 Agent：

```text
key
description
```

例如：

```text
key = research-assistant
description = Campus AI Agent 校园智能助理...
```

### `ServiceMetadata`

`GET /info` 的响应结构。

包含：

```text
agents
models
default_agent
default_model
```

前端启动时会请求 `/info`，用于生成模型选择和 Agent 选择。

### `Feedback`

用户反馈请求体。

包含：

```text
run_id
key
score
kwargs
```

用于把用户评分提交给 LangSmith。

### `FeedbackResponse`

反馈提交成功后的响应：

```python
status = "success"
```

### `ChatHistoryInput`

查询聊天历史时的请求体：

```text
thread_id
```

### `ChatHistory`

聊天历史响应：

```text
messages: list[ChatMessage]
```

## 9. service.py 中 invoke() 和 stream() 使用哪些 schema？

### invoke()

位置：

```text
src/service/service.py
```

接口：

```python
async def invoke(user_input: UserInput, agent_id: str = DEFAULT_AGENT) -> ChatMessage
```

使用：

```text
请求体：UserInput
响应体：ChatMessage
```

### stream()

接口：

```python
async def stream(user_input: StreamInput, agent_id: str = DEFAULT_AGENT) -> StreamingResponse
```

使用：

```text
请求体：StreamInput
响应体：StreamingResponse
```

注意：`stream()` 返回的不是普通 JSON，而是 SSE 文本流。

SSE 中会包含：

```text
token event
message event
error event
[DONE]
```

其中 `message event` 的 content 是 `ChatMessage` 的 JSON。

## 10. AgentClient 如何构造 UserInput / StreamInput？

位置：

```text
src/client/client.py
```

### 非流式调用

`ainvoke()` / `invoke()` 中构造：

```python
request = UserInput(message=message)
```

然后按需填入：

```python
request.thread_id = thread_id
request.model = model
request.agent_config = agent_config
request.user_id = user_id
```

最后发送：

```text
POST /{agent}/invoke
```

### 流式调用

`astream()` / `stream()` 中构造：

```python
request = StreamInput(message=message, stream_tokens=stream_tokens)
```

然后按需填入：

```text
thread_id
model
agent_config
user_id
```

最后发送：

```text
POST /{agent}/stream
```

## 11. LangChain Message 到 ChatMessage 的转换流程

LangGraph 内部使用的是 LangChain 消息类型，例如：

```text
HumanMessage
AIMessage
ToolMessage
LangchainChatMessage(role="custom")
```

但前端不直接处理这些对象。

后端会调用：

```python
langchain_to_chat_message()
```

把它们统一转换成 `ChatMessage`。

转换链路：

```text
LangGraph event
    ↓
LangChain message
    ↓
service/utils.py
    ↓
langchain_to_chat_message()
    ↓
ChatMessage
    ↓
JSON / SSE
    ↓
AgentClient
    ↓
Streamlit draw_messages()
```

## 12. langchain_to_chat_message() 的完整逻辑

位置：

```text
src/service/utils.py
```

函数：

```python
def langchain_to_chat_message(message: BaseMessage) -> ChatMessage:
```

### HumanMessage

如果是：

```python
HumanMessage()
```

转换为：

```python
ChatMessage(
    type="human",
    content=convert_message_content_to_string(message.content),
)
```

作用：表示用户消息。

### AIMessage

如果是：

```python
AIMessage()
```

转换为：

```python
ChatMessage(
    type="ai",
    content=convert_message_content_to_string(message.content),
)
```

如果 AIMessage 中有工具调用：

```python
if message.tool_calls:
    ai_message.tool_calls = message.tool_calls
```

如果有模型响应元数据：

```python
if message.response_metadata:
    ai_message.response_metadata = message.response_metadata
```

作用：表示 AI 回复，或者 AI 发起工具调用。

### ToolMessage

如果是：

```python
ToolMessage()
```

转换为：

```python
ChatMessage(
    type="tool",
    content=convert_message_content_to_string(message.content),
    tool_call_id=message.tool_call_id,
)
```

作用：表示工具执行结果，并通过 `tool_call_id` 对应回具体工具调用。

### LangchainChatMessage(role="custom")

如果是：

```python
LangchainChatMessage()
```

并且：

```python
message.role == "custom"
```

转换为：

```python
ChatMessage(
    type="custom",
    content="",
    custom_data=message.content[0],
)
```

作用：表示自定义事件，例如后台任务进度。

### 不支持的类型

如果遇到其他消息类型：

```python
raise ValueError(...)
```

## 13. convert_message_content_to_string() 解决什么问题？

LangChain message 的 `content` 不一定总是字符串。

有时可能是：

```python
str
```

也可能是：

```python
list[str | dict]
```

例如多模态消息、Anthropic 风格消息、结构化 content block。

`convert_message_content_to_string()` 的作用是把这些内容统一转成字符串。

逻辑：

```text
如果 content 是 str
    直接返回
如果 content 是 list
    遍历每一项
    如果是 str，加入结果
    如果是 dict 且 type == "text"，取 text 字段
最后拼接成字符串
```

解决的问题：

```text
前端 ChatMessage.content 需要稳定是 str
但 LangChain 内部 content 可能是复杂结构
```

所以它是内部消息格式和前端协议之间的兼容层。

## 14. remove_tool_calls() 的作用是什么？

`remove_tool_calls()` 用于处理流式 token 内容。

位置：

```text
src/service/utils.py
```

逻辑：

```text
如果 content 是 str，直接返回
如果 content 是 list，则过滤掉 type == "tool_use" 的 content block
```

注释中说明：

```text
Currently only Anthropic models stream tool calls, using content item type tool_use.
```

也就是说，有些模型在流式输出中会把工具调用信息作为 content block 发出来。

但前端 token 流只应该显示自然语言文本，不应该把工具调用 JSON 或内部 tool_use block 当作普通文本显示给用户。

所以在 `message_generator()` 中：

```python
content = remove_tool_calls(msg.content)
```

再把 content 作为 token 返回。

## 15. SSE 与 ChatMessage 的关系

流式接口 `/stream` 返回 SSE，不是一次性 JSON。

后端会发送几类事件：

### token event

```text
data: {"type": "token", "content": "..."}
```

含义：

```text
模型正在流式输出的文本 token
```

前端收到后作为字符串处理，不是 ChatMessage。

### message event

```text
data: {"type": "message", "content": {...ChatMessage...}}
```

含义：

```text
完整结构化消息
```

其中 `content` 是：

```python
chat_message.model_dump()
```

也就是 `ChatMessage` 的 JSON。

### error event

```text
data: {"type": "error", "content": "Unexpected error"}
```

client 会把它包装成：

```python
ChatMessage(type="ai", content="Error: ...")
```

### done event

```text
data: [DONE]
```

表示流结束。

## 16. SSE token / message / custom event 和 ChatMessage 的关系

可以这样理解：

```text
SSE 是传输外壳
ChatMessage 是结构化消息内容
```

关系如下：

| SSE type | 是否是 ChatMessage | 前端处理方式 |
| --- | --- | --- |
| `token` | 否 | 当作字符串追加到当前 AI 消息 |
| `message` | 是 | 解析成 ChatMessage |
| `error` | 转成 ChatMessage | 显示错误消息 |
| `[DONE]` | 否 | 结束流 |
| `custom` | 最终封装成 ChatMessage(type="custom") | 渲染后台任务状态 |

在后端 `message_generator()` 中，custom stream event 会先变成 LangChain custom message，再通过：

```python
langchain_to_chat_message()
```

变成：

```python
ChatMessage(type="custom")
```

## 17. 前端 draw_messages() 为什么能根据 ChatMessage type 渲染不同消息？

因为 `ChatMessage.type` 是一个明确枚举：

```python
Literal["human", "ai", "tool", "custom"]
```

前端 `draw_messages()` 中使用：

```python
match msg.type:
    case "human":
        ...
    case "ai":
        ...
    case "custom":
        ...
    case _:
        ...
```

对于 AI 消息，还会检查：

```python
msg.tool_calls
```

如果有工具调用，就创建工具状态容器。

随后它会继续从流里读取对应的：

```python
ChatMessage(type="tool")
```

并根据：

```python
tool_result.tool_call_id
```

把工具结果放回对应工具调用状态里。

所以前端能正确渲染，是因为后端把 LangChain 的消息类型统一转换成了 `ChatMessage.type`。

## 18. 当前实现风险点

### 1. ChatMessage.content 只能是 str

当前 schema 中：

```python
content: str
```

这对普通文本足够，但对结构化工具结果不够友好。

例如课程查询、活动查询、RAG 来源，本可以用结构化 JSON 表达，但现在多被压成字符串。

### 2. ToolCall args 类型宽松

```python
args: dict[str, Any]
```

灵活但缺少参数 schema 约束。

前端无法知道不同工具的参数结构。

### 3. custom_data 是通用 dict

```python
custom_data: dict[str, Any]
```

适合扩展，但缺少强类型。

如果 custom event 变多，前端容易出现类型判断混乱。

### 4. response_metadata 没有规范

```python
response_metadata: dict[str, Any]
```

不同模型 provider 返回结构可能不同。

不适合直接用于稳定 UI 展示。

### 5. 缺少 RAG 来源结构

当前没有专门字段表示：

```text
retrieved_docs
source_citations
chunk_id
score
```

所以 RAG 来源只能塞进 `content` 或 `custom_data`。

### 6. 缺少 Trace 信息

当前 `ChatMessage` 有：

```text
run_id
```

但没有：

```text
trace_id
node_name
latency_ms
tool_latency_ms
retrieval_latency_ms
```

后续做可观测性 UI 会受限。

### 7. SSE token 和最终 message 可能重复

流式 token 会先显示，随后完整 `AIMessage` 也可能返回。

当前前端通过 placeholder 更新来处理，但复杂工具场景下仍需要小心重复渲染。

## 19. 后续优化切入点

### 增加 trace_id

适合扩展：

```python
ChatMessage
```

可以新增：

```text
trace_id
span_id
parent_span_id
node_name
```

用途：

```text
关联 LangSmith / Langfuse / 自定义 trace
```

### 增加 latency_ms

适合扩展：

```python
ChatMessage
```

或新增：

```python
MessageMetrics
```

再挂到：

```python
ChatMessage.metrics
```

### 增加 retrieved_docs

适合扩展：

```python
ChatMessage.custom_data
```

短期可以放在 `custom_data`。

长期建议新增强类型字段：

```python
retrieved_docs: list[RetrievedDocument]
```

其中：

```text
source
path
chunk_id
content
score
metadata
```

### 增加 source_citations

推荐新增：

```python
SourceCitation
```

并挂到：

```python
ChatMessage.source_citations
```

这样前端可以稳定渲染来源引用。

### 结构化工具返回

当前工具结果是 `ToolMessage(content=str)`。

后续可以设计：

```python
ToolResultMessage
```

或在 `ChatMessage.custom_data` 中加入：

```text
tool_name
tool_args
tool_result
tool_status
```

### 更严格的 ToolCall schema

可以为不同工具定义参数 schema，例如：

```text
CourseScheduleArgs
CampusEventsArgs
StudyPlanArgs
PolicyQueryArgs
```

这样前端和测试都更稳定。

## 20. 推荐扩展哪个 schema？

### 要增加 `trace_id`

推荐扩展：

```python
ChatMessage
```

因为 trace 信息应跟随每条消息返回前端。

### 要增加 `latency_ms`

推荐扩展：

```python
ChatMessage
```

或新增：

```python
MessageMetrics
```

再挂到：

```python
ChatMessage.metrics
```

### 要增加 `retrieved_docs`

推荐扩展：

```python
ChatMessage.custom_data
```

短期最快。

长期建议新增：

```python
RetrievedDocument
```

并在 `ChatMessage` 中加：

```python
retrieved_docs: list[RetrievedDocument] = []
```

### 要增加 `source_citations`

推荐新增：

```python
SourceCitation
```

并挂到：

```python
ChatMessage.source_citations
```

这样前端可以稳定渲染来源引用。

### 要增加工具执行详情

推荐扩展：

```python
ChatMessage
```

或新增：

```python
ToolExecutionInfo
```

字段包括：

```text
tool_name
tool_call_id
args
status
latency_ms
error
```

## 21. 面试表达

可以这样解释这部分设计：

> `schema.py` 是项目的 API 协议层，定义了前端和后端通信的数据结构。用户请求通过 `UserInput` 或 `StreamInput` 进入 FastAPI，后端调用 LangGraph 后，会把 LangChain 的 `HumanMessage`、`AIMessage`、`ToolMessage` 统一转换成项目自定义的 `ChatMessage`。`ChatMessage` 用 `type` 字段区分 human、ai、tool 和 custom，因此 Streamlit 前端可以根据不同类型渲染普通消息、AI 回复、工具调用结果和自定义任务状态。

更具体一点：

> `service/utils.py` 是内部消息到 API 消息的转换层。`langchain_to_chat_message()` 负责把 LangChain 消息转换成 `ChatMessage`；`convert_message_content_to_string()` 解决不同模型返回 content 格式不一致的问题；`remove_tool_calls()` 用于在流式 token 中过滤掉 Anthropic 等模型可能输出的 tool_use block，避免把工具调用结构显示给用户。整体上，这套 schema 简洁易用，但对结构化工具结果、RAG 来源引用和 Trace 展示支持不足，后续可以扩展 `ChatMessage`，增加 trace_id、latency_ms、retrieved_docs 和 source_citations 等字段。

## 22. 总结

当前消息流可以概括为：

```text
前端输入
    ↓
UserInput / StreamInput
    ↓
FastAPI
    ↓
LangGraph
    ↓
LangChain Message
    ↓
langchain_to_chat_message()
    ↓
ChatMessage
    ↓
SSE / JSON
    ↓
AgentClient
    ↓
Streamlit draw_messages()
```

最关键的理解点：

```text
1. UserInput 是普通请求体
2. StreamInput 继承 UserInput，用于流式请求
3. ChatMessage 是前端统一渲染的核心消息格式
4. ToolCall 表示 AIMessage 中的工具调用请求
5. ToolMessage 会转换成 ChatMessage(type="tool")
6. SSE 的 message event 中承载 ChatMessage
7. SSE 的 token event 不是 ChatMessage，而是流式字符串
8. 当前 schema 对结构化 RAG 来源和 Trace 支持较弱
9. 后续应重点扩展 ChatMessage 或 custom_data
```
