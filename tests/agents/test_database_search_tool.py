import pytest
from langchain_core.documents import Document

from agents import tools as campus_tools
from agents.tools import database_search, database_search_func, format_contexts
from core.tracing import TraceRecord, bind_trace_record, generate_trace_id


class FakeRetriever:
    def __init__(self, documents):
        self.documents = documents
        self.queries = []

    def invoke(self, query: str):
        self.queries.append(query)
        return self.documents


class FailingRetriever:
    def invoke(self, query: str):
        raise RuntimeError(f"retrieval failed: {query}")


def test_database_search_tool_is_registered_with_expected_name():
    assert database_search.name == "Database_Search"


def test_database_search_returns_retrieved_context_with_metadata(monkeypatch):
    documents = [
        Document(
            page_content="学生请假应当提交请假申请和证明材料。",
            metadata={
                "source": "leave_policy.md",
                "path": "/kb/leave_policy.md",
                "chunk_id": "leave_policy.md::chunk-0001",
            },
        )
    ]
    fake_retriever = FakeRetriever(documents)
    monkeypatch.setattr(campus_tools, "load_chroma_db", lambda: fake_retriever)

    result = database_search_func("请假需要什么材料？")

    assert fake_retriever.queries == ["请假需要什么材料？"]
    assert "学生请假应当提交请假申请和证明材料。" in result
    assert "Source: leave_policy.md" in result
    assert "Path: /kb/leave_policy.md" in result
    assert "Chunk: leave_policy.md::chunk-0001" in result
    assert "### 来源" in result
    assert "- leave_policy.md | leave_policy.md::chunk-0001 | /kb/leave_policy.md" in result


def test_database_search_preserves_enriched_context_metadata(monkeypatch):
    documents = [
        Document(
            page_content="考试作弊将按照考试纪律处理。",
            metadata={
                "source": "exam_policy.md",
                "chunk_id": "exam_policy.md::chunk-0001",
                "section": "作弊处理",
                "heading_path": "考试纪律 > 作弊处理",
                "policy_type": "exam",
            },
        )
    ]
    monkeypatch.setattr(campus_tools, "load_chroma_db", lambda: FakeRetriever(documents))

    result = database_search_func("考试作弊有什么后果？")

    assert "Section: 作弊处理" in result
    assert "Heading Path: 考试纪律 > 作弊处理" in result
    assert "Policy Type: exam" in result


def test_database_search_records_structured_retrieved_docs_for_response_metadata(monkeypatch):
    documents = [
        Document(
            page_content="考试作弊将按照考试纪律处理。",
            metadata={
                "source": "exam_policy.md",
                "chunk_id": "exam_policy.md::chunk-0001",
                "section": "作弊处理",
                "heading_path": "考试纪律 > 作弊处理",
                "policy_type": "exam",
                "retrieval_source": "vector+bm25",
                "hybrid_score": 0.03,
            },
        )
    ]
    monkeypatch.setattr(campus_tools, "load_chroma_db", lambda: FakeRetriever(documents))
    monkeypatch.setattr(campus_tools, "write_trace_jsonl", lambda record: None)
    record = TraceRecord(trace_id=generate_trace_id(), route="invoke")

    with bind_trace_record(record):
        database_search_func("考试作弊有什么后果？")

    retrieved = record.retrieved_docs[0]
    assert retrieved["source"] == "exam_policy.md"
    assert retrieved["chunk_id"] == "exam_policy.md::chunk-0001"
    assert retrieved["section"] == "作弊处理"
    assert retrieved["retrieval_source"] == "vector+bm25"
    assert retrieved["hybrid_score"] == 0.03


def test_database_search_tool_invokes_search_without_real_vector_store(monkeypatch):
    documents = [
        Document(
            page_content="考试作弊将按照考试纪律相关规定处理。",
            metadata={"source": "exam_policy.md", "chunk_id": "exam-policy-1"},
        )
    ]
    monkeypatch.setattr(campus_tools, "load_chroma_db", lambda: FakeRetriever(documents))

    result = database_search.invoke({"query": "考试作弊有什么后果？"})

    assert "考试作弊将按照考试纪律相关规定处理。" in result
    assert "Source: exam_policy.md" in result
    assert "Chunk: exam-policy-1" in result


def test_database_search_empty_results_returns_no_answer_without_fabricating_details(monkeypatch):
    monkeypatch.setattr(campus_tools, "load_chroma_db", lambda: FakeRetriever([]))

    result = database_search_func("知识库里不存在的问题")

    assert "当前知识库中没有找到明确依据" in result
    assert "建议以学校官方通知或辅导员答复为准" in result
    assert "不得编造具体制度、电话、办公室、网址" in result
    assert "http://" not in result
    assert "https://" not in result


