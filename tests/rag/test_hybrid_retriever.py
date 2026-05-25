from langchain_core.documents import Document

from rag import hybrid_retriever
from rag.hybrid_retriever import (
    bm25_search,
    build_bm25_index,
    hybrid_search,
    reciprocal_rank_fusion,
    tokenize_for_bm25,
)


def _document(source: str, chunk_id: str, content: str) -> Document:
    return Document(
        page_content=content,
        metadata={
            "source": source,
            "chunk_id": chunk_id,
            "policy_type": source.split("_", 1)[0],
            "section": "制度说明",
            "heading_path": "制度说明 > 办理要求",
        },
    )


def test_tokenize_for_bm25_extracts_chinese_policy_keywords():
    tokens = tokenize_for_bm25("宿舍晚归怎么处理？奖学金申请条件")

    assert "宿舍" in tokens
    assert "晚归" in tokens
    assert "奖学" in tokens
    assert "学金" in tokens


def test_bm25_search_retrieves_keyword_matched_policy_document():
    documents = [
        _document("leave_policy.md", "leave-1", "学生请假应当提交申请材料。"),
        _document("dormitory_policy.md", "dormitory-1", "宿舍晚归需要按规定登记。"),
        _document("exam_policy.md", "exam-1", "考试作弊将按纪律处理。"),
    ]

    results = bm25_search("宿舍晚归怎么处理？", build_bm25_index(documents), top_k=2)

    assert results[0].metadata["source"] == "dormitory_policy.md"


def test_rrf_deduplicates_chunks_and_promotes_documents_seen_by_both_retrievers():
    shared = _document("scholarship_policy.md", "scholarship-1", "奖学金评定条件。")
    vector_docs = [
        _document("leave_policy.md", "leave-1", "请假流程。"),
        shared,
    ]
    bm25_docs = [
        shared,
        _document("exam_policy.md", "exam-1", "考试纪律。"),
    ]

    results = reciprocal_rank_fusion(vector_docs, bm25_docs, top_k=3)

    assert [document.metadata["chunk_id"] for document in results].count("scholarship-1") == 1
    assert results[0].metadata["chunk_id"] == "scholarship-1"
    assert results[0].metadata["retrieval_source"] == "vector+bm25"
    assert results[0].metadata["vector_rank"] == 2
    assert results[0].metadata["bm25_rank"] == 1
    assert results[0].metadata["hybrid_score"] > 0
    assert results[0].metadata["policy_type"] == "scholarship"
    assert results[0].metadata["section"] == "制度说明"
    assert results[0].metadata["heading_path"] == "制度说明 > 办理要求"


def test_hybrid_search_invokes_vector_and_bm25_channels(monkeypatch):
    vector_document = _document("exam_policy.md", "exam-1", "考试作弊处理。")
    bm25_document = _document("exam_policy.md", "exam-1", "考试作弊处理。")

    class FakeVectorRetriever:
        queries = []

        def invoke(self, query: str):
            self.queries.append(query)
            return [vector_document]

    bm25_calls = []

    def fake_bm25_search(query, documents, top_k):
        bm25_calls.append((query, documents, top_k))
        return [bm25_document]

    retriever = FakeVectorRetriever()
    corpus = [bm25_document]
    monkeypatch.setattr(hybrid_retriever, "bm25_search", fake_bm25_search)

    results = hybrid_search(
        "考试作弊有什么后果？",
        retriever,
        corpus,
        top_k=3,
        vector_k=5,
        bm25_k=4,
    )

    assert retriever.queries == ["考试作弊有什么后果？"]
    assert bm25_calls == [("考试作弊有什么后果？", corpus, 4)]
    assert results[0].metadata["retrieval_source"] == "vector+bm25"
