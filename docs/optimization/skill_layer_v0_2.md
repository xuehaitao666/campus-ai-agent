# Campus AI Agent Skill Layer v0.2 阶段性优化留痕

> 状态：已完成 | 日期：2026-05-29 | 关联文件：`src/skills/`、`src/service/service.py`

---

## 1. 优化背景

### 1.1 问题

Campus AI Agent 的 `service.py` 中存在两处硬编码的快路径 if 链：

```python
# invoke() 中
if output := _maybe_handle_course_fast_path(user_input, trace_record):
    ...
if output := _maybe_handle_event_fast_path(user_input, trace_record):
    ...

# message_generator() 中（完全相同的结构再次出现）
if output := _maybe_handle_course_fast_path(user_input, trace_record):
    ...
if output := _maybe_handle_event_fast_path(user_input, trace_record):
    ...
```

这种模式在只有 2 个快路径时勉强可维护，但随着后续接入 `policy_qa`、`study_planner`、`interview_coach` 等技能，if-else 链会线性膨胀，且两处代码完全重复。

### 1.2 目标

- 将快路径分发逻辑从硬编码 if 链收敛为统一的 Skill 执行器
- 保持用户可见行为完全不变
- 保持 trace 字段向后兼容
- 为后续技能扩展建立清晰的接入模式

---

## 2. v0.1 完成内容（Skill metadata 层）

### 2.1 新增文件

```
src/skills/__init__.py
src/skills/base.py                  # SkillExample + SkillMetadata (Pydantic) + SkillRegistry
src/skills/definitions.py           # COURSE_QUERY_SKILL + EVENT_QUERY_SKILL + BUILTIN_SKILLS
src/skills/registry.py              # default_registry 实例
tests/skills/__init__.py (未创建 —— 详见下方注意)
tests/skills/test_skill_registry.py # 12 个元数据校验测试
```

> **注意**：`tests/skills/__init__.py` 刻意不创建。`tests/core/`、`tests/agents/`、`tests/service/` 等现有测试目录均无 `__init__.py`，这样做是为了避免测试目录被 Python 当作包，从而遮盖同名的 `src/skills/` 包。

### 2.2 核心设计

**SkillMetadata** 是对一个已有能力的结构化描述。每个字段都精确映射到现有代码：

| 字段 | course_query 示例值 | 来源 |
|---|---|---|
| `name` | `"course_query"` | 自行命名 |
| `intent` | `RouteIntent.COURSE.value` | `core/router.py:7` |
| `trigger_keywords` | `list(COURSE_KEYWORDS)` | 直接从 `core/router.py` 引用 |
| `fast_path_handler_name` | `"_maybe_handle_course_fast_path"` | `service.py:263` |
| `bound_tools` | `["get_course_schedule"]` | `service.py:285` |
| `response_template_name` | `"format_course_fast_path_response"` | `core/response_templates.py:19` |
| `examples` | 2 个带 expected_params 的样例 | 来自现有测试用例 |

**关键决策**：`trigger_keywords` 不重复定义，直接从 `router.py` 的 `COURSE_KEYWORDS` / `EVENT_KEYWORDS` 常量 import。这保证了 Skill metadata 和 Router 行为始终同步。

### 2.3 约束

v0.1 **不接入执行链路**。不修改 `service.py`、`router.py`、`tools.py`、`response_templates.py`，不改变任何用户可见行为。

### 2.4 测试结果

```
tests/skills/test_skill_registry.py — 12 passed
全量: 332 passed, 1 xfailed, 0 failures
```

---

## 3. v0.2 完成内容（SkillExecutor 接入层）

### 3.1 新增/修改文件

```
src/skills/executor.py              # 新增：try_skill_fast_path()
tests/skills/test_skill_executor.py # 新增：7 个 executor 单元测试
src/service/service.py              # 修改：+1 import, +4 行 map, invoke/message_generator 各 -4+1 行
```

### 3.2 executor.py 设计

`try_skill_fast_path(user_input, trace_record, handlers)` 的核心逻辑：

```
for each skill in registry (fast_path_enabled=True):
    1. route_query() → intent 不匹配则 skip（提前剪枝）
    2. handlers.get(skill.fast_path_handler_name) → 缺失则 log warning + skip
    3. handler(user_input, trace_record) → 异常则 log exception + skip
    4. 返回 None → 继续下一个 Skill
    5. 返回 ChatMessage → 立即返回
全部未命中 → 返回 None
```

