# Benchmark Run: after_rag_token_budget_same_questions

## 1. Run Metadata

- created_at: 2026-05-25T15:09:03.812585+00:00
- git commit hash: 7c9cc28
- trace file: logs/agent_trace.jsonl
- selection_mode: request-last
- requested_request_count: 5
- actual_request_count: 5
- sample size: 5 valid trace records
- request sample size: 5
- child event count: 0
- skipped child event count: 4
- skipped invalid JSON lines: 0
- model list: deepseek-chat
- agent list: research-assistant

## 2. Summary

- total_requests: 5
- average_total_latency_ms: 9681.98
- average_llm_time_ms: 6015.14
- average_tool_time_ms: 3628.41
- average_retrieval_time_ms: 65.61
- average_prompt_tokens: 10680.60
- average_completion_tokens: 432.60
- average_total_tokens: 11113.20
- error_count: 0
- fallback_count: 0

## 3. Per-query Results

| query | agent_id | model_name | route | tool_calls | retrieved_docs | total_latency_ms | llm_time_ms | tool_time_ms | retrieval_time_ms | prompt_tokens | completion_tokens | total_tokens | error_message |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 请假流程是什么？ | research-assistant | deepseek-chat | stream | query_campus_policy | leave_policy.md (leave_policy.md::chunk-0010), leave_policy.md (leave_policy.md::chunk-0005), exam_policy.md (exam_policy.md::chunk-0008), leave_policy.md (leave_policy.md::chunk-0001), student_handbook.md (student_handbook.md::chunk-0008) | 23782.24 | 5766.02 | 17986.63 | 172.66 | 6184 | 360 | 6544 | - |
| 挂科了还能申请奖学金吗？ | research-assistant | deepseek-chat | stream | query_campus_policy | scholarship_policy.md (scholarship_policy.md::chunk-0009), scholarship_policy.md (scholarship_policy.md::chunk-0010), scholarship_policy.md (scholarship_policy.md::chunk-0005), scholarship_policy.md (scholarship_policy.md::chunk-0012), scholarship_policy.md (scholarship_policy.md::chunk-0013) | 6183.56 | 6093.57 | 53.47 | 53.46 | 8351 | 389 | 8740 | - |
| 宿舍晚归会怎么处理？ | research-assistant | deepseek-chat | stream | query_campus_policy | dormitory_policy.md (dormitory_policy.md::chunk-0004), dormitory_policy.md (dormitory_policy.md::chunk-0012), dormitory_policy.md (dormitory_policy.md::chunk-0010), dormitory_policy.md (dormitory_policy.md::chunk-0009), dormitory_policy.md (dormitory_policy.md::chunk-0003) | 5769.30 | 5699.00 | 32.85 | 32.84 | 10605 | 472 | 11077 | - |
| 考试作弊有什么后果？ | research-assistant | deepseek-chat | stream | query_campus_policy | exam_policy.md (exam_policy.md::chunk-0010), exam_policy.md (exam_policy.md::chunk-0008), exam_policy.md (exam_policy.md::chunk-0003), exam_policy.md (exam_policy.md::chunk-0009), scholarship_policy.md (scholarship_policy.md::chunk-0006) | 5523.10 | 5442.42 | 32.89 | 32.89 | 12987 | 429 | 13416 | - |
| 如果我因为生病缺考怎么办？ | research-assistant | deepseek-chat | stream | query_campus_policy | exam_policy.md (exam_policy.md::chunk-0011), leave_policy.md (leave_policy.md::chunk-0009), leave_policy.md (leave_policy.md::chunk-0004), leave_policy.md (leave_policy.md::chunk-0012), exam_policy.md (exam_policy.md::chunk-0006) | 7151.71 | 7074.70 | 36.22 | 36.21 | 15276 | 513 | 15789 | - |

## 4. Observations

TODO

## 5. Next Optimization Target

TODO
