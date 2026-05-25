import re
from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

DEFAULT_CHUNK_SIZE = 800
DEFAULT_CHUNK_OVERLAP = 120
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
POLICY_TYPE_MAP = {
    "leave_policy.md": "leave",
    "exam_policy.md": "exam",
    "scholarship_policy.md": "scholarship",
    "dormitory_policy.md": "dormitory",
    "student_handbook.md": "handbook",
}


@dataclass
class MarkdownSection:
    text: str
    section: str
    heading_path: str


def infer_policy_type(source: str) -> str:
    """Infer a stable policy category from a Markdown source filename."""
    filename = source.rsplit("/", 1)[-1].lower()
    return POLICY_TYPE_MAP.get(filename, "general")


def _splitter(chunk_size: int, chunk_overlap: int) -> RecursiveCharacterTextSplitter:
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", "，", " ", ""],
    )


def _chunk_metadata(document: Document) -> dict:
    metadata = dict(document.metadata)
    source = str(metadata.get("source", "unknown"))
    metadata.setdefault("path", "")
    metadata.setdefault("section", "未分节")
    metadata.setdefault("heading_path", metadata["section"])
    metadata["policy_type"] = infer_policy_type(source)
    return metadata


def _assign_chunk_ids(chunks: list[Document]) -> list[Document]:
    for index, chunk in enumerate(chunks, 1):
        source = str(chunk.metadata.get("source", "unknown"))
        chunk.metadata["chunk_id"] = f"{source}::chunk-{index:04d}"
    return chunks


def fixed_size_chunk(
    document: Document,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Document]:
    """Split one document by size while attaching baseline RAG metadata."""
    metadata = _chunk_metadata(document)
    prepared = Document(page_content=document.page_content, metadata=metadata)
    chunks = [
        chunk
        for chunk in _splitter(chunk_size, chunk_overlap).split_documents([prepared])
        if chunk.page_content.strip()
    ]
    return _assign_chunk_ids(chunks)


def _markdown_sections(document: Document) -> list[MarkdownSection]:
    sections: list[MarkdownSection] = []
    heading_stack: list[str] = []
    buffer: list[str] = []
    current_section = "未分节"
    current_path = "未分节"

    def flush() -> None:
        text = "\n".join(buffer).strip()
        body_lines = [
            line for line in buffer if line.strip() and HEADING_PATTERN.match(line) is None
        ]
        if text and body_lines:
            sections.append(
                MarkdownSection(
                    text=text,
                    section=current_section,
                    heading_path=current_path,
                )
            )

    for line in document.page_content.splitlines():
        heading = HEADING_PATTERN.match(line)
        if heading:
            flush()
            buffer = []
            level = len(heading.group(1))
            title = heading.group(2).strip()
            heading_stack[level - 1 :] = [title]
            current_section = title
            current_path = " > ".join(heading_stack)
        buffer.append(line)

    flush()
    return sections


def markdown_heading_chunk(
    document: Document,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Document]:
    """Split Markdown at headings, with size-based subdivision for long sections."""
    sections = _markdown_sections(document)
    if not sections:
        return fixed_size_chunk(document, chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    chunks: list[Document] = []
    for section in sections:
        metadata = {
            **document.metadata,
            "section": section.section,
            "heading_path": section.heading_path,
        }
        section_chunks = fixed_size_chunk(
            Document(page_content=section.text, metadata=metadata),
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        chunks.extend(section_chunks)

    return _assign_chunk_ids(chunks)