**关键设计决策**：

- executor.py **不 import service.py**，避免循环依赖。handler map 由 service.py 作为参数传入
- 采用**显式 `FAST_PATH_HANDLERS` dict** 注册 handler，而非 `getattr(service_module, name)`。原因：
  - 避免 executor.py → service.py 的循环依赖
  - 注册遗漏会在测试中暴露，而非生产环境静默跳过
  - IDE 可追踪函数引用
- handler 失败**不中断主链路**：缺失 handler → warning + skip，handler 异常 → exception log + skip，均 fallback 到 Agent

### 3.3 service.py 改动

**invoke()** 中：

```python
# 改前（2 个 if）
if output := _maybe_handle_course_fast_path(user_input, trace_record):
    trace_record.total_latency_ms = timer.stop()
    _add_trace_custom_data(output, trace_record)
    return output
if output := _maybe_handle_event_fast_path(user_input, trace_record):
    ...

# 改后（1 行）
if output := try_skill_fast_path(user_input, trace_record, FAST_PATH_HANDLERS):
    trace_record.total_latency_ms = timer.stop()
    _add_trace_custom_data(output, trace_record)
    return output
```

**message_generator()** 中同样的替换。

新增 handler 映射：

```python
FAST_PATH_HANDLERS = {
    "_maybe_handle_course_fast_path": _maybe_handle_course_fast_path,
    "_maybe_handle_event_fast_path": _maybe_handle_event_fast_path,
}
```

### 3.4 保持不变的部分

- `_maybe_handle_course_fast_path` 和 `_maybe_handle_event_fast_path` 函数体一字未改
- `route_query()`、`parse_course_query()`、`parse_event_query()` 不变
- `format_course_fast_path_response()`、`format_event_fast_path_response()` 不变
- `get_course_schedule_func()`、`get_campus_events_func()` 不变
- `trace_record.route` 仍为 `"course_schedule_fast_path"` / `"campus_event_fast_path"`

---

## 4. 调用链路对比

### 优化前

```
用户请求
  → service.py invoke() / message_generator()
    → _maybe_handle_course_fast_path()
      → route_query()  → intent==COURSE ?
      → parse_course_query()
      → get_course_schedule_func()
      → format_course_fast_path_response()
    → (如果 course 返回 None)
    → _maybe_handle_event_fast_path()
      → route_query()  → intent==EVENT ?
      → parse_event_query()
      → get_campus_events_func()
      → format_event_fast_path_response()
    → (如果 event 也返回 None)
    → get_agent("research-assistant") → agent.ainvoke() / agent.astream()
```

### 优化后

```
用户请求
  → service.py invoke() / message_generator()
    → try_skill_fast_path(user_input, trace_record, FAST_PATH_HANDLERS)
      → for skill in SkillRegistry (fast_path_enabled=True):
        → route_query() → intent 匹配 skill.intent？
          → (YES) handlers[skill.fast_path_handler_name](user_input, trace_record)
            → handler 内部（逻辑不变）:
              → route_query()
              → parse_*_query()
              → tool_func()
              → format_*_fast_path_response()
          → (NO) 下一个 Skill
    → (全部未命中或 handler 返回 None)
    → get_agent("research-assistant") → agent.ainvoke() / agent.astream()
```

差异：原来在 service.py 层面做 2 次显式 if-else 判断，现在在 SkillExecutor 层面做 1 次循环遍历。调用结果完全等价。

---

## 5. 测试结果

### v0.2 新增测试

```
tests/skills/test_skill_executor.py::test_try_skill_fast_path_executes_course_handler PASSED
tests/skills/test_skill_executor.py::test_try_skill_fast_path_executes_event_handler PASSED
tests/skills/test_skill_executor.py::test_try_skill_fast_path_returns_none_when_no_skill_matches PASSED
tests/skills/test_skill_executor.py::test_try_skill_fast_path_skips_missing_handler PASSED
tests/skills/test_skill_executor.py::test_try_skill_fast_path_uses_first_non_none_result PASSED
tests/skills/test_skill_executor.py::test_try_skill_fast_path_handles_handler_exception_gracefully PASSED
tests/skills/test_skill_executor.py::test_try_skill_fast_path_returns_none_when_all_handlers_return_none PASSED
```

