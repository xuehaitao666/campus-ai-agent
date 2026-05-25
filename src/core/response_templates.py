from collections.abc import Mapping

ParsedArgs = Mapping[str, str | None]


def _format_conditions(parsed_args: ParsedArgs, labels: dict[str, str]) -> str:
    conditions = [
        f"- {labels[key]}：`{value}`"
        for key, value in parsed_args.items()
        if value and key in labels
    ]
    return "\n".join(conditions) if conditions else "- 未提取到可展示的筛选条件"


def _is_empty_result(tool_result: str) -> bool:
    return not tool_result.strip() or "没有找到符合条件" in tool_result


def format_course_fast_path_response(
    query: str,
    parsed_args: ParsedArgs,
    tool_result: str,
) -> str:
    """Wrap a course lookup string in a stable Markdown response."""
    if _is_empty_result(tool_result):
        return format_fast_path_empty_result("course", query, parsed_args)
    conditions = _format_conditions(
        parsed_args,
        {"day": "星期", "time_period": "时间段", "course_name": "课程关键词"},
    )
    return (
        "## 课程查询结果\n\n"
        "### 查询条件\n"
        f"- 问题：{query}\n"
        f"{conditions}\n\n"
        "### 结果\n"
        f"{tool_result}\n\n"
        "### 下一步\n"
        "你还可以继续按星期、时间段或课程名称查询。"
    )


def format_event_fast_path_response(
    query: str,
    parsed_args: ParsedArgs,
    tool_result: str,
) -> str:
    """Wrap a campus event lookup string in a stable Markdown response."""
    if _is_empty_result(tool_result):
        return format_fast_path_empty_result("event", query, parsed_args)
    conditions = _format_conditions(
        parsed_args,
        {
            "keyword": "关键词",
            "date_range": "日期范围",
            "event_type": "活动类型",
            "target_audience": "适合人群",
        },
    )
    return (
        "## 校园活动查询结果\n\n"
        "### 查询条件\n"
        f"- 问题：{query}\n"
        f"{conditions}\n\n"
        "### 结果\n"
        f"{tool_result}\n\n"
        "### 下一步\n"
        "你还可以继续按日期、活动类型或关键词查询校园活动。"
    )


def format_fast_path_empty_result(intent: str, query: str, parsed_args: ParsedArgs) -> str:
    """Return a readable empty-result message without exposing internal details."""
    is_course = intent in {"course", "course_schedule"}
    title = "课程查询结果" if is_course else "校园活动查询结果"
    retry_hint = (
        "请尝试更换星期、时间段或课程名称。"
        if is_course
        else "请尝试更换日期范围、活动类型或关键词。"
    )
    condition_labels = (
        {"day": "星期", "time_period": "时间段", "course_name": "课程关键词"}
        if is_course
        else {
            "keyword": "关键词",
            "date_range": "日期范围",
            "event_type": "活动类型",
            "target_audience": "适合人群",
        }
    )
    conditions = _format_conditions(parsed_args, condition_labels)
    return (
        f"## {title}\n\n"
        "### 查询条件\n"
        f"- 问题：{query}\n"
        f"{conditions}\n\n"
        "### 结果\n"
        "暂未找到符合条件的信息。\n\n"
        "### 下一步\n"
        f"{retry_hint}"
    )


def format_fast_path_error(intent: str, error_message: str) -> str:
    """Return a user-facing error message while keeping internal details out of content."""
    _ = error_message
    title = "课程查询结果" if intent in {"course", "course_schedule"} else "校园活动查询结果"
    return (
        f"## {title}\n\n"
        "### 查询状态\n"
        "查询服务暂时不可用，请稍后重试。\n\n"
        "### 下一步\n"
        "你也可以换一种查询条件后再次尝试。"
    )
