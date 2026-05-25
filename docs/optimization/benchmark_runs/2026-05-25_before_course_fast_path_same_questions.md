# Benchmark Run: before_course_fast_path_same_questions

## 1. Run Metadata

- created_at: 2026-05-25T07:31:53.040665+00:00
- git commit hash: 5b426de
- trace file: /tmp/before_course_fast_path_trace.jsonl
- sample size: 5 valid trace records
- request sample size: 5
- child event count: 0
- skipped invalid JSON lines: 0
- model list: deepseek-chat
- agent list: research-assistant

## 2. Summary

- total_requests: 5
- average_total_latency_ms: 3535.00
- average_llm_time_ms: 3502.92
- average_tool_time_ms: -
- average_retrieval_time_ms: -
- average_prompt_tokens: 5329.00
- average_completion_tokens: 190.00
- average_total_tokens: 5519.00
- error_count: 0
- fallback_count: 0

## 3. Per-query Results

| query | agent_id | model_name | route | tool_calls | retrieved_docs | total_latency_ms | llm_time_ms | tool_time_ms | retrieval_time_ms | prompt_tokens | completion_tokens | total_tokens | error_message |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 我周一有什么课？ | research-assistant | deepseek-chat | stream | get_course_schedule | - | 4263.44 | 4221.41 | - | - | 5661 | 272 | 5933 | - |
| 我周一上午有什么课？ | research-assistant | deepseek-chat | stream | - | - | 2582.25 | 2566.34 | - | - | 3160 | 154 | 3314 | - |
| 我周二下午有什么课？ | research-assistant | deepseek-chat | stream | get_course_schedule | - | 4377.70 | 4333.93 | - | - | 6757 | 168 | 6925 | - |
| 数据结构课在哪里上？ | research-assistant | deepseek-chat | stream | - | - | 2834.51 | 2815.72 | - | - | 3534 | 152 | 3686 | - |
| 操作系统课在哪里上？ | research-assistant | deepseek-chat | stream | get_course_schedule | - | 3617.11 | 3577.21 | - | - | 7533 | 204 | 7737 | - |

## 4. Observations

TODO

## 5. Next Optimization Target

TODO
