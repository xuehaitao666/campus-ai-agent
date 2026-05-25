import pytest
from langchain_core.documents import Document

from agents import tools as campus_tools
from agents.tools import database_search, database_search_func, format_contexts


class FakeRetriever:
    def __init__(self, documents):
        self.documents = documents
        self.queries = []

    def invoke(self, query: str):
        self.queries.append(query)
        return self.documents


class FailingRetriever:
    def invoke(self, query: str):
        raise RuntimeError(f"retrieval failed: {query}")


def test_database_search_tool_is_registered_with_expected_name():
    assert database_search.name == "Database_Search"


def test_database_search_returns_retrieved_context_with_metadata(monkeypatch):
    documents = [
        Document(
            page_content="学生请假应当提交请假申请和证明材料。",
            metadata={
                "source": "leave_policy.md",
                "path": "/kb/leave_policy.md",
                "chunk_id": "leave_policy.md::chunk-0001",
            },
        )
    ]
    fake_retriever = FakeRetriever(documents)
    monkeypatch.setattr(campus_tools, "load_chroma_db", lambda: fake_retriever)

    result = database_search_func("请假需要什么材料？")

    assert fake_retriever.queries == ["请假需要什么材料？"]
    assert "学生请假应当提交请假申请和证明材料。" in result
    assert "Source: leave_policy.md" in result
    assert "Path: /kb/leave_policy.md" in result
    assert "Chunk: leave_policy.md::chunk-0001" in result
    assert "### 来源" in result
    assert "- leave_policy.md | leave_policy.md::chunk-0001 | /kb/leave_policy.md" in result


def test_database_search_tool_invokes_search_without_real_vector_store(monkeypatch):
    documents = [
        Document(
            page_content="考试作弊将按照考试纪律相关规定处理。",
            metadata={"source": "exam_policy.md", "chunk_id": "exam-policy-1"},
        )
    ]
    monkeypatch.setattr(campus_tools, "load_chroma_db", lambda: FakeRetriever(documents))

    result = database_search.invoke({"query": "考试作弊有什么后果？"})

    assert "考试作弊将按照考试纪律相关规定处理。" in result
    assert "Source: exam_policy.md" in result
    assert "Chunk: exam-policy-1" in result


def test_database_search_empty_results_returns_no_answer_without_fabricating_details(monkeypatch):
    monkeypatch.setattr(campus_tools, "load_chroma_db", lambda: FakeRetriever([]))

    result = database_search_func("知识库里不存在的问题")

    assert "当前知识库中没有找到明确依据" in result
    assert "建议以学校官方通知或辅导员答复为准" in result
    assert "不得编造具体制度、电话、办公室、网址" in result
    assert "http://" not in result
    assert "https://" not in result


def test_database_search_low_relevance_results_return_no_answer(monkeypatch):
    documents = [
        Document(
            page_content="大学英语选课办理流程，本课程强调听说读写训练。",
            metadata={"source": "course_intro.md", "chunk_id": "english-1"},
        )
    ]
    monkeypatch.setattr(campus_tools, "load_chroma_db", lambda: FakeRetriever(documents))

    result = database_search_func("宿舍晚归办理流程是什么？")

    assert "当前知识库中没有找到明确依据" in result
    assert "当前检索结果与问题相关性不足" in result
    assert "大学英语" not in result


def test_database_search_propagates_retriever_errors(monkeypatch):
    monkeypatch.setattr(campus_tools, "load_chroma_db", lambda: FailingRetriever())

    with pytest.raises(RuntimeError, match="retrieval failed"):
        database_search_func("触发检索异常")


def test_format_contexts_preserves_stable_document_and_metadata_format():
    documents = [
        Document(
            page_content="第一段制度内容。",
            metadata={
                "source": "student_handbook.md",
                "path": "/kb/student_handbook.md",
                "chunk_id": "student_handbook.md::chunk-0001",
            },
        ),
        Document(
            page_content="第二段制度内容。",
            metadata={
                "source": "exam_policy.md",
                "path": "/kb/exam_policy.md",
                "chunk_id": "exam_policy.md::chunk-0002",
            },
        ),
    ]

    result = format_contexts(documents)

    assert result == (
        "--- Source: student_handbook.md | Path: /kb/student_handbook.md | "
        "Chunk: student_handbook.md::chunk-0001 ---\n"
        "第一段制度内容。\n\n"
        "--- Source: exam_policy.md | Path: /kb/exam_policy.md | "
        "Chunk: exam_policy.md::chunk-0002 ---\n"
        "第二段制度内容。"
    )
