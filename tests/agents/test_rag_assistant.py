import pytest
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableLambda

from agents import rag_assistant as rag_module
from agents import tools as campus_tools
from agents.safeguard import SafeguardOutput, SafetyAssessment


class SafeSafeguard:
    async def ainvoke(self, messages):
        return SafeguardOutput(safety_assessment=SafetyAssessment.SAFE)


class FakeRetriever:
    def __init__(self, documents):
        self.documents = documents
        self.queries = []

    def invoke(self, query: str):
        self.queries.append(query)
        return self.documents


class DatabaseSearchFakeModel:
    def __init__(self, query: str, final_answer: str):
        self.query = query
        self.final_answer = final_answer
        self.bound_tool_names = []
        self.calls = []

    def bind_tools(self, available_tools):
        self.bound_tool_names = [tool.name for tool in available_tools]

        async def invoke(messages):
            self.calls.append(messages)
            tool_messages = [message for message in messages if isinstance(message, ToolMessage)]
            if not tool_messages:
                return AIMessage(
                    content="",
                    tool_calls=[
                        {
                            "name": "Database_Search",
                            "args": {"query": self.query},
                            "id": "call-database-search-1",
                            "type": "tool_call",
                        }
                    ],
                )

            return AIMessage(content=self.final_answer)

        return RunnableLambda(invoke)


def test_rag_assistant_binds_database_search_and_constrains_knowledge_answers():
    assert [tool.name for tool in rag_module.tools] == ["Database_Search"]
    assert "Database_Search" in rag_module.instructions
    assert "只能基于数据库检索结果或用户已提供资料" in rag_module.instructions
    assert "没有找到明确依据" in rag_module.instructions
    assert "不要编造学校规定" in rag_module.instructions
    assert "来源信息" in rag_module.instructions


@pytest.mark.asyncio
async def test_rag_assistant_runs_model_database_search_model_cycle(monkeypatch):
    documents = [
        Document(
            page_content="学生请假应当提交申请，并上传相应证明材料。",
            metadata={
                "source": "leave_policy.md",
                "path": "/kb/leave_policy.md",
                "chunk_id": "leave_policy.md::chunk-0001",
            },
        )
    ]
    fake_retriever = FakeRetriever(documents)
    fake_model = DatabaseSearchFakeModel(
        "请假需要提交哪些材料？",
        "根据请假制度，需要提交申请并上传证明材料。",
    )
    monkeypatch.setattr(campus_tools, "load_chroma_db", lambda: fake_retriever)
    monkeypatch.setattr(rag_module, "Safeguard", SafeSafeguard)
    monkeypatch.setattr(rag_module, "get_model", lambda model_name: fake_model)

    result = await rag_module.rag_assistant.ainvoke(
        {"messages": [HumanMessage(content="请假需要提交哪些材料？")]},
        config={"configurable": {}},
    )

    messages = result["messages"]
    tool_messages = [message for message in messages if isinstance(message, ToolMessage)]

    assert fake_model.bound_tool_names == ["Database_Search"]
    assert fake_retriever.queries == ["请假需要提交哪些材料？"]
    assert len(fake_model.calls) == 2
    assert messages[1].tool_calls[0]["name"] == "Database_Search"
    assert len(tool_messages) == 1
    assert tool_messages[0].tool_call_id == "call-database-search-1"
    assert "学生请假应当提交申请" in tool_messages[0].content
    assert "Source: leave_policy.md" in tool_messages[0].content
    assert "Chunk: leave_policy.md::chunk-0001" in tool_messages[0].content
    assert any(isinstance(message, ToolMessage) for message in fake_model.calls[1])
    assert messages[-1].content == "根据请假制度，需要提交申请并上传证明材料。"


@pytest.mark.asyncio
async def test_rag_assistant_empty_retrieval_passes_empty_tool_context_to_model(monkeypatch):
    fake_retriever = FakeRetriever([])
    fake_model = DatabaseSearchFakeModel(
        "未知校园制度是什么？",
        "当前知识库中没有找到明确依据。",
    )
    monkeypatch.setattr(campus_tools, "load_chroma_db", lambda: fake_retriever)
    monkeypatch.setattr(rag_module, "Safeguard", SafeSafeguard)
    monkeypatch.setattr(rag_module, "get_model", lambda model_name: fake_model)

    result = await rag_module.rag_assistant.ainvoke(
        {"messages": [HumanMessage(content="未知校园制度是什么？")]},
        config={"configurable": {}},
    )

    tool_message = next(message for message in result["messages"] if isinstance(message, ToolMessage))

    # Database_Search currently returns an empty context; no-answer wording is model-driven.
    assert fake_retriever.queries == ["未知校园制度是什么？"]
    assert tool_message.content == ""
    assert result["messages"][-1].content == "当前知识库中没有找到明确依据。"


def test_rag_assistant_pending_tool_calls_routes_database_search_and_final_answer():
    tool_call_state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "Database_Search",
                        "args": {"query": "奖学金规定"},
                        "id": "call-database-search-1",
                        "type": "tool_call",
                    }
                ],
            )
        ]
    }
    final_answer_state = {"messages": [AIMessage(content="已基于知识库回答。")]}

    assert rag_module.pending_tool_calls(tool_call_state) == "tools"
    assert rag_module.pending_tool_calls(final_answer_state) == "done"
