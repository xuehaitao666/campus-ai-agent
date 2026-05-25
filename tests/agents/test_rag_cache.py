from functools import lru_cache

import pytest
from langchain_core.documents import Document

from agents import tools as campus_tools
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


@pytest.fixture(autouse=True)
def clear_cached_resources():
    campus_tools.clear_rag_cache()
    yield
    campus_tools.clear_rag_cache()


def _install_fake_vector_store(monkeypatch, retriever):
    calls = {"embeddings": 0, "chroma": 0, "retriever": 0}

    @lru_cache(maxsize=1)
    def fake_embeddings():
        calls["embeddings"] += 1
        return object()

    class FakeChroma:
        def __init__(self, **kwargs):
            calls["chroma"] += 1
            assert kwargs["embedding_function"] is fake_embeddings()

        def as_retriever(self, search_kwargs):
            calls["retriever"] += 1
            assert search_kwargs == {"k": 5}
            return retriever

    monkeypatch.setattr(campus_tools, "create_campus_policy_embeddings", fake_embeddings)
    monkeypatch.setattr(campus_tools, "Chroma", FakeChroma)
    return calls


def test_rag_tools_cache_initialization_but_retrieve_for_each_query(monkeypatch):
    fake_retriever = FakeRetriever(
        [
            Document(
                page_content="请假制度内容。",
                metadata={"source": "leave_policy.md", "chunk_id": "leave-1"},
            )
        ]
    )
    calls = _install_fake_vector_store(monkeypatch, fake_retriever)

    campus_tools.database_search_func("请假流程是什么？")
    campus_tools.database_search_func("请假需要哪些材料？")
    campus_tools.query_campus_policy_func("请假流程是什么？")

    assert calls == {"embeddings": 1, "chroma": 1, "retriever": 1}
    assert fake_retriever.queries == [
        "请假流程是什么？",
        "请假需要哪些材料？",
        "请假流程是什么？",
    ]


def test_clear_rag_cache_forces_resource_reinitialization(monkeypatch):
    fake_retriever = FakeRetriever([])
    calls = _install_fake_vector_store(monkeypatch, fake_retriever)

    campus_tools.database_search_func("首次查询")
    campus_tools.clear_rag_cache()
    campus_tools.database_search_func("知识库更新后的查询")

    assert calls == {"embeddings": 2, "chroma": 2, "retriever": 2}
    assert fake_retriever.queries == ["首次查询", "知识库更新后的查询"]


def test_database_search_trace_records_retrieval_metadata_and_empty_result(monkeypatch):
    retriever = FakeRetriever(
        [
            Document(
                page_content="奖学金制度内容。",
                metadata={
                    "source": "scholarship_policy.md",
                    "path": "/kb/scholarship_policy.md",
                    "chunk_id": "scholarship-1",
                },
            )
        ]
    )
    _install_fake_vector_store(monkeypatch, retriever)
    records = []
    monkeypatch.setattr(campus_tools, "write_trace_jsonl", records.append)
    request_record = TraceRecord(trace_id=generate_trace_id(), query="奖学金条件", route="invoke")

    with bind_trace_record(request_record):
        campus_tools.database_search_func("奖学金条件")

    query_record = next(record for record in records if record.route == "Database_Search")
    assert query_record.rag_load_time_ms is not None
    assert query_record.retrieval_time_ms is not None
    assert query_record.returned_doc_count == 1
    assert query_record.source_list == ["scholarship_policy.md"]
    assert query_record.chunk_id_list == ["scholarship-1"]
    assert query_record.is_empty_result is False
    assert request_record.rag_load_time_ms is not None
    assert request_record.retrieved_docs[0]["source"] == "scholarship_policy.md"

    retriever.documents = []
    records.clear()
    with bind_trace_record(TraceRecord(trace_id=generate_trace_id(), route="invoke")):
        assert campus_tools.database_search_func("无匹配内容") == ""

    empty_record = next(record for record in records if record.route == "Database_Search")
    assert empty_record.returned_doc_count == 0
    assert empty_record.is_empty_result is True
    assert empty_record.source_list == []
    assert empty_record.chunk_id_list == []


def test_database_search_keeps_retriever_errors_visible_and_traced(monkeypatch):
    _install_fake_vector_store(monkeypatch, FailingRetriever())
    records = []
    monkeypatch.setattr(campus_tools, "write_trace_jsonl", records.append)

    with bind_trace_record(TraceRecord(trace_id=generate_trace_id(), route="invoke")):
        with pytest.raises(RuntimeError, match="retrieval failed"):
            campus_tools.database_search_func("触发检索异常")

    query_record = next(record for record in records if record.route == "Database_Search")
    assert "retrieval failed" in query_record.error_message
    assert query_record.returned_doc_count == 0
    assert query_record.is_empty_result is True
