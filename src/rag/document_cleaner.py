import re


def clean_markdown_text(text: str) -> str:
    """Normalize harmless Markdown whitespace while preserving document structure."""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = "\n".join(line.rstrip() for line in normalized.split("\n"))
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()
