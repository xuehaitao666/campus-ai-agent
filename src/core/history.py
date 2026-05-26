from collections.abc import Sequence

from langchain_core.messages import AnyMessage, SystemMessage


def trim_messages_for_model(
    messages: Sequence[AnyMessage],
    max_messages: int,
) -> tuple[list[AnyMessage], int]:
    """Keep all system messages and the latest bounded conversation messages."""
    if max_messages < 1:
        raise ValueError("max_messages must be at least 1")

    non_system_count = sum(1 for message in messages if not isinstance(message, SystemMessage))
    remaining_to_drop = max(0, non_system_count - max_messages)
    trimmed_message_count = remaining_to_drop
    trimmed_messages: list[AnyMessage] = []

    for message in messages:
        if not isinstance(message, SystemMessage) and remaining_to_drop:
            remaining_to_drop -= 1
            continue
        trimmed_messages.append(message)

    return trimmed_messages, trimmed_message_count
