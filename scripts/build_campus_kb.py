import argparse
import shutil
from pathlib import Path

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KNOWLEDGE_BASE_DIR = PROJECT_ROOT / "data" / "knowledge_base"
DEFAULT_VECTOR_STORE_DIR = PROJECT_ROOT / "data" / "vector_store" / "campus_policy"
DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 120


def load_markdown_documents(knowledge_base_dir: Path | str) -> list[Document]:
    """Load all Markdown files below a knowledge base directory as Documents."""

    kb_dir = Path(knowledge_base_dir)
    if not kb_dir.exists():
        raise FileNotFoundError(f"Knowledge base directory does not exist: {kb_dir}")

    documents: list[Document] = []
    for md_path in sorted(kb_dir.rglob("*.md")):
        content = md_path.read_text(encoding="utf-8")
        documents.append(
            Document(
                page_content=content,
                metadata={
                    "source": md_path.name,
                    "full_path": str(md_path.resolve()),
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
    """Split Markdown Documents and attach stable chunk metadata."""

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n## ", "\n### ", "\n\n", "\n", "。", "，", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    source_counts: dict[str, int] = {}

    for chunk in chunks:
        source = str(chunk.metadata.get("source", "unknown"))
        source_counts[source] = source_counts.get(source, 0) + 1
        chunk.metadata["chunk_id"] = f"{source}::chunk-{source_counts[source]:04d}"

    return chunks


def build_campus_knowledge_base(
    knowledge_base_dir: Path | str = DEFAULT_KNOWLEDGE_BASE_DIR,
    vector_store_dir: Path | str = DEFAULT_VECTOR_STORE_DIR,
    embeddings: Embeddings | None = None,
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

    embedding_function = embeddings or OpenAIEmbeddings()
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
        delete_existing=not args.keep_existing,
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )
    count = vector_store._collection.count()
    print(f"Campus knowledge base index built at: {args.vector_store_dir}")
    print(f"Indexed chunks: {count}")


if __name__ == "__main__":
    main()
