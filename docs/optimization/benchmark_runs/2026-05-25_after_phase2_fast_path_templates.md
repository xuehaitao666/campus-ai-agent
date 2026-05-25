# Benchmark Run: after_phase2_fast_path_templates

## 1. Run Metadata

- created_at: 2026-05-25T08:10:04.520250+00:00
- git commit hash: 2252c16
- trace file: logs/agent_trace.jsonl
- sample size: 7 valid trace records
- request sample size: 5
- child event count: 2
- skipped invalid JSON lines: 0
- model list: deepseek-chat
- agent list: research-assistant

## 2. Summary

- total_requests: 5
- average_total_latency_ms: 8529.66
- average_llm_time_ms: 4895.26
- average_tool_time_ms: 6023.43
- average_retrieval_time_ms: 18068.67
- average_prompt_tokens: 2764.40
- average_completion_tokens: 282.60
- average_total_tokens: 3047.00
- error_count: 0
- fallback_count: 0

## 3. Per-query Results

| query | agent_id | model_name | route | tool_calls | retrieved_docs | total_latency_ms | llm_time_ms | tool_time_ms | retrieval_time_ms | prompt_tokens | completion_tokens | total_tokens | error_message |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 这周有什么 AI 相关讲座？ | research-assistant | deepseek-chat | campus_event_fast_path | get_campus_events | - | 1.21 | 0 | 0.94 | - | 0 | 0 | 0 | - |
| 最近有没有比赛可以报名？ | research-assistant | deepseek-chat | campus_event_fast_path | get_campus_events | - | 0.85 | 0 | 0.68 | - | 0 | 0 | 0 | - |
| 什么是 LangGraph？ | research-assistant | deepseek-chat | stream | - | - | 7657.45 | 7621.86 | - | - | 2725 | 432 | 3157 | - |
| 什么是 LangGraph？ | research-assistant | deepseek-chat | stream | - | - | 9041.56 | 9020.26 | - | - | 3165 | 501 | 3666 | - |
| 挂科了还能申请奖学金吗？ | research-assistant | deepseek-chat | stream | query_campus_policy | scholarship_policy.md (scholarship_policy.md::chunk-0001), scholarship_policy.md (scholarship_policy.md::chunk-0002), student_handbook.md (student_handbook.md::chunk-0001), leave_policy.md (leave_policy.md::chunk-0003), exam_policy.md (exam_policy.md::chunk-0003) | 25947.22 | 7834.17 | 18068.67 | 18068.67 | 7932 | 480 | 8412 | - |

## 4. Observations

TODO

## 5. Next Optimization Target

TODO
