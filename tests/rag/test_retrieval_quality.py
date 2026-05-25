from pathlib import Path

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from rag.hybrid_retriever import hybrid_search
from scripts.build_campus_kb import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    build_campus_knowledge_base,
)

TOP_K = 3
GOLDEN_QUESTIONS = [
    ("请假流程是什么？", {"leave_policy.md"}),
    ("挂科还能申请奖学金吗？", {"scholarship_policy.md"}),
    ("宿舍晚归怎么处理？", {"dormitory_policy.md"}),
    ("考试作弊有什么后果？", {"exam_policy.md"}),
    ("生病缺考怎么办？", {"exam_policy.md", "leave_policy.md"}),
]
POLICY_TYPE_BY_SOURCE = {
    "leave_policy.md": "leave",
    "scholarship_policy.md": "scholarship",
    "dormitory_policy.md": "dormitory",
    "exam_policy.md": "exam",
}


class KeywordEmbeddings(Embeddings):
    """Offline embeddings for a deterministic source-recall baseline."""

    vocabulary = [
        "请假",
        "流程",
        "挂科",
        "奖学金",
        "宿舍",
        "晚归",
        "考试",
        "作弊",
        "生病",
        "缺考",
        "缓考",
    ]

    def _embed(self, text: str) -> list[float]:
        return [float(keyword in text) for keyword in self.vocabulary] + [1.0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


def retrieved_sources(documents: list[Document]) -> set[str]:
    return {str(document.metadata["source"]) for document in documents}


def correct_doc_recall(expected_sources: set[str], actual_sources: set[str]) -> bool:
    return bool(expected_sources & actual_sources)


def correct_policy_type_recall(expected_sources: set[str], documents: list[Document]) -> bool:
    expected_types = {POLICY_TYPE_BY_SOURCE[source] for source in expected_sources}
    retrieved_types = {str(document.metadata["policy_type"]) for document in documents}
    return bool(expected_types & retrieved_types)


@pytest.fixture
def campus_policy_retriever(tmp_path):
    vector_store = build_campus_knowledge_base(
        knowledge_base_dir=Path("data/knowledge_base"),
        vector_store_dir=tmp_path / "vector_store" / "campus_policy",
        embeddings=KeywordEmbeddings(),
        chunk_size=DEFAULT_CHUNK_SIZE,
        chunk_overlap=DEFAULT_CHUNK_OVERLAP,
    )
    return vector_store.as_retriever(search_kwargs={"k": TOP_K})


@pytest.fixture
def hybrid_policy_retrieval_components(tmp_path):
    vector_store = build_campus_knowledge_base(
        knowledge_base_dir=Path("data/knowledge_base"),
        vector_store_dir=tmp_path / "hybrid_vector_store" / "campus_policy",
        embeddings=KeywordEmbeddings(),
        chunk_size=DEFAULT_CHUNK_SIZE,
        chunk_overlap=DEFAULT_CHUNK_OVERLAP,
    )
    stored = vector_store.get(include=["documents", "metadatas"])
    documents = [
        Document(page_content=content, metadata=metadata)
        for content, metadata in zip(stored["documents"], stored["metadatas"], strict=False)
    ]
    return vector_store.as_retriever(search_kwargs={"k": 8}), documents


@pytest.mark.parametrize(
    ("question", "expected_sources"),
    GOLDEN_QUESTIONS,
    ids=["leave", "scholarship", "dormitory", "exam-cheating", "sick-exam-absence"],
)
def test_golden_question_retrieves_expected_policy_source(
    campus_policy_retriever,
    question,
    expected_sources,
):
    documents = campus_policy_retriever.invoke(question)
    actual_sources = retrieved_sources(documents)

    assert correct_doc_recall(expected_sources, actual_sources), (
        f"question={question!r}, expected_sources={expected_sources}, "
        f"retrieved_sources={actual_sources}"
    )
    assert correct_policy_type_recall(expected_sources, documents)
    assert all(document.metadata["section"] for document in documents)
    assert all(document.metadata["heading_path"] for document in documents)


def test_golden_question_correct_doc_recall_baseline(campus_policy_retriever):
    evaluations = []
    for question, expected_sources in GOLDEN_QUESTIONS:
        documents = campus_policy_retriever.invoke(question)
        actual_sources = retrieved_sources(documents)
        evaluations.append(
            {
                "question": question,
                "expected_sources": expected_sources,
                "retrieved_sources": actual_sources,
                "correct_doc_recall": correct_doc_recall(expected_sources, actual_sources),
                "correct_policy_type_recall": correct_policy_type_recall(
                    expected_sources, documents
                ),
            }
        )

    recall = sum(item["correct_doc_recall"] for item in evaluations) / len(evaluations)

    # Offline deterministic baseline: build/split/persist/retrieve real Markdown sources.
    # Production multilingual embedding quality needs a separately enabled evaluation run.
    assert recall == 1.0, f"correct_doc_recall={recall:.2%}, evaluations={evaluations}"
    assert all(item["correct_policy_type_recall"] for item in evaluations)


@pytest.mark.parametrize(
    ("question", "expected_sources"),
    GOLDEN_QUESTIONS[:4],
    ids=["hybrid-leave", "hybrid-scholarship", "hybrid-dormitory", "hybrid-exam-cheating"],
)
def test_hybrid_golden_question_retrieves_expected_policy_source(
    hybrid_policy_retrieval_components,
    question,
    expected_sources,
):
    retriever, bm25_documents = hybrid_policy_retrieval_components

    documents = hybrid_search(
        question,
        retriever,
        bm25_documents,
        top_k=TOP_K,
        vector_k=8,
        bm25_k=8,
    )

    assert correct_doc_recall(expected_sources, retrieved_sources(documents))
    assert correct_policy_type_recall(expected_sources, documents)
    assert all(document.metadata["retrieval_source"] for document in documents)
    assert all(document.metadata["hybrid_score"] > 0 for document in documents)