### 现有测试回归

```
tests/core/test_router.py                  — 15 passed
tests/service/test_course_fast_path.py      —  8 passed (含 trace route 断言)
tests/service/test_event_fast_path.py       — 11 passed (含 trace route 断言)
tests/service/test_fast_path_templates.py   —  3 passed
tests/skills/test_skill_registry.py         — 12 passed (v0.1 无回归)
```

### 全量

```
339 passed, 1 xfailed, 0 failures
```

---

## 6. 工程设计亮点

### 6.1 Skill metadata 与执行逻辑解耦

v0.1 只定义元数据，v0.2 才接入执行。两个阶段独立测试、独立回滚。新增 Skill 时，定义和接入也是分离的步骤。

### 6.2 避免循环依赖

`executor.py` 不 import `service.py`。handler 函数引用通过 service.py 主动注册到 executor 的 handler map 中。依赖方向始终是 service → executor，单向无环。

### 6.3 显式注册优于隐式查找

使用 `FAST_PATH_HANDLERS` dict 显式注册每个 handler，而非 `getattr(service_module, name)` 或 `importlib` 动态查找。好处：
- 注册遗漏 → 测试直接暴露（handler 缺失测试会挂）
- 重构 handler 函数名 → IDE 自动更新引用
- 无运行时字符串解析的脆弱性

### 6.4 Trace 向后兼容

`trace_record.route` 保持原值（`"course_schedule_fast_path"` / `"campus_event_fast_path"`）。现有 benchmark、监控面板、日志消费方无需任何改动。未来可通过新增字段（如 `skill_name`）提供 Skill 维度的追踪，而不破坏现有字段。

### 6.5 优雅降级

handler 缺失或异常时，executor 记录 warning/exception 后跳过该 Skill，继续尝试下一个或 fallback 到 Agent。单个 Skill 的故障不会导致整个请求失败。

### 6.6 最小改动量

v0.2 的 service.py 改动：净减约 4 行代码。invoke() 和 message_generator() 的快路径逻辑从 8 行缩减为 3 行。

---

## 7. 面试表达

### 7.1 简历描述版

> 主导 Campus AI Agent 的 Skill Layer 架构设计与实现。将 service.py 中硬编码的快路径 if-else 链重构为基于 SkillRegistry 的可插拔 Skill 执行框架。设计了 SkillMetadata 元数据层（Pydantic）和 SkillExecutor 分发层，实现技能定义与执行的解耦。通过显式 handler 注册避免了模块间循环依赖，handler 异常时优雅降级至通用 Agent 路径。全量 339 个测试零回归，用户可见行为不变，trace 字段向后兼容。

### 7.2 面试讲解版

> 我们有一个校园 AI Agent，最开始只有课程查询和活动查询两个快路径。当时 service.py 里用两个 if-else 分别调用两个 handler，代码量不大，但每次加新技能都要在两处（invoke 和 stream）加同样的 if 块。
>
> 所以我分两步做了 Skill Layer。v0.1 先把已有快路径的"隐藏知识"结构化：每个技能有哪些触发关键词、对应哪个 handler、绑定哪些工具、输出什么格式，全部写成 Pydantic model。这些 metadata 直接从 router.py 的常量引用，保证定义和运行时行为一致。
>
> v0.2 做了接入。写了一个 SkillExecutor，遍历 Registry 里所有 fast_path_enabled 的技能，用 route_query 做 intent 匹配，匹配到了就调对应的 handler。handler 还是原来的 handler，一行没改。executor 不 import service.py，而是由 service.py 把 handler 函数注入到一个 dict 里——这样避免了循环依赖。handler 缺失或抛异常也不打崩主链路，log 一下然后 fallback 到 Agent。
>
> 改动量很小：service.py 净减 4 行，新增约 100 行 executor 代码。全量 339 个测试通过，trace 字段完全向后兼容。

### 7.3 面试追问回答版

**Q: 为什么不直接用 LangGraph 的 subgraph 或 supervisor 模式做技能路由？**

