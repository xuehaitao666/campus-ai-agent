from langchain_core.documents import Document
import pytest

from agents import tools as campus_tools
from core.tracing import TraceRecord, bind_trace_record, generate_trace_id
from rag import reranker as reranker_module


class FakeRetriever:
    def __init__(self, documents):
        self.documents = documents

    def invoke(self, query: str):
        return self.documents


class FailingRetriever:
    def invoke(self, query: str):
        raise RuntimeError("retriever temporarily unavailable")


def _policy_document(source: str, chunk_id: str, content: str, **metadata) -> Document:
    return Document(
        page_content=content,
        metadata={
            "source": source,
            "chunk_id": chunk_id,
            "section": metadata.pop("section", "制度规定"),
            "heading_path": metadata.pop("heading_path", "校园制度 > 制度规定"),
            "policy_type": metadata.pop("policy_type", "general"),
            "retrieval_source": metadata.pop("retrieval_source", "vector+bm25"),
            "hybrid_score": metadata.pop("hybrid_score", 0.02),
            **metadata,
        },
    )


def test_retriever_exception_records_controlled_failure_without_traceback_text(monkeypatch):
    monkeypatch.setattr(campus_tools, "load_chroma_db", lambda: FailingRetriever())
    monkeypatch.setattr(campus_tools, "write_trace_jsonl", lambda record: None)
    record = TraceRecord(trace_id=generate_trace_id(), route="invoke")

    with bind_trace_record(record):
        with pytest.raises(RuntimeError) as error:
            campus_tools.database_search_func("考试作弊有什么后果？")

    assert str(error.value) == "retriever temporarily unavailable"
    assert "Traceback" not in str(error.value)
    assert record.error_message == "retriever temporarily unavailable"
    # Current contract propagates retrieval failures; converting this to no-answer is future work.


def test_reranker_failure_falls_back_to_retrieval_order_and_preserves_metadata(monkeypatch):
    documents = [
        _policy_document(
            "exam_policy.md",
            "exam_policy.md::chunk-0001",
            "考试作弊将依据考试纪律处理。",
            policy_type="exam",
            section="作弊处理",
        ),
        _policy_document(
            "student_handbook.md",
            "student_handbook.md::chunk-0001",
            "考试纪律须遵守学生手册。",
            policy_type="handbook",
        ),
    ]
    monkeypatch.setattr(campus_tools.settings, "ENABLE_RAG_RERANKER", True)
    monkeypatch.setattr(campus_tools.settings, "RAG_RERANK_TOP_N", 2)
    monkeypatch.setattr(campus_tools.settings, "RAG_FINAL_TOP_K", 2)
    monkeypatch.setattr(campus_tools.settings, "RAG_RETRIEVAL_MODE", "vector")
    monkeypatch.setattr(campus_tools, "load_chroma_db", lambda: FakeRetriever(documents))
    monkeypatch.setattr(campus_tools, "write_trace_jsonl", lambda record: None)

    def fail_rerank(*args, **kwargs):
        raise RuntimeError("reranker unavailable")

    monkeypatch.setattr(reranker_module, "rerank_documents", fail_rerank)
    record = TraceRecord(trace_id=generate_trace_id(), route="invoke")

    with bind_trace_record(record):
        result = campus_tools.database_search_func("考试作弊有什么后果？")

    assert "exam_policy.md | exam_policy.md::chunk-0001" in result
    assert record.reranker_enabled is True
    assert record.rerank_error == "reranker unavailable"
    assert record.retrieved_docs[0]["source"] == "exam_policy.md"
    assert record.retrieved_docs[0]["chunk_id"] == "exam_policy.md::chunk-0001"
    assert record.retrieved_docs[0]["section"] == "作弊处理"


def test_low_relevance_no_answer_keeps_trace_shape_and_avoids_policy_fabrication(monkeypatch):
    documents = [
        _policy_document(
            "course_intro.md",
            "course_intro.md::chunk-0001",
            "大学英语课程重点训练听说读写能力。",
        )
    ]
    monkeypatch.setattr(campus_tools, "load_chroma_db", lambda: FakeRetriever(documents))
    monkeypatch.setattr(campus_tools, "write_trace_jsonl", lambda record: None)
    record = TraceRecord(trace_id=generate_trace_id(), route="invoke")

    with bind_trace_record(record):
        result = campus_tools.database_search_func("宿舍晚归如何处理？")

    assert "当前知识库中没有找到明确依据" in result
    assert "大学英语" not in result
    assert "宿舍晚归将被处分" not in result
    assert record.is_low_relevance is True
    assert record.no_answer_triggered is True
    assert record.retrieved_docs[0]["source"] == "course_intro.md"


def test_normal_retrieval_keeps_citation_and_structured_source_metadata(monkeypatch):
    documents = [
        _policy_document(
            "leave_policy.md",
            "leave_policy.md::chunk-0002",
            "学生请假应提交申请材料和相关证明。",
            policy_type="leave",
            section="请假流程",
            heading_path="请假管理 > 请假流程",
        )
    ]
    monkeypatch.setattr(campus_tools, "load_chroma_db", lambda: FakeRetriever(documents))
    monkeypatch.setattr(campus_tools, "write_trace_jsonl", lambda record: None)
    record = TraceRecord(trace_id=generate_trace_id(), route="invoke")

    with bind_trace_record(record):
        result = campus_tools.database_search_func("请假流程是什么？")

    assert "Source: leave_policy.md" in result
    assert "Chunk: leave_policy.md::chunk-0002" in result
    assert "Section: 请假流程" in result
    assert "### 来源" in result
    assert record.retrieved_docs[0]["source"] == "leave_policy.md"
    assert record.retrieved_docs[0]["chunk_id"] == "leave_policy.md::chunk-0002"
    assert record.retrieved_docs[0]["section"] == "请假流程"
