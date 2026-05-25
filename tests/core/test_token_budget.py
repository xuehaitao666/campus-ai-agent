from langchain_core.documents import Document

from core.token_budget import (
    estimate_tokens,
    format_rag_context,
    select_context_docs,
    trim_text_to_budget,
)


def _document(content: str, source: str = "leave_policy.md", chunk_id: str = "leave-1"):
    return Document(
        page_content=content,
        metadata={
            "source": source,
            "chunk_id": chunk_id,
            "section": "请假流程",
            "heading_path": "学生请假制度 > 请假流程",
            "policy_type": "leave",
        },
    )


def test_estimate_tokens_supports_chinese_and_english_text():
    assert estimate_tokens("请假流程") > 0
    assert estimate_tokens("leave application process") > 0
    assert estimate_tokens("") == 0


def test_trim_text_to_budget_limits_long_text():
    result = trim_text_to_budget("制度内容" * 30, max_chars=25)

    assert len(result) <= 25
    assert "截断" in result


def test_select_context_docs_limits_document_count_and_preserves_metadata():
    documents = [_document(f"制度内容 {index}", chunk_id=f"leave-{index}") for index in range(4)]

    selected = select_context_docs(documents, max_docs=2)

    assert len(selected) == 2
    assert selected[0].metadata["source"] == "leave_policy.md"
    assert selected[0].metadata["chunk_id"] == "leave-0"


def test_select_context_docs_limits_formatted_total_chars_and_chunk_length():
    documents = [
        _document("考试处理规定。" * 30, "exam_policy.md", f"exam-{index}") for index in range(3)
    ]

    selected = select_context_docs(
        documents,
        max_docs=3,
        max_total_chars=220,
        max_chunk_chars=90,
    )
    context = format_rag_context(selected)

    assert selected
    assert len(context) <= 220
    assert all(len(document.page_content) <= 90 for document in selected)


def test_format_rag_context_includes_source_chunk_and_section():
    context = format_rag_context([_document("学生提交申请材料。")])

    assert "Source: leave_policy.md" in context
    assert "Chunk: leave-1" in context
    assert "Section: 请假流程" in context
    assert "学生提交申请材料。" in context


def test_empty_context_documents_do_not_fail():
    assert select_context_docs([]) == []
    assert format_rag_context([]) == ""
