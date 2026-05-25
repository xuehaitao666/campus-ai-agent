from pathlib import Path

import pytest
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

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
            }
        )

    recall = sum(item["correct_doc_recall"] for item in evaluations) / len(evaluations)

    # Offline deterministic baseline: build/split/persist/retrieve real Markdown sources.
    # Production multilingual embedding quality needs a separately enabled evaluation run.
    assert recall == 1.0, f"correct_doc_recall={recall:.2%}, evaluations={evaluations}"
