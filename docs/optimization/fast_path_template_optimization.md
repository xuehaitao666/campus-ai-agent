# Fast Path Template Response Optimization

## 为什么 Fast Path 仍需要模板化响应

课程和校园活动 Fast Path 已经可以跳过 LLM，直接调用本地工具返回结果。这显著降低了确定性查询的延迟与 token 消耗，但工具原始字符串偏向内部数据表达：不同工具的标题、筛选条件说明和下一步提示并不统一。

Phase 2.4 在不改变工具数据与路由行为的情况下，为 Fast Path 增加统一 Markdown 包装，使直查回答更稳定、更易读，也便于后续前端展示升级。

## 不调用 LLM 的收益

模板化过程由本地纯函数完成，不新增模型调用：

- 课程 Fast Path 仍调用 `get_course_schedule`。
- 活动 Fast Path 仍调用 `get_campus_events`。
- `llm_time_ms` 保持为 `0`。
- `prompt_tokens`、`completion_tokens` 与 `total_tokens` 保持为 `0`。
- 无法解析的请求仍进入原 Agent fallback 链路。

因此，模板化提升的是输出一致性，不牺牲既有 Fast Path 性能目标。

## 课程模板设计

课程 Fast Path 响应采用以下 Markdown 结构：

```markdown
## 课程查询结果

### 查询条件
- 问题：...
- 星期：...
- 时间段：...
- 课程关键词：...

### 结果
<现有课程工具返回结果>

### 下一步
你还可以继续按星期、时间段或课程名称查询。
```

仅展示实际解析到的过滤条件，避免输出无意义的空字段。

## 活动模板设计

活动 Fast Path 响应采用以下 Markdown 结构：

```markdown
## 校园活动查询结果

### 查询条件
- 问题：...
- 关键词：...
- 日期范围：...
- 活动类型：...

### 结果
<现有活动工具返回结果>

### 下一步
你还可以继续按日期、活动类型或关键词查询校园活动。
```

该结构复用现有工具过滤条件，不修改 `campus_events.json` 或工具实现。

## 空结果与错误策略

| 情况 | 展示策略 |
| --- | --- |
| 工具返回没有匹配课程/活动 | 显示“暂未找到符合条件的信息”，并提示调整查询条件 |
| Fast Path 工具执行异常 | 返回“查询服务暂时不可用，请稍后重试”的友好信息 |
| 内部异常细节 | 仅保留在 Trace `error_message` 中，不在用户响应中暴露 traceback |
| 无法解析参数或非 Fast Path 意图 | 保持原 Agent fallback 链路 |

## 后续演进方向

当前模板仍基于工具返回的字符串进行包装，是一次低风险的输出层优化。后续可以逐步演进为：

1. 工具返回结构化课程与活动对象，而不是预格式化文本。
2. response template 根据结构化对象生成 Markdown、JSON 或前端展示模型。
3. 前端在不改变查询链路的前提下展示课程列表、活动卡片与筛选条件。
4. 继续使用 Trace 和 benchmark 比较模板化、结构化输出以及前端展示升级后的延迟与错误率。

本阶段不包含学习计划 Fast Path、RAG Fast Path、Hybrid Retrieval 或前端修改。
