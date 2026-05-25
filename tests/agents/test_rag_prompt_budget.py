from langchain_core.documents import Document

from agents import rag_assistant as rag_module
from agents import tools as campus_tools
from agents.tools import database_search_func
from core.token_budget import format_rag_context, select_context_docs
from core.tracing import TraceRecord, bind_trace_record, generate_trace_id
from prompts.rag_prompts import (
    RAG_NO_ANSWER_INSTRUCTION,
    RAG_POLICY_SYSTEM_PROMPT,
    RAG_SOURCE_CITATION_INSTRUCTION,
)


class FakeRetriever:
    def __init__(self, documents):
        self.documents = documents

    def invoke(self, query: str):
        return self.documents


def _documents(count: int) -> list[Document]:
    return [
        Document(
            page_content=f"## 规定 {index}\n" + ("请假办理需要提交证明材料。" * 100),
            metadata={
                "source": "leave_policy.md",
                "chunk_id": f"leave_policy.md::chunk-{index:04d}",
                "section": "请假流程",
                "heading_path": "学生请假制度 > 请假流程",
                "policy_type": "leave",
            },
        )
        for index in range(1, count + 1)
    ]


def test_budgeted_rag_context_retains_citations_within_default_limits():
    selected = select_context_docs(_documents(8))
    context = format_rag_context(selected)

    assert len(selected) <= 5
    assert len(context) <= 6000
    assert "Source: leave_policy.md" in context
    assert "Chunk: leave_policy.md::chunk-0001" in context


def test_database_search_applies_budget_and_records_context_metrics(monkeypatch):
    documents = _documents(8)
    records = []
    monkeypatch.setattr(campus_tools.settings, "RAG_TOP_K", 8)
    monkeypatch.setattr(campus_tools, "load_chroma_db", lambda: FakeRetriever(documents))
    monkeypatch.setattr(campus_tools, "write_trace_jsonl", records.append)

    with bind_trace_record(TraceRecord(trace_id=generate_trace_id(), route="invoke")):
        result = database_search_func("请假需要提交哪些材料？")

    trace = next(record for record in records if record.route == "Database_Search")
    assert trace.returned_doc_count == 8
    assert trace.context_docs_count <= 5
    assert trace.context_chars <= 6000
    assert trace.estimated_context_tokens > 0
    assert trace.dropped_context_docs_count >= 3
    assert "leave_policy.md::chunk-0001" in result


def test_no_answer_is_not_trimmed_by_context_budget(monkeypatch):
    monkeypatch.setattr(campus_tools, "load_chroma_db", lambda: FakeRetriever([]))

    result = database_search_func("知识库中没有的问题")

    assert "当前知识库中没有找到明确依据" in result
    assert "建议以学校官方通知或辅导员答复为准" in result
    assert "不得编造具体制度、电话、办公室、网址" in result


def test_rag_prompt_fragments_are_composed_into_agent_instructions():
    assert "只能基于数据库检索结果或用户已提供资料" in RAG_POLICY_SYSTEM_PROMPT
    assert "不得补充确定性制度结论" in RAG_NO_ANSWER_INSTRUCTION
    assert "source / chunk_id" in RAG_SOURCE_CITATION_INSTRUCTION
    assert RAG_POLICY_SYSTEM_PROMPT.strip() in rag_module.instructions
    assert RAG_NO_ANSWER_INSTRUCTION.strip() in rag_module.instructions
    assert RAG_SOURCE_CITATION_INSTRUCTION.strip() in rag_module.instructions
