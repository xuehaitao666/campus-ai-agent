import pytest
from langchain_core.documents import Document

from rag.chunking import fixed_size_chunk, infer_policy_type, markdown_heading_chunk


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("leave_policy.md", "leave"),
        ("exam_policy.md", "exam"),
        ("scholarship_policy.md", "scholarship"),
        ("dormitory_policy.md", "dormitory"),
        ("student_handbook.md", "handbook"),
        ("other_policy.md", "general"),
    ],
)
def test_infer_policy_type(source, expected):
    assert infer_policy_type(source) == expected


def test_markdown_heading_chunk_preserves_heading_metadata_and_stable_ids():
    document = Document(
        page_content=(
            "# 学生请假制度\n\n说明文字。\n\n"
            "## 办理流程\n\n学生提交申请。\n\n"
            "### 病假材料\n\n上传诊断证明。"
        ),
        metadata={"source": "leave_policy.md", "path": "/kb/leave_policy.md"},
    )

    chunks = markdown_heading_chunk(document)

    assert [chunk.metadata["chunk_id"] for chunk in chunks] == [
        "leave_policy.md::chunk-0001",
        "leave_policy.md::chunk-0002",
        "leave_policy.md::chunk-0003",
    ]
    assert [chunk.metadata["section"] for chunk in chunks] == [
        "学生请假制度",
        "办理流程",
        "病假材料",
    ]
    assert chunks[2].metadata["heading_path"] == "学生请假制度 > 办理流程 > 病假材料"
    assert all(chunk.metadata["source"] == "leave_policy.md" for chunk in chunks)
    assert all(chunk.metadata["path"] == "/kb/leave_policy.md" for chunk in chunks)
    assert all(chunk.metadata["policy_type"] == "leave" for chunk in chunks)


def test_fixed_size_chunk_handles_unheaded_document():
    document = Document(
        page_content="无标题制度说明，仍然需要能够进入索引。",
        metadata={"source": "other_policy.md", "path": "/kb/other_policy.md"},
    )

    chunks = fixed_size_chunk(document, chunk_size=20, chunk_overlap=5)

    assert chunks
    assert all(chunk.metadata["section"] == "未分节" for chunk in chunks)
    assert all(chunk.metadata["heading_path"] == "未分节" for chunk in chunks)
    assert all(chunk.metadata["policy_type"] == "general" for chunk in chunks)


def test_long_heading_section_is_subdivided_without_losing_metadata():
    document = Document(
        page_content="# 考试纪律\n\n## 作弊处理\n\n" + "考试作弊将按规定处理。" * 20,
        metadata={"source": "exam_policy.md", "path": "/kb/exam_policy.md"},
    )

    chunks = markdown_heading_chunk(document, chunk_size=60, chunk_overlap=10)
    treatment_chunks = [chunk for chunk in chunks if chunk.metadata["section"] == "作弊处理"]

    assert len(treatment_chunks) > 1
    assert all(
        chunk.metadata["heading_path"] == "考试纪律 > 作弊处理" for chunk in treatment_chunks
    )
    assert all(chunk.metadata["policy_type"] == "exam" for chunk in treatment_chunks)
    assert all(chunk.page_content.strip() for chunk in chunks)


def test_heading_containers_without_body_do_not_create_noise_chunks():
    document = Document(
        page_content="# 宿舍规定\n\n说明。\n\n## 管理要求\n\n### 晚归\n\n晚归需要登记。",
        metadata={"source": "dormitory_policy.md", "path": "/kb/dormitory_policy.md"},
    )

    chunks = markdown_heading_chunk(document)

    assert "管理要求" not in {chunk.metadata["section"] for chunk in chunks}
    late_return = next(chunk for chunk in chunks if chunk.metadata["section"] == "晚归")
    assert late_return.metadata["heading_path"] == "宿舍规定 > 管理要求 > 晚归"
