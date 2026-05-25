# Benchmark Run: before_rag_retriever_cache_same_questions

## 1. Run Metadata

- created_at: 2026-05-25T12:52:27.718849+00:00
- git commit hash: 8d083e0
- trace file: /tmp/before_rag_retriever_cache_trace.jsonl
- sample size: 5 valid trace records
- request sample size: 2
- child event count: 3
- skipped invalid JSON lines: 0
- model list: deepseek-chat
- agent list: research-assistant

## 2. Summary

- total_requests: 2
- average_total_latency_ms: 24804.17
- average_llm_time_ms: 7896.37
- average_tool_time_ms: 16876.32
- average_retrieval_time_ms: 16876.32
- average_prompt_tokens: 12616.50
- average_completion_tokens: 516.50
- average_total_tokens: 13133.00
- error_count: 0
- fallback_count: 0

## 3. Per-query Results

| query | agent_id | model_name | route | tool_calls | retrieved_docs | total_latency_ms | llm_time_ms | tool_time_ms | retrieval_time_ms | prompt_tokens | completion_tokens | total_tokens | error_message |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 考试作弊有什么后果？ | research-assistant | deepseek-chat | stream | query_campus_policy | exam_policy.md (exam_policy.md::chunk-0003), leave_policy.md (leave_policy.md::chunk-0003), exam_policy.md (exam_policy.md::chunk-0001), exam_policy.md (exam_policy.md::chunk-0002), scholarship_policy.md (scholarship_policy.md::chunk-0001) | 22952.16 | 7206.21 | 15714.98 | 15714.98 | 11620 | 464 | 12084 | - |
| 如果我因为生病缺考怎么办？ | research-assistant | deepseek-chat | stream | query_campus_policy | leave_policy.md (leave_policy.md::chunk-0002), leave_policy.md (leave_policy.md::chunk-0003), exam_policy.md (exam_policy.md::chunk-0002), exam_policy.md (exam_policy.md::chunk-0003), leave_policy.md (leave_policy.md::chunk-0001) | 26656.18 | 8586.53 | 18037.67 | 18037.67 | 13613 | 569 | 14182 | - |

## 4. Observations

TODO

## 5. Next Optimization Target

TODO
