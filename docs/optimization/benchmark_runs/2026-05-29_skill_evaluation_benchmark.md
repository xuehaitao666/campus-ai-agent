# Skill Evaluation Benchmark

**Generated**: 2026-05-29T11:22:22.631131+00:00
**Total cases**: 21

## 1. Summary

| Metric | Value |
| --- | ---: |
| Route Accuracy | 100.00% |
| Skill Accuracy | 100.00% |
| Fast Path Accuracy | 100.00% |
| Fast Path Hit Rate | 85.71% |
| Fallback Rate | 14.29% |

## 2. Per-category Results

| Category | Count | Route Accuracy | Skill Accuracy |
| --- | ---: | ---: | ---: |
| course | 4 | 100.00% | 100.00% |
| event | 4 | 100.00% | 100.00% |
| general | 3 | 100.00% | 100.00% |
| policy | 5 | 100.00% | 100.00% |
| study | 5 | 100.00% | 100.00% |

## 3. Per-skill Results

| Skill | Expected Count | Predicted Count |
| --- | ---: | ---: |
| (none) | 3 | 3 |
| course_query | 4 | 4 |
| event_query | 4 | 4 |
| policy_qa | 5 | 5 |
| study_plan | 5 | 5 |

## 4. Failure Cases

No failures.

## 5. Case-level Results

| ID | Query | Expected Intent | Predicted Intent | Expected Skill | Predicted Skill | Fast Path | Result |
| --- | --- | --- | --- | --- | --- | --- | --- |
| course_001 | 我周一上午有什么课？ | course_schedule | course_schedule | course_query | course_query | True | PASS |
| course_002 | 数据结构课在哪里上？ | course_schedule | course_schedule | course_query | course_query | True | PASS |
| course_003 | 我周二下午有课吗？ | course_schedule | course_schedule | course_query | course_query | True | PASS |
| course_004 | 操作系统课在哪里上？ | course_schedule | course_schedule | course_query | course_query | True | PASS |
| event_001 | 这周有什么 AI 相关讲座？ | campus_event | campus_event | event_query | event_query | True | PASS |
| event_002 | 最近有什么比赛可以报名？ | campus_event | campus_event | event_query | event_query | True | PASS |
| event_003 | 有没有适合软件工程学生的活动？ | campus_event | campus_event | event_query | event_query | True | PASS |
| event_004 | 最近有什么宣讲会？ | campus_event | campus_event | event_query | event_query | True | PASS |
| policy_001 | 请假流程是什么？ | campus_policy | campus_policy | policy_qa | policy_qa | True | PASS |
| policy_002 | 挂科了还能申请奖学金吗？ | campus_policy | campus_policy | policy_qa | policy_qa | True | PASS |
| policy_003 | 宿舍晚归会怎么处理？ | campus_policy | campus_policy | policy_qa | policy_qa | True | PASS |
| policy_004 | 考试作弊有什么后果？ | campus_policy | campus_policy | policy_qa | policy_qa | True | PASS |
| policy_005 | 生病缺考怎么办？ | campus_policy | campus_policy | policy_qa | policy_qa | True | PASS |
| study_001 | 帮我制定一份 7 天 AI Agent 学习计划 | study_plan | study_plan | study_plan | study_plan | True | PASS |
| study_002 | 帮我准备 AI Agent 面试学习路线 | study_plan | study_plan | study_plan | study_plan | True | PASS |
| study_003 | 结合我的课程表，帮我规划本周学习 | study_plan | study_plan | study_plan | study_plan | True | PASS |
| study_004 | 我明天下午没课，帮我安排学习 | study_plan | study_plan | study_plan | study_plan | True | PASS |
| study_005 | 帮我复习数据库 | study_plan | study_plan | study_plan | study_plan | True | PASS |
| general_001 | 什么是 LangGraph？ | unknown | unknown | - | - | False | PASS |
| general_002 | 请你介绍一下 Transformer | general_chat | general_chat | - | - | False | PASS |
| general_003 | 你好呀 | general_chat | general_chat | - | - | False | PASS |
