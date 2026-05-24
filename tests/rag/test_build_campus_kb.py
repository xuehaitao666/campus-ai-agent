import sys
import types
from pathlib import Path

from langchain_core.embeddings import Embeddings

from scripts.build_campus_kb import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    build_campus_knowledge_base,
    create_local_embeddings,
    load_markdown_documents,
    split_markdown_documents,
)


class FakeEmbeddings(Embeddings):
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(len(text) % 10), 1.0, 0.0] for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return [float(len(text) % 10), 1.0, 0.0]


def test_load_markdown_documents_recursively_with_source_metadata(tmp_path):
    kb_dir = tmp_path / "knowledge_base"
    nested_dir = kb_dir / "policies"
    nested_dir.mkdir(parents=True)
    (kb_dir / "leave_policy.md").write_text("# 学生请假制度\n\n请假流程。", encoding="utf-8")
    (nested_dir / "exam_policy.md").write_text("# 考试纪律\n\n考试规则。", encoding="utf-8")
    (nested_dir / "ignored.txt").write_text("ignore me", encoding="utf-8")

    documents = load_markdown_documents(kb_dir)

    assert len(documents) == 2
    assert {doc.metadata["source"] for doc in documents} == {
        "leave_policy.md",
        "exam_policy.md",
    }
    assert all(Path(doc.metadata["path"]).is_absolute() for doc in documents)


def test_split_markdown_documents_adds_chunk_metadata():
    documents = load_markdown_documents(Path("data/knowledge_base"))

    chunks = split_markdown_documents(
        documents,
        chunk_size=DEFAULT_CHUNK_SIZE,
        chunk_overlap=DEFAULT_CHUNK_OVERLAP,
    )

    assert chunks
    assert all("source" in chunk.metadata for chunk in chunks)
    assert all("path" in chunk.metadata for chunk in chunks)
    assert all("chunk_id" in chunk.metadata for chunk in chunks)
    assert all(chunk.metadata["chunk_id"].startswith(chunk.metadata["source"]) for chunk in chunks)


def test_create_local_embeddings_does_not_require_openai_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    class FakeHuggingFaceEmbeddings(Embeddings):
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            return [[1.0, 0.0] for _ in texts]

        def embed_query(self, text: str) -> list[float]:
            return [1.0, 0.0]

    fake_module = types.SimpleNamespace(HuggingFaceEmbeddings=FakeHuggingFaceEmbeddings)
    monkeypatch.setitem(sys.modules, "langchain_huggingface", fake_module)

    embeddings = create_local_embeddings()

    assert isinstance(embeddings, Embeddings)
    assert embeddings.kwargs["model_name"] == "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def test_build_campus_knowledge_base_persists_chroma_index(tmp_path):
    kb_dir = tmp_path / "knowledge_base"
    vector_store_dir = tmp_path / "vector_store" / "campus_policy"
    kb_dir.mkdir()
    (kb_dir / "leave_policy.md").write_text(
        "# 学生请假制度\n\n## 请假流程\n\n学生需要提交申请并等待辅导员审批。",
        encoding="utf-8",
    )

    vector_store = build_campus_knowledge_base(
        knowledge_base_dir=kb_dir,
        vector_store_dir=vector_store_dir,
        embeddings=FakeEmbeddings(),
        chunk_size=80,
        chunk_overlap=10,
    )

    assert vector_store_dir.exists()
    assert vector_store._collection.count() > 0
    results = vector_store.similarity_search("请假流程", k=1)
    assert results
    assert results[0].metadata["source"] == "leave_policy.md"
    assert "chunk_id" in results[0].metadata
