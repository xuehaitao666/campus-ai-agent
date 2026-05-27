# Campus Affairs Planner

## 1. Motivation

课程查询、活动查询和制度 RAG 都能回答单一信息问题，但学生实际提出的往往是组合事务，例如“生病缺考如何办理缓考”或“比赛报名和课程时间冲突怎么办”。这类问题需要把依据、时间安排和可执行步骤放在同一个结果中，而不是让用户自行拼接多次查询结果。

`plan_campus_affair` 是一个只读、规则式的组合工具。它不调用 LLM，不访问真实教务系统，而是复用已有本地工具，输出稳定的办理建议骨架。

## 2. Supported Affairs

| Affair Type | Typical Keywords | Reused Tools |
| --- | --- | --- |
| `exam_absence` | 请假、生病、缺考、缓考、考试、证明、医院 | `query_campus_policy_func` |
| `scholarship_risk` | 挂科、奖学金、绩点、成绩、不及格、评奖 | `query_campus_policy_func` |
| `schedule_conflict` | 活动、比赛、报名、课程冲突、时间冲突、安排 | `get_course_schedule_func`, `get_campus_events_func` |
| `general` | 未明确命中 | 不调用领域工具，仅提示补充信息 |

## 3. How It Differs from Query Tools

普通查询工具返回单一数据源的查询结果；planner 负责将已有只读能力组织为行动计划：

1. 用规则识别事务类型与初步风险等级。
2. 对制度相关事务复用 RAG，完整保留已有 no-answer 与来源引用文本。
3. 对活动/课程冲突复用课程表和活动查询，提示人工核对时间重叠。
4. 读取本地学生画像，在注意事项中声明建议的上下文与 mock 数据边界。

如果 RAG 返回无明确依据，planner 明确输出“当前知识库中没有找到明确制度依据，建议以学院或教务处最新通知为准”，不会生成确定性的制度结论。

## 4. Output Structure

工具返回 Markdown，固定包含以下区块：

- `事务类型`
- `风险等级`
- `建议步骤`
- `时间线`
- `需要准备的材料`
- `相关课程 / 活动`
- `政策依据`
- `注意事项`

`exam_absence` 与 `scholarship_risk` 的政策依据会原样保留 RAG 输出中的 `source` / `chunk_id`；在请求 Trace 已绑定时，底层 RAG 仍会将结构化 retrieved docs 写入现有 Trace/custom_data 流程。

## 5. Trace and MCP

planner 在请求 Trace context 可用时记录：

- `tool_name = plan_campus_affair`
- `affair_type`
- `related_tools`

制度类事务调用 RAG 时，原有 Trace 继续记录 `retrieved_docs`、来源、chunk 与检索指标。

MCP adapter 同步暴露 `plan_campus_affair`，返回现有只读 JSON envelope，包括 `success`、`content`、`tool_name`、`transport` 与 `latency_ms`。

## 6. Testing

测试覆盖：

- 三类受支持事务的规则识别；
- exam absence 和 scholarship risk 的政策依据/来源保留；
- schedule conflict 对课程与活动结果的组合；
- no-answer 时不编造制度、窗口、电话或网址；
- planner Trace 调用信息；
- MCP adapter 的 JSON 可序列化返回。

测试使用 monkeypatch 替换已有工具返回，不调用真实 LLM 或外部 API。

## 7. Current Limitations

- 第一版冲突判断为提醒式规则，不对自由文本结果做精细时段求交。
- 事务类型分类基于关键词，复杂语义会退回 `general` 或由原 Agent 兜底。
- 输出仍为 Markdown；未来可升级为强类型 `CampusAffairPlan` schema 供前端卡片化展示。
- 本工具只使用本地 mock 数据与知识库，不能代替学校正式办理渠道。

## 8. Interview Talking Points

我在已有查询工具之上增加了一个确定性的组合工具，而不是让 LLM 自由拼装校园制度结论。它先通过轻量规则识别请假缺考、奖学金风险或活动课程冲突，再复用 RAG、课程与活动工具生成固定结构的行动计划。对制度事务，原有 no-answer 与 source/chunk 引用被完整保留；对无依据场景，工具明确要求回到官方通知核实。这样既体现了 Agent 的工具编排能力，也把可信边界、可测试性和 MCP 复用纳入了设计。
