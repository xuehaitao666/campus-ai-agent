# Benchmark Run: phase1_baseline

## 1. Run Metadata

- created_at: 2026-05-25T06:55:27.381964+00:00
- git commit hash: 7971508
- trace file: logs/agent_trace.jsonl
- sample size: 15 valid trace records
- request sample size: 15
- child event count: 0
- skipped invalid JSON lines: 0
- model list: claude-sonnet-4-5, deepseek-chat
- agent list: custom_agent, langgraph-supervisor-hierarchy-agent, research-assistant, static-agent

## 2. Summary

- total_requests: 15
- average_total_latency_ms: 1.40
- average_llm_time_ms: -
- average_tool_time_ms: -
- average_retrieval_time_ms: -
- average_prompt_tokens: -
- average_completion_tokens: -
- average_total_tokens: -
- error_count: 1
- fallback_count: 0

## 3. Per-query Results

| query | agent_id | model_name | route | tool_calls | retrieved_docs | total_latency_ms | llm_time_ms | tool_time_ms | retrieval_time_ms | prompt_tokens | completion_tokens | total_tokens | error_message |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 线程 A 的问题 | research-assistant | deepseek-chat | invoke | - | - | 0.71 | - | - | - | - | - | - | - |
| 线程 B 的问题 | research-assistant | deepseek-chat | invoke | - | - | 0.61 | - | - | - | - | - | - | - |
| 查询历史中的工具消息 | research-assistant | deepseek-chat | invoke | - | - | 0.70 | - | - | - | - | - | - | - |
| What is the weather in Tokyo? | research-assistant | deepseek-chat | invoke | - | - | 0.69 | - | - | - | - | - | - | - |
| What is the weather in Tokyo? | custom_agent | deepseek-chat | invoke | - | - | 0.79 | - | - | - | - | - | - | - |
| What is the weather in Tokyo? | research-assistant | claude-sonnet-4-5 | invoke | - | - | 0.70 | - | - | - | - | - | - | - |
| What is the weather in Tokyo? | research-assistant | deepseek-chat | invoke | - | - | 0.46 | - | - | - | - | - | - | - |
| What is the weather in Tokyo? | research-assistant | deepseek-chat | invoke | - | - | 0.46 | - | - | - | - | - | - | - |
| What is the weather in Tokyo? | research-assistant | deepseek-chat | invoke | - | - | 0.02 | - | - | - | - | - | - | agent_config contains reserved keys: {'model'} |
| What is the weather in Tokyo? | research-assistant | deepseek-chat | invoke | - | - | 0.63 | - | - | - | - | - | - | - |
| What is the weather in Tokyo? | research-assistant | deepseek-chat | stream | - | - | 0.66 | - | - | - | - | - | - | - |
| What is the weather in Tokyo? | research-assistant | deepseek-chat | stream | - | - | 0.49 | - | - | - | - | - | - | - |
| What is the weather in Tokyo? | research-assistant | deepseek-chat | stream | - | - | 0.49 | - | - | - | - | - | - | - |
| Test message | static-agent | deepseek-chat | stream | - | - | 0.85 | - | - | - | - | - | - | - |
| Add 2 and 3 | langgraph-supervisor-hierarchy-agent | deepseek-chat | stream | - | - | 12.75 | - | - | - | - | - | - | - |

## 4. Observations

TODO

## 5. Next Optimization Target

TODO
