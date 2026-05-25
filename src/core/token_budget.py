import math
import re

from langchain_core.documents import Document

DEFAULT_MAX_CONTEXT_DOCS = 5
DEFAULT_MAX_CONTEXT_CHARS = 6000
DEFAULT_MAX_CHUNK_CHARS = 1500
TRUNCATION_SUFFIX = "\n...[内容已按上下文预算截断]"
CHINESE_CHARACTER_PATTERN = re.compile(r"[\u4e00-\u9fff]")


def estimate_tokens(text: str) -> int:
    """Estimate context tokens without requiring a provider tokenizer."""
    if not text:
        return 0
    chinese_chars = len(CHINESE_CHARACTER_PATTERN.findall(text))
    other_chars = len(text) - chinese_chars
    return chinese_chars + math.ceil(other_chars / 4)


def trim_text_to_budget(text: str, max_chars: int) -> str:
    """Trim text to a character budget while keeping the result readable."""
    normalized = text.strip()
    if max_chars <= 0:
        return ""
    if len(normalized) <= max_chars:
        return normalized
    if max_chars <= len(TRUNCATION_SUFFIX):
        return normalized[:max_chars]
    return normalized[: max_chars - len(TRUNCATION_SUFFIX)].rstrip() + TRUNCATION_SUFFIX


def _format_context_doc(document: Document) -> str:
    metadata = document.metadata
    fields = [
        f"Source: {metadata.get('source', 'unknown')}",
        f"Chunk: {metadata.get('chunk_id', '')}",
    ]
    optional_fields = [
        ("Section", "section"),
        ("Heading Path", "heading_path"),
        ("Policy Type", "policy_type"),
        ("Path", "path"),
    ]
    fields.extend(
        f"{label}: {metadata[key]}" for label, key in optional_fields if metadata.get(key)
    )
    return f"--- {' | '.join(fields)} ---\n{document.page_content}"


def format_rag_context(docs: list[Document]) -> str:
    """Format selected evidence with stable source and chunk identifiers."""
    return "\n\n".join(_format_context_doc(document) for document in docs)


def select_context_docs(
    docs: list[Document],
    max_docs: int = DEFAULT_MAX_CONTEXT_DOCS,
    max_total_chars: int = DEFAULT_MAX_CONTEXT_CHARS,
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
) -> list[Document]:
    """Select ranked evidence chunks while bounding the formatted LLM context."""
    if max_docs <= 0 or max_total_chars <= 0 or max_chunk_chars <= 0:
        return []

    selected: list[Document] = []
    used_chars = 0
    for document in docs:
        if len(selected) >= max_docs:
            break
        content = trim_text_to_budget(document.page_content, max_chunk_chars)
        if not content:
            continue

        separator_chars = 2 if selected else 0
        candidate = Document(page_content=content, metadata=dict(document.metadata))
        rendered = _format_context_doc(candidate)
        remaining_chars = max_total_chars - used_chars - separator_chars
        if remaining_chars <= 0:
            break
        if len(rendered) > remaining_chars:
            empty_body = Document(page_content="", metadata=dict(document.metadata))
            header_length = len(_format_context_doc(empty_body))
            available_body_chars = remaining_chars - header_length
            content = trim_text_to_budget(content, available_body_chars)
            if not content:
                break
            candidate = Document(page_content=content, metadata=dict(document.metadata))
            rendered = _format_context_doc(candidate)

        selected.append(candidate)
        used_chars += separator_chars + len(rendered)

    return selected
