import argparse
import shutil
import sys
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from rag.chunking import markdown_heading_chunk  # noqa: E402
from rag.document_cleaner import clean_markdown_text  # noqa: E402

DEFAULT_KNOWLEDGE_BASE_DIR = PROJECT_ROOT / "data" / "knowledge_base"
DEFAULT_VECTOR_STORE_DIR = PROJECT_ROOT / "data" / "vector_store" / "campus_policy"
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 120


def load_markdown_documents(knowledge_base_dir: Path | str) -> list[Document]:
    """Load all Markdown files below a knowledge base directory as Documents."""

    kb_dir = Path(knowledge_base_dir)
    if not kb_dir.exists():
        raise FileNotFoundError(f"Knowledge base directory does not exist: {kb_dir}")

    documents: list[Document] = []
    for md_path in sorted(kb_dir.rglob("*.md")):
        content = clean_markdown_text(md_path.read_text(encoding="utf-8"))
        documents.append(
            Document(
                page_content=content,
                metadata={
                    "source": md_path.name,
                    "path": str(md_path.resolve()),
                },
            )
        )

    if not documents:
        raise ValueError(f"No Markdown documents found under: {kb_dir}")

    return documents


def split_markdown_documents(
    documents: list[Document],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Document]:
    """Split cleaned Markdown documents by headings with enriched metadata."""
    chunks: list[Document] = []
    for document in documents:
        chunks.extend(
            markdown_heading_chunk(
                document,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
        )
    return chunks


def create_local_embeddings(model_name: str = DEFAULT_EMBEDDING_MODEL) -> Embeddings:
    """Create local HuggingFace embeddings without requiring OpenAI credentials."""

    try:
        from langchain_huggingface import HuggingFaceEmbeddings
    except ImportError as e:
        raise RuntimeError(
            "Missing local embedding dependencies. Install langchain-huggingface "
            "and sentence-transformers before building the campus knowledge base."
        ) from e

    return HuggingFaceEmbeddings(
        model_name=model_name,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


def build_campus_knowledge_base(
    knowledge_base_dir: Path | str = DEFAULT_KNOWLEDGE_BASE_DIR,
    vector_store_dir: Path | str = DEFAULT_VECTOR_STORE_DIR,
    embeddings: Embeddings | None = None,
    embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    delete_existing: bool = True,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> Chroma:
    """Build and persist the campus policy Chroma index."""

    kb_dir = Path(knowledge_base_dir)
    store_dir = Path(vector_store_dir)
    documents = load_markdown_documents(kb_dir)
    chunks = split_markdown_documents(
        documents,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    if delete_existing and store_dir.exists():
        shutil.rmtree(store_dir)
    store_dir.mkdir(parents=True, exist_ok=True)

    embedding_function = embeddings or create_local_embeddings(embedding_model)
    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embedding_function,
        persist_directory=str(store_dir),
    )
    return vector_store


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Campus AI Agent Markdown RAG index.")
    parser.add_argument(
        "--knowledge-base-dir",
        type=Path,
        default=DEFAULT_KNOWLEDGE_BASE_DIR,
        help="Directory containing Markdown knowledge base files.",
    )
    parser.add_argument(
        "--vector-store-dir",
        type=Path,
        default=DEFAULT_VECTOR_STORE_DIR,
        help="Directory where the Chroma vector store will be persisted.",
    )
    parser.add_argument("--chunk-size", type=int, default=DEFAULT_CHUNK_SIZE)
    parser.add_argument("--chunk-overlap", type=int, default=DEFAULT_CHUNK_OVERLAP)
    parser.add_argument(
        "--embedding-model",
        default=DEFAULT_EMBEDDING_MODEL,
        help="Local sentence-transformers model used for embeddings.",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Append to the existing vector store instead of rebuilding it.",
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    vector_store = build_campus_knowledge_base(
        knowledge_base_dir=args.knowledge_base_dir,
        vector_store_dir=args.vector_store_dir,
        embedding_model=args.embedding_model,
        delete_existing=not args.keep_existing,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    count = vector_store._collection.count()
    print(f"Campus knowledge base index built at: {args.vector_store_dir}")
    print(f"Indexed chunks: {count}")
    documents = load_markdown_documents(args.knowledge_base_dir)
    chunks = split_markdown_documents(
        documents,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    chunk_counts = Counter(str(chunk.metadata["source"]) for chunk in chunks)
    print("Chunks by source:")
    for source, source_count in sorted(chunk_counts.items()):
        print(f"- {source}: {source_count}")


if __name__ == "__main__":
    main()
