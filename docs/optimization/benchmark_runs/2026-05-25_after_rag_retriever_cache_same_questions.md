# Benchmark Run: after_rag_retriever_cache_same_questions

## 1. Run Metadata

- created_at: 2026-05-25T12:54:24.440587+00:00
- git commit hash: 8d083e0
- trace file: logs/agent_trace.jsonl
- sample size: 5 valid trace records
- request sample size: 3
- child event count: 2
- skipped invalid JSON lines: 0
- model list: deepseek-chat
- agent list: research-assistant

## 2. Summary

- total_requests: 3
- average_total_latency_ms: 7174.04
- average_llm_time_ms: 7097.74
- average_tool_time_ms: 40.81
- average_retrieval_time_ms: 40.80
- average_prompt_tokens: 11836.67
- average_completion_tokens: 497.67
- average_total_tokens: 12334.33
- error_count: 0
- fallback_count: 0

## 3. Per-query Results

| query | agent_id | model_name | route | tool_calls | retrieved_docs | total_latency_ms | llm_time_ms | tool_time_ms | retrieval_time_ms | prompt_tokens | completion_tokens | total_tokens | error_message |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 宿舍晚归会怎么处理？ | research-assistant | deepseek-chat | stream | query_campus_policy | dormitory_policy.md (dormitory_policy.md::chunk-0002), dormitory_policy.md (dormitory_policy.md::chunk-0001), dormitory_policy.md (dormitory_policy.md::chunk-0003), leave_policy.md (leave_policy.md::chunk-0003), student_handbook.md (student_handbook.md::chunk-0001) | 6267.75 | 6187.00 | 45.99 | 45.98 | 9871 | 444 | 10315 | - |
| 考试作弊有什么后果？ | research-assistant | deepseek-chat | stream | query_campus_policy | exam_policy.md (exam_policy.md::chunk-0003), leave_policy.md (leave_policy.md::chunk-0003), exam_policy.md (exam_policy.md::chunk-0001), exam_policy.md (exam_policy.md::chunk-0002), scholarship_policy.md (scholarship_policy.md::chunk-0001) | 6725.16 | 6653.69 | 36.60 | 36.57 | 11821 | 467 | 12288 | - |
| 如果我因为生病缺考怎么办？ | research-assistant | deepseek-chat | stream | query_campus_policy | leave_policy.md (leave_policy.md::chunk-0003), leave_policy.md (leave_policy.md::chunk-0002), exam_policy.md (exam_policy.md::chunk-0002), exam_policy.md (exam_policy.md::chunk-0003), leave_policy.md (leave_policy.md::chunk-0001) | 8529.20 | 8452.54 | 39.85 | 39.85 | 13818 | 582 | 14400 | - |

## 4. Observations

TODO

## 5. Next Optimization Target

TODO
