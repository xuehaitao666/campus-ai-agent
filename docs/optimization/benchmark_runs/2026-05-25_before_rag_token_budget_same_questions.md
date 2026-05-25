# Benchmark Run: before_rag_token_budget_same_questions

## 1. Run Metadata

- created_at: 2026-05-25T15:02:08.002199+00:00
- git commit hash: c37f3ca
- trace file: /tmp/before_rag_token_budget_trace.jsonl
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
- average_total_latency_ms: 11274.15
- average_llm_time_ms: 7706.12
- average_tool_time_ms: 3533.18
- average_retrieval_time_ms: 66.99
- average_prompt_tokens: 10809.60
- average_completion_tokens: 498.60
- average_total_tokens: 11308.20
- error_count: 0
- fallback_count: 0

## 3. Per-query Results

| query | agent_id | model_name | route | tool_calls | retrieved_docs | total_latency_ms | llm_time_ms | tool_time_ms | retrieval_time_ms | prompt_tokens | completion_tokens | total_tokens | error_message |
| --- | --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 请假流程是什么？ | research-assistant | deepseek-chat | stream | query_campus_policy | leave_policy.md (leave_policy.md::chunk-0010), leave_policy.md (leave_policy.md::chunk-0005), exam_policy.md (exam_policy.md::chunk-0008), leave_policy.md (leave_policy.md::chunk-0001), student_handbook.md (student_handbook.md::chunk-0008) | 24323.23 | 6774.77 | 17518.37 | 187.43 | 6186 | 392 | 6578 | - |
| 挂科了还能申请奖学金吗？ | research-assistant | deepseek-chat | stream | query_campus_policy | scholarship_policy.md (scholarship_policy.md::chunk-0009), scholarship_policy.md (scholarship_policy.md::chunk-0005), scholarship_policy.md (scholarship_policy.md::chunk-0012), scholarship_policy.md (scholarship_policy.md::chunk-0010), scholarship_policy.md (scholarship_policy.md::chunk-0013) | 6978.20 | 6900.52 | 37.35 | 37.34 | 8389 | 420 | 8809 | - |
| 宿舍晚归会怎么处理？ | research-assistant | deepseek-chat | stream | query_campus_policy | dormitory_policy.md (dormitory_policy.md::chunk-0004), dormitory_policy.md (dormitory_policy.md::chunk-0012), dormitory_policy.md (dormitory_policy.md::chunk-0010), dormitory_policy.md (dormitory_policy.md::chunk-0009), dormitory_policy.md (dormitory_policy.md::chunk-0003) | 7786.88 | 7716.53 | 37.87 | 37.86 | 10678 | 501 | 11179 | - |
| 考试作弊有什么后果？ | research-assistant | deepseek-chat | stream | query_campus_policy | exam_policy.md (exam_policy.md::chunk-0010), exam_policy.md (exam_policy.md::chunk-0008), exam_policy.md (exam_policy.md::chunk-0003), exam_policy.md (exam_policy.md::chunk-0009), scholarship_policy.md (scholarship_policy.md::chunk-0006) | 8180.06 | 8108.42 | 35.85 | 35.84 | 13119 | 571 | 13690 | - |
| 如果我因为生病缺考怎么办？ | research-assistant | deepseek-chat | stream | query_campus_policy | exam_policy.md (exam_policy.md::chunk-0005), leave_policy.md (leave_policy.md::chunk-0009), exam_policy.md (exam_policy.md::chunk-0012), exam_policy.md (exam_policy.md::chunk-0011), leave_policy.md (leave_policy.md::chunk-0004) | 9102.38 | 9030.35 | 36.48 | 36.47 | 15676 | 609 | 16285 | - |

## 4. Observations

TODO

## 5. Next Optimization Target

TODO
