# Day15 工具调用阶段测试报告

## 一、测试目标

验证 Campus AI Agent 当前三个校园工具的接入、数据读取、工具选择规则和基础返回质量：

- `get_course_schedule`：课程表查询工具。
- `get_campus_events`：校园活动查询工具。
- `generate_study_plan`：学习计划生成工具。

本次测试重点关注：工具是否注册到默认 Agent、是否读取 `data/campus/` 下的 mock 数据、是否能覆盖课程查询、活动查询和学习计划生成场景，以及无匹配结果时是否避免编造。

## 二、测试环境

- 项目目录：`/Users/demensions/Developer/ai-agent-projects/campus-ai-agent`
- Python 环境：项目本地 `.venv`
- 测试框架：`pytest`
- 测试日期：2026-05-23
- mock 数据文件：
  - `data/campus/course_schedule.json`
  - `data/campus/campus_events.json`
  - `data/campus/student_profile.json`

## 三、测试范围

本次测试覆盖以下内容：

- 默认 Agent 的工具注册列表：`src/agents/research_assistant.py` 中的 `tools`。
- 默认 Agent 的 system prompt：`src/agents/research_assistant.py` 中的 `instructions`。
- 三个工具的 description 和参数 schema：`src/agents/tools.py`。
- 三个工具对本地 mock JSON 文件的读取能力。
- 六个 Day15 验收问题的工具匹配和返回结果。
- 无匹配结果时是否返回明确提示，且不编造课程或活动。

说明：本阶段测试以静态工具注册检查、system prompt 规则检查和工具函数直接调用为主；未依赖真实在线 LLM，因此“实际工具”记录为根据当前工具选择规则进行的直接调用结果。

## 四、测试问题与结果

| 编号 | 用户问题 | 预期工具 | 实际工具 | 是否通过 | 问题说明 |
|---|---|---|---|---|---|
| 1 | 我周一上午有什么课？ | `get_course_schedule` | `get_course_schedule` | 通过 | 返回 `数据结构与算法`，包含时间、教室、教师、课程类型、周次和备注，结果来自 `course_schedule.json`。 |
| 2 | 数据结构课在哪里上？ | `get_course_schedule` | `get_course_schedule` | 通过 | 返回 `数据结构与算法`，地点为 `软件楼 A302`，教师为 `刘明`，结果来自 `course_schedule.json`。 |
| 3 | 这周有什么 AI 相关活动？ | `get_campus_events` | `get_campus_events` | 通过 | 正确调用活动工具；由于当前日期为 2026-05-23，`本周` 按自然周计算为 2026-05-18 至 2026-05-24，mock 数据中 AI 活动在 2026-05-25，因此返回无匹配提示，未编造活动。 |
| 4 | 最近有没有适合软件工程学生的讲座？ | `get_campus_events` | `get_campus_events` | 通过 | 返回 `AI Agent 技术分享会`，包含时间、地点、类型、适合人群、主办方、报名方式和简介，结果来自 `campus_events.json`。 |
| 5 | 帮我制定一份 7 天 AI Agent 学习计划。 | `generate_study_plan` | `generate_study_plan` | 通过 | 返回 7 天结构化计划，包含学习时间、主题、实践任务、复盘任务、预期产出和最终建议，结果结合 `student_profile.json` 与 `course_schedule.json`。 |
| 6 | 结合我的课程表，安排一下明天的学习。 | `generate_study_plan` | `generate_study_plan` | 通过 | 返回 1 天学习计划。已修复 `明天` 语义，计划起始日期为 2026-05-24，并保留结合课程表的能力。 |

## 五、发现的问题

1. `generate_study_plan` 对“明天的学习”这类表达支持不够精确：原逻辑会把 `明天` 当作可用时间文本，但计划日期仍从今天开始。
2. `这周有什么 AI 相关活动？` 能正确选择 `get_campus_events`，但在当前 mock 数据和自然周解释下没有匹配活动。该行为符合数据，不属于编造或工具错误；如果产品期望“这周”表示未来 7 天，可后续单独调整日期范围语义。

## 六、修复记录

1. 在 `src/agents/tools.py` 中新增 `_get_plan_start_date()`。
2. `generate_study_plan_func()` 现在会识别 `available_time` 中的 `明天` 或 `tomorrow`，并将计划起始日期顺延一天。
3. 新增 `tests/agents/test_day15_tool_call_flow.py`，覆盖：
   - 三个校园工具是否注册到默认 Agent。
   - 三个 mock JSON 文件是否可读取。
   - system prompt 是否包含工具选择规则。
   - 课程表按星期和时间段查询。
   - 课程表按课程名查询。
   - 活动按关键词查询。
   - 活动按活动类型和适合人群查询。
   - 学习计划默认 7 天生成。
   - 学习计划识别“明天”并结合课程表。
   - 无匹配结果时返回明确提示且不编造。

## 七、剩余风险

1. 当前测试未调用真实在线 LLM，因此不能完全证明所有模型都会稳定产出正确 tool call；已通过 system prompt、工具 description 和工具注册测试降低风险。
2. `本周` 当前按自然周计算，不等同于“未来 7 天”。如果前端用户习惯把“这周/最近”混用，后续可增加更细的日期解析规则。
3. 三个校园工具仍基于本地 mock 数据，不代表真实教务系统、真实校园活动平台或学校正式安排。
4. 校园制度问答尚未接入正式 RAG 知识库，涉及请假、奖学金、宿舍、考试纪律等问题仍应提示以官方文件或辅导员答复为准。

## 八、阶段结论

Day15 阶段测试通过。当前三个校园工具已经接入默认 Agent，能够读取对应 mock 数据文件，并覆盖课程查询、校园活动查询和学习计划生成三个核心场景。无匹配结果时工具会返回明确提示，没有发现编造课程或活动的问题。

当前状态可以作为 v0.2 阶段候选，但建议在打 tag 前根据团队标准再运行一次全量测试，并确认是否接受 `本周` 按自然周解释这一产品语义。
