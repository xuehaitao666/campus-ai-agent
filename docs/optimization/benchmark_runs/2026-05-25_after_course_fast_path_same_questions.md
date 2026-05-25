# Benchmark Run: after_course_fast_path_same_questions

## 1. Run Metadata

- created_at: 2026-05-25T07:34:00.896983+00:00
- git commit hash: 5b426de
- trace file: logs/agent_trace.jsonl
- sample size: 5 valid trace records
- request sample size: 5
- child event count: 0
- skipped invalid JSON lines: 0
- model list: deepseek-chat
- agent list: research-assistant

## 2. Summary

- total_requests: 5
- average_total_latency_ms: 1.19
- average_llm_time_ms: 0.00
- average_tool_time_ms: 0.74
- average_retrieval_time_ms: -
- average_prompt_tokens: 0.00
- average_completion_tokens: 0.00
- average_total_tokens: 0.00
- error_count: 0
- fallback_count: 0

## 3. Per-query Results

| query | agent_id | model_name | route | tool_calls | retrieved_docs | total_latency_ms | llm_time_ms | tool_time_ms | retrieval_time_ms | prompt_tokens | completion_tokens | total_tokens | error_message |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 我周一上午有什么课？ | research-assistant | deepseek-chat | course_schedule_fast_path | get_course_schedule | - | 0.66 | 0 | 0.42 | - | 0 | 0 | 0 | - |
| 我周一有什么课？ | research-assistant | deepseek-chat | course_schedule_fast_path | get_course_schedule | - | 0.62 | 0 | 0.48 | - | 0 | 0 | 0 | - |
| 我周二下午有什么课？ | research-assistant | deepseek-chat | course_schedule_fast_path | get_course_schedule | - | 0.58 | 0 | 0.43 | - | 0 | 0 | 0 | - |
| 数据结构课在哪里上？ | research-assistant | deepseek-chat | course_schedule_fast_path | get_course_schedule | - | 3.67 | 0 | 2.09 | - | 0 | 0 | 0 | - |
| 操作系统课在哪里上？ | research-assistant | deepseek-chat | course_schedule_fast_path | get_course_schedule | - | 0.42 | 0 | 0.28 | - | 0 | 0 | 0 | - |

## 4. Observations

TODO

## 5. Next Optimization Target

TODO
