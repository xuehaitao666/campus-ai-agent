from langchain_core.documents import Document

from agents import tools as campus_tools
from agents.research_assistant import tools
from agents.tools import query_campus_policy, query_campus_policy_func


class FakeRetriever:
    def __init__(self, documents):
        self.documents = documents
        self.queries = []

    def invoke(self, query: str):
        self.queries.append(query)
        return self.documents


def _tool_names() -> set[str]:
    return {tool.name for tool in tools}


def test_query_campus_policy_is_registered_in_default_agent():
    assert query_campus_policy.name == "query_campus_policy"
    assert "query_campus_policy" in _tool_names()


def test_query_campus_policy_returns_fixed_sections_and_leave_source(monkeypatch):
    documents = [
        Document(
            page_content=(
                "# 学生请假制度\n\n"
                "## 办理流程或处理流程\n"
                "学生在请假系统或学院指定表单中提交请假申请。\n"
                "上传诊断证明、就诊记录或其他证明材料。\n\n"
                "## 注意事项\n"
                "请假期间如涉及考试，应单独办理缓考或补考申请。"
            ),
            metadata={"source": "leave_policy.md", "path": "/kb/leave_policy.md", "chunk_id": "leave-1"},
        )
    ]
    fake_retriever = FakeRetriever(documents)
    monkeypatch.setattr(campus_tools, "load_chroma_db", lambda: fake_retriever)

    result = query_campus_policy_func("请假流程是什么？")

    assert fake_retriever.queries == ["请假流程是什么？"]
    assert "## 简要结论" in result
    assert "## 依据说明" in result
    assert "## 办理流程" in result
    assert "## 注意事项" in result
    assert "## 来源文档" in result
    assert "### 制度明确规定" in result
    assert "### 建议性提醒" in result
    assert "leave_policy.md" in result
    assert "请假系统" in result
    assert "不代表查询了真实学校系统" in result


def test_query_campus_policy_returns_scholarship_and_exam_sources(monkeypatch):
    documents = [
        Document(
            page_content="奖学金评定办法\n申请条件包括学业成绩、综合测评和无严重违纪记录。",
            metadata={"source": "scholarship_policy.md", "chunk_id": "scholarship-1"},
        ),
        Document(
            page_content="考试纪律与缓考管理规定\n考试作弊通常会导致该课程考试成绩无效或记为零分。",
            metadata={"source": "exam_policy.md", "chunk_id": "exam-1"},
        ),
    ]
    monkeypatch.setattr(campus_tools, "load_chroma_db", lambda: FakeRetriever(documents))

    result = query_campus_policy_func("挂科后还能评奖学金吗？考试作弊有什么后果？")

    assert "scholarship_policy.md" in result
    assert "exam_policy.md" in result
    assert "奖学金" in result
    assert "考试作弊" in result


def test_query_campus_policy_no_match_does_not_fabricate(monkeypatch):
    monkeypatch.setattr(campus_tools, "load_chroma_db", lambda: FakeRetriever([]))

    result = query_campus_policy_func("火星交换生宿舍制度是什么？")

    assert "知识库中未找到明确依据" in result
    assert "## 来源文档\n无" in result
    assert "电话号码" in result


def test_query_campus_policy_low_relevance_returns_insufficient_basis(monkeypatch):
    documents = [
        Document(
            page_content="大学英语课程介绍\n本课程强调听说读写训练。",
            metadata={"source": "student_handbook.md", "chunk_id": "student-1"},
        )
    ]
    monkeypatch.setattr(campus_tools, "load_chroma_db", lambda: FakeRetriever(documents))

    result = query_campus_policy_func("宿舍晚归会怎么处理？")

    assert "知识库中未找到明确依据" in result
    assert "当前依据不足" in result
    assert "大学英语" not in result
    assert "## 来源文档\n无" in result


def test_query_campus_policy_does_not_fabricate_contacts_urls_or_windows(monkeypatch):
    documents = [
        Document(
            page_content="考试纪律与缓考管理规定\n因病无法参加考试，可以申请缓考。",
            metadata={"source": "exam_policy.md", "chunk_id": "exam-2"},
        )
    ]
    monkeypatch.setattr(campus_tools, "load_chroma_db", lambda: FakeRetriever(documents))

    result = query_campus_policy_func("如果因为生病缺考怎么办？")

    assert "exam_policy.md" in result
    assert "当前知识库未提供明确说明" in result
    assert "电话：" not in result
    assert "http://" not in result
    assert "https://" not in result
    assert "办理窗口：" not in result
