# Campus Tools MCP Server Adapter

## 1. Why MCP

Campus AI Agent 已经具备可复用的课程、活动、校园制度查询和校园事务规划能力。Model Context Protocol (MCP) 提供了一个标准工具暴露方式，使外部 Agent 或 MCP Client 能发现并调用这些能力，而不必依赖本项目的 FastAPI 对话接口或 LangGraph 图结构。

Phase 5.1 的目标不是替换主系统，而是建立一个轻量、只读、旁路的 MCP server adapter。

## 2. Why a Sidecar Adapter

主 Agent 仍沿用原有工具绑定与 LangGraph 链路。本阶段不将原 Agent 改造为 MCP client，原因是：

- 避免为已经稳定的 `/invoke`、`/stream` 和前端路径引入新的传输依赖；
- adapter 只调用已有 native function，不复制课程、活动或 RAG 业务逻辑；
- 可以独立验证 MCP schema、安全边界和适配开销；
- 外部 Agent 可以选择使用 MCP，而内部主流程没有强制迁移成本。

## 3. Exposed Tools

MCP server 名称为 `campus-ai-agent-tools`，当前注册四个只读工具：

| MCP Tool | Native Function | 参数 | 用途 |
| --- | --- | --- | --- |
| `get_course_schedule` | `agents.tools.get_course_schedule_func` | `day`, `time_period`, `course_name` | 查询本地 mock 课程表 |
| `get_campus_events` | `agents.tools.get_campus_events_func` | `keyword`, `date_range`, `event_type`, `target_audience` | 查询本地 mock 校园活动 |
| `query_campus_policy` | `agents.tools.query_campus_policy_func` | `query` | 查询校园制度知识库 |
| `plan_campus_affair` | `agents.tools.plan_campus_affair_func` | `issue`, `deadline`, `urgency` | 组合只读数据生成事务办理建议 |

工具 adapter 返回 JSON 可序列化 envelope：

```json
{
  "success": true,
  "content": "工具原始结果文本",
  "tool_name": "get_course_schedule",
  "transport": "mcp",
  "latency_ms": 0.42
}
```

异常不会向调用方暴露 Python traceback，而返回：

```json
{
  "success": false,
  "error": "native tool unavailable",
  "tool_name": "get_course_schedule",
  "transport": "mcp",
  "latency_ms": 0.12
}
```

## 4. Local Run

项目的 Python import 约定将 `src/` 放入 module search path。使用 stdio transport 启动 MCP server：

```bash
PYTHONPATH=src uv run python -m mcp_server.server
```

该命令只启动 MCP 进程，不启动 FastAPI，也不会改变 Streamlit 或 LangGraph Agent 的运行方式。

## 5. Testing

运行 MCP adapter 专项测试：

```bash
uv run pytest tests/mcp/test_mcp_tools.py -q
```

测试使用 native mock 或 fake RAG 返回，不调用真实 LLM API，也不需要加载真实外部服务。

## 6. Metrics

第一版 adapter 在每次返回中提供：

- `tool_name`
- `transport = "mcp"`
- `latency_ms`
- `success`
- `error`（仅失败时）

可用于后续评估的指标：

| 指标 | 含义 |
| --- | --- |
| `tool_result_match_rate` | 同输入下 MCP adapter 内容与 native tool 结果一致率 |
| `mcp_adapter_overhead_ms` | 适配层相对 native tool 增加的耗时 |
| `mcp_tool_schema_coverage` | 已暴露工具的参数 schema 覆盖程度 |
| `mcp_error_case_pass_rate` | native 工具失败时 adapter 可控返回的测试通过率 |

本阶段 MCP 调用不依附 FastAPI 请求的 Trace context，因此只在返回 envelope 中记录最小耗时信息。后续如引入 MCP client 请求关联，可为 MCP 调用生成或透传 `trace_id`。

## 7. Security Boundary

此 MCP server 是只读能力出口，仅暴露：

- 课程查询；
- 校园活动查询；
- 校园制度知识库查询。
- 校园事务办理建议生成。

明确不暴露：

- shell 命令执行；
- 文件写入或删除；
- 邮件发送；
- 数据库修改；
- 任意网络请求工具。

校园活动与课程工具读取项目内本地 mock 数据；制度查询沿用项目已有本地 RAG 工具的安全和来源引用策略。

## 8. Current Limitations

- 第一版仅为 server adapter，主 LangGraph 流程仍直接调用 native tools。
- 当前不接入第三方 MCP server。
- MCP 返回结构尚未升级为项目内强类型 schema。
- MCP adapter 的耗时尚未统一写入现有 Agent Trace JSONL。

## 9. Interview Talking Points

我没有为了接入 MCP 重构已有 Agent 主链路，而是先把稳定的只读领域工具包装为独立 MCP server。课程、活动和校园制度查询继续复用原有 native function，MCP adapter 只负责标准化暴露、计时与安全错误 envelope，因此能保证结果一致性并降低改造风险。这个阶段还明确限制为只读工具，不开放 shell、写文件或外部副作用能力；后续如果需要让主 Agent 作为 MCP client，再基于适配开销、工具一致率和 Trace 关联数据做有依据的演进。
