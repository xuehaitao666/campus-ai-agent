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

This explains the restart behavior:

| Mode | Checkpointer | Long-term store | Survives backend restart? |
| --- | --- | --- | --- |
| `DATABASE_TYPE=` or `sqlite` | `AsyncSqliteSaver` | `InMemoryStore` | thread checkpoints can persist, profile memory does not |
| `DATABASE_TYPE=postgres` | `AsyncPostgresSaver` | `AsyncPostgresStore` | yes, as long as the Postgres volume/database is kept |

## Enable Persistent Postgres Memory

Use the existing project settings; no separate memory-specific environment variables are
needed:

```env
DATABASE_TYPE=postgres
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_DB=campus_agent
```

When running outside Docker against a local database, set `POSTGRES_HOST=localhost` instead.
In Docker Compose, `POSTGRES_HOST=postgres` points the backend container at the Compose
Postgres service.

## Cross-Restart Verification

1. Start the service in Postgres mode.
2. Send: `请记住我偏好简洁回答`
3. Send: `你记住了我什么？`
4. Stop only the backend service.
5. Start the backend service again while keeping the Postgres volume/database.
6. Send again: `你记住了我什么？`
7. Expected result: the answer still includes `偏好简洁回答`.

If the same steps are run in the default SQLite mode, the long-term memory is expected to
disappear after backend restart because the store is in memory.

## Behavior

- Only explicit memory intent such as `记住`, `以后默认`, `我的偏好`, or `我希望你以后` is saved.
- Common sensitive markers such as passwords, identity-card numbers, tokens, and API keys
  are rejected by the minimal memory extraction rule.
- A saved note is capped in length and replaces the previous profile note, so it cannot grow
  without bound.
- Store read or write failures are logged and do not block the main assistant response.
- Users can now explicitly view or delete their stored profile note through
  `view_user_memory` and `delete_user_memory`; deletion uses the store's native
  `adelete` operation.
- Memory management tools derive `user_id` from the current LangGraph runtime rather
  than exposing an arbitrary user-id argument, so users manage only their own memory.

## Limitations

- Memory is a single recent note, not semantic memory search.
- The implementation does not automatically summarize conversation history.
- It is not a comprehensive privacy or sensitive-data classification system.
- Only `research-assistant` explicitly reads and writes this profile memory in the default
  product flow.
- There is not yet a dedicated frontend memory-management screen or memory-edit tool.
