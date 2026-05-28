import os
from uuid import uuid4

import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_POSTGRES_TESTS") != "1",
    reason="Set RUN_POSTGRES_TESTS=1 and configure POSTGRES_* env vars to run this test.",
)


@pytest.mark.asyncio
async def test_postgres_store_persists_user_memory_across_store_instances():
    from memory.postgres import get_postgres_store
    from memory.user_memory import (
        USER_MEMORY_KEY,
        USER_MEMORY_NAMESPACE,
        delete_user_memory,
        get_user_memory,
    )

    user_id = f"postgres-memory-test-{uuid4()}"
    namespace = (USER_MEMORY_NAMESPACE, user_id)

    async with get_postgres_store() as store:
        await store.aput(namespace, USER_MEMORY_KEY, {"memory": "偏好简洁回答"})

    async with get_postgres_store() as store:
        memory = await get_user_memory(store, user_id)
        await delete_user_memory(store, user_id)

    assert memory is not None
    assert memory["memory"] == "偏好简洁回答"
