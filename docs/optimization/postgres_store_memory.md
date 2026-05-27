# Research Assistant Long-Term Memory

## Scope

The default `research-assistant` now uses the LangGraph store for a minimal user-scoped
long-term memory loop. It stores only user messages that explicitly ask the assistant to
remember a preference or standing instruction, and injects the saved note as concise
context before a later model call.

## Checkpointer and Store

`checkpointer` is thread-scoped conversation state. It is keyed by `thread_id` and preserves
the graph state and message history needed for multi-turn conversations.

`store` is user-scoped long-term storage. The research assistant uses `user_id` with the
namespace `("user_memory", user_id)` and the key `"profile"` to save one recent explicit
memory note.

With `DATABASE_TYPE=postgres`, the service initializes both `AsyncPostgresSaver` and
`AsyncPostgresStore`, so conversation state and saved user memory persist across service
processes. With the default SQLite mode, checkpoints are persisted in SQLite while the
store is an `InMemoryStore`, which is sufficient for local execution and tests but does not
survive a service restart.

## Behavior

- Only explicit memory intent such as `记住`, `以后默认`, `我的偏好`, or `我希望你以后` is saved.
- Common sensitive markers such as passwords, identity-card numbers, tokens, and API keys
  are rejected by the minimal memory extraction rule.
- A saved note is capped in length and replaces the previous profile note, so it cannot grow
  without bound.
- Store read or write failures are logged and do not block the main assistant response.

## Limitations

- Memory is a single recent note, not semantic memory search.
- The implementation does not automatically summarize conversation history.
- It is not a comprehensive privacy or sensitive-data classification system.
- Only `research-assistant` explicitly reads and writes this profile memory in the default
  product flow.
