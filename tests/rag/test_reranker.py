from types import SimpleNamespace

from langchain_core.documents import Document

from rag import reranker
from rag.reranker import maybe_rerank_documents, rerank_documents


def _doc(source: str, chunk_id: str, content: str, **metadata) -> Document:
    return Document(
        page_content=content,
        metadata={
            "source": source,
            "chunk_id": chunk_id,
            "section": metadata.pop("section", "制度说明"),
            "heading_path": metadata.pop("heading_path", "制度说明 > 规则"),
            "policy_type": metadata.pop("policy_type", "general"),
            "retrieval_source": metadata.pop("retrieval_source", "vector+bm25"),
            "hybrid_score": metadata.pop("hybrid_score", 0.02),
            **metadata,
        },
    )


def _config(enabled: bool, final_top_k: int = 2, rerank_top_n: int = 3):
    return SimpleNamespace(
        ENABLE_RAG_RERANKER=enabled,
        RAG_FINAL_TOP_K=final_top_k,
        RAG_RERANK_TOP_N=rerank_top_n,
    )


def test_disabled_reranker_returns_original_order():
    documents = [
        _doc("leave_policy.md", "leave-1", "请假流程。"),
        _doc("exam_policy.md", "exam-1", "考试作弊处理。"),
    ]

    results = maybe_rerank_documents("考试作弊有什么后果？", documents, _config(False))

    assert [document.metadata["chunk_id"] for document in results] == ["leave-1", "exam-1"]
    assert "rerank_score" not in results[0].metadata


def test_reranker_orders_policy_match_and_retains_metadata():
    documents = [
        _doc("leave_policy.md", "leave-1", "学生申请材料说明。", policy_type="leave"),
        _doc(
            "exam_policy.md",
            "exam-1",
            "考试作弊将依据纪律处理。",
            policy_type="exam",
            section="考试作弊处理",
            heading_path="考试纪律 > 考试作弊处理",
        ),
    ]

    results = rerank_documents("考试作弊有什么后果？", documents, top_k=1)

    assert results[0].metadata["chunk_id"] == "exam-1"
    assert results[0].metadata["rerank_score"] > 0
    assert results[0].metadata["source"] == "exam_policy.md"
    assert results[0].metadata["section"] == "考试作弊处理"
    assert results[0].metadata["heading_path"] == "考试纪律 > 考试作弊处理"
    assert results[0].metadata["policy_type"] == "exam"
    assert results[0].metadata["retrieval_source"] == "vector+bm25"
    assert results[0].metadata["hybrid_score"] == 0.02


def test_heading_match_promotes_document_under_limited_budget():
    documents = [
        _doc("generic.md", "generic-1", "晚归处理说明。", policy_type="general"),
        _doc(
            "dormitory_policy.md",
            "dormitory-1",
            "违反住宿管理规定的行为按制度办理。",
            policy_type="dormitory",
            section="晚归处理",
            heading_path="宿舍管理 > 晚归处理",
        ),
    ]

    results = rerank_documents("宿舍晚归怎么处理？", documents, top_k=2)

    assert results[0].metadata["chunk_id"] == "dormitory-1"


def test_reranker_top_k_limits_results():
    documents = [
        _doc("exam_policy.md", f"exam-{index}", "考试作弊处理。", policy_type="exam")
        for index in range(3)
    ]

    assert len(rerank_documents("考试作弊", documents, top_k=2)) == 2


def test_reranker_failure_falls_back_to_original_ranking(monkeypatch):
    documents = [
        _doc("leave_policy.md", "leave-1", "请假流程。"),
        _doc("exam_policy.md", "exam-1", "考试作弊处理。"),
    ]

    def fail_rerank(*args, **kwargs):
        raise RuntimeError("reranker unavailable")

    monkeypatch.setattr(reranker, "rerank_documents", fail_rerank)

    results = maybe_rerank_documents("考试作弊", documents, _config(True))

    assert [document.metadata["chunk_id"] for document in results] == ["leave-1", "exam-1"]
    assert results[0].metadata["rerank_error"] == "reranker unavailable"
