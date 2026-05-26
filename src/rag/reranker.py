from __future__ import annotations

from typing import Any

from langchain_core.documents import Document

from rag.hybrid_retriever import tokenize_for_bm25

POLICY_QUERY_TERMS: dict[str, set[str]] = {
    "leave": {"请假", "病假", "事假", "缺考", "缓考"},
    "exam": {"考试", "作弊", "缺考", "补考", "缓考"},
    "scholarship": {"奖学金", "挂科", "评奖", "综测"},
    "dormitory": {"宿舍", "晚归", "寝室", "电器"},
    "handbook": {"学籍", "处分", "违纪", "学生手册"},
}


def _token_overlap(query_tokens: set[str], value: str) -> float:
    if not query_tokens:
        return 0.0
    value_tokens = set(tokenize_for_bm25(value))
    return len(query_tokens & value_tokens) / len(query_tokens)


def _policy_match(query: str, policy_type: str) -> float:
    terms = POLICY_QUERY_TERMS.get(policy_type, set())
    return 1.0 if any(term in query for term in terms) else 0.0


def rerank_documents(query: str, docs: list[Document], top_k: int) -> list[Document]:
    """Rerank candidate chunks using lightweight lexical and metadata signals."""
    if top_k <= 0:
        return []

    query_tokens = set(tokenize_for_bm25(query))
    ranked: list[tuple[float, int, Document]] = []
    for index, document in enumerate(docs):
        metadata = dict(document.metadata)
        heading_text = " ".join(
            str(metadata.get(field, "")) for field in ("section", "heading_path")
        )
        content_score = _token_overlap(query_tokens, document.page_content)
        heading_score = _token_overlap(query_tokens, heading_text)
        policy_score = _policy_match(query, str(metadata.get("policy_type", "")))
        hybrid_score = float(metadata.get("hybrid_score") or 0.0)
        score = content_score + 1.5 * heading_score + 1.25 * policy_score + hybrid_score
        metadata["rerank_score"] = round(score, 8)
        ranked.append(
            (
                score,
                index,
                Document(page_content=document.page_content, metadata=metadata),
            )
        )

    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [document for _, _, document in ranked[:top_k]]


def maybe_rerank_documents(query: str, docs: list[Document], settings: Any) -> list[Document]:
    """Apply optional reranking, falling back to the existing ranking on failure."""
    top_k = int(getattr(settings, "RAG_FINAL_TOP_K", len(docs)))
    if not getattr(settings, "ENABLE_RAG_RERANKER", False):
        return list(docs)[:top_k]

    candidate_limit = int(getattr(settings, "RAG_RERANK_TOP_N", len(docs)))
    candidates = list(docs)[:candidate_limit]
    try:
        return rerank_documents(query, candidates, top_k=top_k)
    except Exception as exc:
        fallback: list[Document] = []
        for document in candidates[:top_k]:
            metadata = dict(document.metadata)
            metadata["rerank_error"] = str(exc)
            fallback.append(Document(page_content=document.page_content, metadata=metadata))
        return fallback
