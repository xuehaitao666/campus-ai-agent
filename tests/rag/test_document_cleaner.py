from rag.document_cleaner import clean_markdown_text


def test_clean_markdown_text_normalizes_whitespace_without_losing_markdown_structure():
    raw_text = (
        "\r\n# 学生请假制度   \r\n\r\n\r\n\r\n"
        "## 办理流程\t \r\n\r\n"
        "- 提交申请   \r\n"
        "- 上传材料\t\r\n"
    )

    cleaned = clean_markdown_text(raw_text)

    assert cleaned == "# 学生请假制度\n\n## 办理流程\n\n- 提交申请\n- 上传材料"
    assert "\n\n\n" not in cleaned
    assert "# 学生请假制度" in cleaned
    assert "- 提交申请\n- 上传材料" in cleaned


def test_clean_markdown_text_handles_empty_string():
    assert clean_markdown_text("") == ""