def test_database_search_low_relevance_results_return_no_answer(monkeypatch):
    documents = [
        Document(
            page_content="大学英语选课办理流程，本课程强调听说读写训练。",
            metadata={"source": "course_intro.md", "chunk_id": "english-1"},
        )
    ]
    monkeypatch.setattr(campus_tools, "load_chroma_db", lambda: FakeRetriever(documents))

    result = database_search_func("宿舍晚归办理流程是什么？")

    assert "当前知识库中没有找到明确依据" in result
    assert "当前检索结果与问题相关性不足" in result
    assert "大学英语" not in result


def test_database_search_uses_hybrid_retrieval_when_enabled(monkeypatch):
    documents = [
        Document(
            page_content="考试作弊将按照考试纪律相关规定处理。",
            metadata={
                "source": "exam_policy.md",
                "chunk_id": "exam-policy-1",
                "retrieval_source": "vector+bm25",
                "hybrid_score": 0.03,
            },
        )
    ]
    fake_retriever = FakeRetriever([])
    hybrid_calls = []
    monkeypatch.setattr(campus_tools.settings, "RAG_RETRIEVAL_MODE", "hybrid")
    monkeypatch.setattr(campus_tools, "load_chroma_db", lambda: fake_retriever)
    monkeypatch.setattr(campus_tools, "load_bm25_index", lambda: "cached-index")

    def fake_hybrid_search(**kwargs):
        hybrid_calls.append(kwargs)
        return documents

    monkeypatch.setattr(campus_tools, "hybrid_search", fake_hybrid_search)

    result = database_search_func("考试作弊有什么后果？")

    assert hybrid_calls[0]["vector_retriever"] is fake_retriever
    assert hybrid_calls[0]["bm25_documents"] == "cached-index"
    assert "exam_policy.md" in result
    assert "exam-policy-1" in result


def test_database_search_records_reranker_metrics_when_enabled(monkeypatch):
    documents = [
        Document(
            page_content="普通制度说明。",
            metadata={"source": "handbook.md", "chunk_id": "handbook-1"},
        ),
        Document(
            page_content="考试作弊将依据考试纪律处理。",
            metadata={
                "source": "exam_policy.md",
                "chunk_id": "exam-1",
                "section": "作弊处理",
                "heading_path": "考试纪律 > 作弊处理",
                "policy_type": "exam",
            },
        ),
    ]
    monkeypatch.setattr(campus_tools.settings, "ENABLE_RAG_RERANKER", True)
    monkeypatch.setattr(campus_tools.settings, "RAG_RERANK_TOP_N", 2)
    monkeypatch.setattr(campus_tools.settings, "RAG_FINAL_TOP_K", 1)
    monkeypatch.setattr(campus_tools, "load_chroma_db", lambda: FakeRetriever(documents))
    records = []
    monkeypatch.setattr(campus_tools, "write_trace_jsonl", records.append)
    request_record = TraceRecord(trace_id=generate_trace_id(), route="invoke")

    with bind_trace_record(request_record):
        result = database_search_func("考试作弊有什么后果？")

    trace = next(record for record in records if record.route == "Database_Search")
    assert "exam_policy.md" in result
    assert trace.reranker_enabled is True
    assert trace.rerank_input_count == 2
    assert trace.rerank_output_count == 1
    assert trace.rerank_latency_ms is not None
    assert trace.rerank_error is None
    assert trace.reranked_source_list == ["exam_policy.md"]
    assert trace.reranked_chunk_id_list == ["exam-1"]
    assert trace.retrieved_docs[0]["rerank_score"] > 0
    assert request_record.reranker_enabled is True


def test_database_search_propagates_retriever_errors(monkeypatch):
    monkeypatch.setattr(campus_tools, "load_chroma_db", lambda: FailingRetriever())

    with pytest.raises(RuntimeError, match="retrieval failed"):
        database_search_func("触发检索异常")


def test_format_contexts_preserves_stable_document_and_metadata_format():
    documents = [
        Document(
            page_content="第一段制度内容。",
            metadata={
                "source": "student_handbook.md",
                "path": "/kb/student_handbook.md",
                "chunk_id": "student_handbook.md::chunk-0001",
            },
        ),
        Document(
            page_content="第二段制度内容。",
            metadata={
                "source": "exam_policy.md",
                "path": "/kb/exam_policy.md",
                "chunk_id": "exam_policy.md::chunk-0002",
            },
        ),
    ]

    result = format_contexts(documents)

    assert result == (
        "--- Source: student_handbook.md | Path: /kb/student_handbook.md | "
        "Chunk: student_handbook.md::chunk-0001 ---\n"
        "第一段制度内容。\n\n"
        "--- Source: exam_policy.md | Path: /kb/exam_policy.md | "
        "Chunk: exam_policy.md::chunk-0002 ---\n"
        "第二段制度内容。"
    )
