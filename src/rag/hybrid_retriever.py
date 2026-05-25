import math
import re
from collections import Counter
from dataclasses import dataclass

from langchain_core.documents import Document

TEXT_PATTERN = re.compile(r"[\u4e00-\u9fff]+|[a-zA-Z0-9_]+")


@dataclass
class BM25Index:
    documents: list[Document]
    tokenized_documents: list[list[str]]
    term_frequencies: list[Counter[str]]
    document_frequencies: Counter[str]
    average_document_length: float


def tokenize_for_bm25(text: str) -> list[str]:
    """Tokenize English tokens and Chinese character bigrams for policy search."""
    tokens: list[str] = []
    for segment in TEXT_PATTERN.findall(text.lower()):
        if re.fullmatch(r"[\u4e00-\u9fff]+", segment):
            if len(segment) == 1:
                tokens.append(segment)
            else:
                tokens.extend(segment[index : index + 2] for index in range(len(segment) - 1))
        else:
            tokens.append(segment)
    return tokens


def build_bm25_index(documents: list[Document]) -> BM25Index:
    """Build an in-memory BM25 index from persisted policy chunks."""
    tokenized_documents = [tokenize_for_bm25(document.page_content) for document in documents]
    term_frequencies = [Counter(tokens) for tokens in tokenized_documents]
    document_frequencies: Counter[str] = Counter()
    for tokens in tokenized_documents:
        document_frequencies.update(set(tokens))
    average_length = (
        sum(len(tokens) for tokens in tokenized_documents) / len(tokenized_documents)
        if tokenized_documents
        else 0.0
    )
    return BM25Index(
        documents=list(documents),
        tokenized_documents=tokenized_documents,
        term_frequencies=term_frequencies,
        document_frequencies=document_frequencies,
        average_document_length=average_length,
    )


def bm25_search(
    query: str,
    documents: list[Document] | BM25Index,
    top_k: int = 5,
) -> list[Document]:
    """Return the highest-scoring BM25 documents for a query."""
    index = documents if isinstance(documents, BM25Index) else build_bm25_index(documents)
    query_tokens = tokenize_for_bm25(query)
    if not index.documents or not query_tokens:
        return []

    scores: list[tuple[float, int]] = []
    document_count = len(index.documents)
    average_length = index.average_document_length or 1.0
    k1 = 1.5
    b = 0.75
    for position, frequencies in enumerate(index.term_frequencies):
        document_length = len(index.tokenized_documents[position])
        score = 0.0
        for token in query_tokens:
            frequency = frequencies.get(token, 0)
            if frequency == 0:
                continue
            document_frequency = index.document_frequencies[token]
            inverse_frequency = math.log(
                1 + (document_count - document_frequency + 0.5) / (document_frequency + 0.5)
            )
            denominator = frequency + k1 * (1 - b + b * document_length / average_length)
            score += inverse_frequency * frequency * (k1 + 1) / denominator
        if score > 0:
            scores.append((score, position))

    scores.sort(key=lambda value: (-value[0], value[1]))
    return [index.documents[position] for _, position in scores[:top_k]]


def _document_key(document: Document) -> str:
    chunk_id = str(document.metadata.get("chunk_id", "")).strip()
    if chunk_id:
        return chunk_id
    source = str(document.metadata.get("source", "unknown"))
    return f"{source}:{document.page_content}"


def reciprocal_rank_fusion(
    vector_docs: list[Document],
    bm25_docs: list[Document],
    k: int = 60,
    top_k: int = 5,
) -> list[Document]:
    """Fuse independent rankings without comparing incompatible raw scores."""
    scores: dict[str, float] = {}
    documents: dict[str, Document] = {}
    ranks: dict[str, dict[str, int]] = {}

    for source, candidates in (("vector", vector_docs), ("bm25", bm25_docs)):
        for rank, document in enumerate(candidates, 1):
            key = _document_key(document)
            documents.setdefault(key, document)
            ranks.setdefault(key, {})[source] = rank
            scores[key] = scores.get(key, 0.0) + 1 / (k + rank)

    ordered_keys = sorted(
        scores,
        key=lambda key: (
            -scores[key],
            min(ranks[key].values()),
            key,
        ),
    )
    fused_documents: list[Document] = []
    for key in ordered_keys[:top_k]:
        metadata = dict(documents[key].metadata)
        matched_sources = ranks[key]
        metadata.update(
            {
                "retrieval_source": (
                    "vector+bm25" if len(matched_sources) == 2 else next(iter(matched_sources))
                ),
                "hybrid_score": scores[key],
                "vector_rank": matched_sources.get("vector"),
                "bm25_rank": matched_sources.get("bm25"),
            }
        )
        fused_documents.append(
            Document(page_content=documents[key].page_content, metadata=metadata)
        )
    return fused_documents


def hybrid_search(
    query: str,
    vector_retriever,
    bm25_documents: list[Document] | BM25Index,
    top_k: int = 5,
    vector_k: int = 8,
    bm25_k: int = 8,
) -> list[Document]:
    """Execute vector and BM25 retrieval, then return RRF-fused chunks."""
    vector_docs = list(vector_retriever.invoke(query))[:vector_k]
    bm25_docs = bm25_search(query, bm25_documents, top_k=bm25_k)
    return reciprocal_rank_fusion(vector_docs, bm25_docs, top_k=top_k)