> Subgraph/supervisor 适合做多 Agent 协作，比如一个 Agent 负责课程、另一个负责制度、第三个负责学习计划，supervisor 根据用户意图动态调度。但我们的场景不同：课程查询和活动查询的答案完全确定，不需要 LLM 参与推理。走 subgraph 意味着每个请求都要经过 LLM（哪怕是 supervisor 的意图判断），这对确定性查询来说是浪费。我们的 Skill Layer 快路径完全不调 LLM，total_latency_ms 从 3800ms 降到 ~50ms，token 消耗为零。这是 subgraph 做不到的。当然，v0.3 及以后我们可以把"需要 LLM 推理的 Skill"（如面试教练）用 subgraph 实现，而"确定性查询 Skill"保留快路径——两种模式在同一个 SkillExecutor 框架下共存。

**Q: handler map 显式注册，以后有 50 个 Skill 怎么办？**

> 两个层面的回答。第一，v0.2 只有 2 个 Skill，显式注册完全够用且最安全。第二，当 Skill 数量真的到 50 个时，可以引入自动注册：handler 函数加一个 `@skill_handler("course_query")` 装饰器，装饰器内部调用 `register_handler`。但装饰器方案增加了隐式行为，需要配套的测试来保证没有遗漏。现在不引入，遵循 YAGNI 原则。

**Q: route_query 在 executor 里和 handler 里各调一次，不浪费吗？**

> executor 里的 route_query 调用是"提前剪枝"优化。假设 registry 里有 10 个 Skill，每个 handler 内部都会调 route_query + parse + 参数校验。如果 executor 不提前判断，就要对 10 个 handler 都调一遍。route_query 只是几个关键词的 `in` 操作，开销几乎为零。用一次几乎零开销的词匹配避免 9 次 handler 调用（包括 JSON 文件读取），是值得的。当然，这是一个很小的优化，不是架构决策——去掉 executor 里的 route_query 也不会影响正确性。

---

## 8. v0.3 展望

### 8.1 可接入的新 Skill

基于当前 Router 已支持的 intent（但尚无快路径），v0.3 优先接入：

| Skill | intent | 快路径可行性 | 说明 |
|---|---|---|---|
| `policy_qa_skill` | `campus_policy` | 部分可行 | 同义查询可走缓存快路径；复杂制度推理仍需 LLM |
| `study_planner_skill` | `study_plan` | 可行 | 当前已是规则生成（`generate_study_plan_func`），可直接快路径 |
| `campus_affair_skill` | 组合 intent | 部分可行 | 组合查询需要编排多个工具，可快路径 + LLM 混合 |

### 8.2 非 Router intent 的新 Skill

这些 Skill 当前 Router 不支持，需要扩展分类逻辑或通过工具调用触发：

| Skill | 触发方式 | 说明 |
|---|---|---|
| `interview_coach_skill` | Agent 工具调用 | 角色扮演式 Skill，需要专用 system prompt + 对话管理 |
| `document_qa_skill` | 文件上传触发 | 用户上传文件后的上下文问答 |

### 8.3 基础设施增强

- **Skill-level Trace**：TraceRecord 新增 `skill_name`、`skill_source` 字段，支持按 Skill 维度做性能统计和回归检测
- **Skill Evaluation benchmark**：每个 Skill 关联 10-20 条标准 query，CI 中自动运行端到端评估
- **Plugin Skill 支持**：允许用户通过 YAML + Python handler 自定义 Skill，加载到 Registry 中

---

## 附录：相关文件索引

| 文件 | 版本 | 职责 |
|---|---|---|
| `src/skills/base.py` | v0.1 | SkillExample、SkillMetadata、SkillRegistry |
| `src/skills/definitions.py` | v0.1 | COURSE_QUERY_SKILL、EVENT_QUERY_SKILL、BUILTIN_SKILLS |
| `src/skills/registry.py` | v0.1 | default_registry 实例 |
| `src/skills/executor.py` | v0.2 | try_skill_fast_path() |
| `src/service/service.py` | v0.2 | FAST_PATH_HANDLERS、try_skill_fast_path() 调用 |
| `tests/skills/test_skill_registry.py` | v0.1 | 12 个 metadata 校验测试 |
| `tests/skills/test_skill_executor.py` | v0.2 | 7 个 executor 单元测试 |
