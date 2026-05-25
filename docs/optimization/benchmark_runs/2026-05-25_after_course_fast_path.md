# Benchmark Run: after_course_fast_path

## 1. Run Metadata

- created_at: 2026-05-25T07:16:35.506602+00:00
- git commit hash: bb339f3
- trace file: logs/agent_trace.jsonl
- sample size: 15 valid trace records
- request sample size: 15
- child event count: 0
- skipped invalid JSON lines: 0
- model list: claude-sonnet-4-5, deepseek-chat
- agent list: custom_agent, langgraph-supervisor-hierarchy-agent, research-assistant, static-agent

## 2. Summary

- total_requests: 15
- average_total_latency_ms: 1.48
- average_llm_time_ms: 0.00
- average_tool_time_ms: 0.56
- average_retrieval_time_ms: -
- average_prompt_tokens: 0.00
- average_completion_tokens: 0.00
- average_total_tokens: 0.00
- error_count: 1
- fallback_count: 0

## 3. Per-query Results

| query | agent_id | model_name | route | tool_calls | retrieved_docs | total_latency_ms | llm_time_ms | tool_time_ms | retrieval_time_ms | prompt_tokens | completion_tokens | total_tokens | error_message |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| What is the weather in Tokyo? | custom_agent | deepseek-chat | invoke | - | - | 0.62 | - | - | - | - | - | - | - |
| What is the weather in Tokyo? | research-assistant | claude-sonnet-4-5 | invoke | - | - | 1.15 | - | - | - | - | - | - | - |
| What is the weather in Tokyo? | research-assistant | deepseek-chat | invoke | - | - | 0.47 | - | - | - | - | - | - | - |
| What is the weather in Tokyo? | research-assistant | deepseek-chat | invoke | - | - | 0.45 | - | - | - | - | - | - | - |
| What is the weather in Tokyo? | research-assistant | deepseek-chat | invoke | - | - | 0.02 | - | - | - | - | - | - | agent_config contains reserved keys: {'model'} |
| What is the weather in Tokyo? | research-assistant | deepseek-chat | invoke | - | - | 0.64 | - | - | - | - | - | - | - |
| What is the weather in Tokyo? | research-assistant | deepseek-chat | stream | - | - | 0.49 | - | - | - | - | - | - | - |
| What is the weather in Tokyo? | research-assistant | deepseek-chat | stream | - | - | 0.65 | - | - | - | - | - | - | - |
| What is the weather in Tokyo? | research-assistant | deepseek-chat | stream | - | - | 0.69 | - | - | - | - | - | - | - |
| Test message | static-agent | deepseek-chat | stream | - | - | 0.90 | - | - | - | - | - | - | - |
| Add 2 and 3 | langgraph-supervisor-hierarchy-agent | deepseek-chat | stream | - | - | 12.74 | - | - | - | - | - | - | - |
| 我周一有什么课 | research-assistant | deepseek-chat | course_schedule_fast_path | get_course_schedule | - | 0.75 | 0 | 0.50 | - | 0 | 0 | 0 | - |
| 我周二下午有什么课 | research-assistant | deepseek-chat | course_schedule_fast_path | get_course_schedule | - | 0.64 | 0 | 0.49 | - | 0 | 0 | 0 | - |
| 我周三上午有什么 | research-assistant | deepseek-chat | course_schedule_fast_path | get_course_schedule | - | 0.53 | 0 | 0.36 | - | 0 | 0 | 0 | - |
| 我周一有什么课？ | research-assistant | deepseek-chat | course_schedule_fast_path | get_course_schedule | - | 1.52 | 0 | 0.87 | - | 0 | 0 | 0 | - |

## 4. Observations

TODO

## 5. Next Optimization Target

TODO
