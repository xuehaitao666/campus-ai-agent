import logging
import os
from typing import Any

from langchain_aws import AmazonKnowledgeBasesRetriever
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig, RunnableLambda, RunnableSerializable
from langchain_core.runnables.base import RunnableSequence
from langgraph.graph import END, MessagesState, StateGraph
from langgraph.managed import RemainingSteps

from agents.campus_prompt import CAMPUS_AI_AGENT_SYSTEM_PROMPT
from core import get_model, settings

logger = logging.getLogger(__name__)


# Define the state
class AgentState(MessagesState, total=False):
    """State for Knowledge Base agent."""

    remaining_steps: RemainingSteps
    retrieved_documents: list[dict[str, Any]]
    kb_documents: str


# Create the retriever
def get_kb_retriever():
    """Create and return a Knowledge Base retriever instance."""
    # Get the Knowledge Base ID from environment
    kb_id = os.environ.get("AWS_KB_ID", "")
    if not kb_id:
        raise ValueError("AWS_KB_ID environment variable must be set")

    # Create the retriever with the specified Knowledge Base ID
    retriever = AmazonKnowledgeBasesRetriever(
        knowledge_base_id=kb_id,
        retrieval_config={
            "vectorSearchConfiguration": {
                "numberOfResults": 3,
            }
        },
    )
    return retriever


def wrap_model(model: BaseChatModel) -> RunnableSerializable[AgentState, AIMessage]:
    """Wrap the model with a system prompt for the Knowledge Base agent."""

    def create_system_message(state):
        base_prompt = f"""{CAMPUS_AI_AGENT_SYSTEM_PROMPT}

        你将收到用户问题以及从校园知识库中检索到的相关文档。请使用这些文档辅助回答课程、活动、校园制度和学习规划相关问题。

        知识库回答规则：
        1. 校园制度类问题应主要依据检索到的文档回答；
        2. 如果文档包含答案，请清晰、简洁、结构化地回答；
        3. 如果文档不足，请说明“当前知识库中没有找到明确依据，建议以学校官方通知或辅导员答复为准”；
        4. 不要编造文档中不存在的学校规定、流程、时间、地点或教师信息；
        5. 引用具体信息时，请尽量说明来源文档；
        6. 如果文档之间有冲突，请说明存在不同说法，并提醒用户以官方最新通知为准；

        请用适合大学生阅读的语气回答，必要时使用 Markdown 分点和表格。
        """

        # Check if documents were retrieved
        if "kb_documents" in state:
            # Append document information to the system prompt
            document_prompt = f"\n\n以下是从校园知识库中检索到的相关文档：\n\n{state['kb_documents']}\n\n请基于这些文档回答用户问题。对于没有明确依据的内容，请明确说明不确定。"
            return [SystemMessage(content=base_prompt + document_prompt)] + state["messages"]
        else:
            # No documents were retrieved
            no_docs_prompt = (
                "\n\n当前校园知识库中没有检索到与该问题相关的文档。"
            )
            return [SystemMessage(content=base_prompt + no_docs_prompt)] + state["messages"]

    preprocessor = RunnableLambda(
        create_system_message,
        name="StateModifier",
    )
    return RunnableSequence(preprocessor, model)


async def retrieve_documents(state: AgentState, config: RunnableConfig) -> AgentState:
    """Retrieve relevant documents from the knowledge base."""
    # Get the last human message
    human_messages = [msg for msg in state["messages"] if isinstance(msg, HumanMessage)]
    if not human_messages:
        # Include messages from original state
        return {"messages": [], "retrieved_documents": []}

    # Use the last human message as the query
    query = human_messages[-1].content

    try:
        # Initialize the retriever
        retriever = get_kb_retriever()

        # Retrieve documents
        retrieved_docs = await retriever.ainvoke(query)

        # Create document summaries for the state
        document_summaries = []
        for i, doc in enumerate(retrieved_docs, 1):
            summary = {
                "id": doc.metadata.get("id", f"doc-{i}"),
                "source": doc.metadata.get("source", "Unknown"),
                "title": doc.metadata.get("title", f"Document {i}"),
                "content": doc.page_content,
                "relevance_score": doc.metadata.get("score", 0),
            }
            document_summaries.append(summary)

        logger.info(f"Retrieved {len(document_summaries)} documents for query: {query[:50]}...")

        return {"retrieved_documents": document_summaries, "messages": []}

    except Exception as e:
        logger.error(f"Error retrieving documents: {str(e)}")
        return {"retrieved_documents": [], "messages": []}


async def prepare_augmented_prompt(state: AgentState, config: RunnableConfig) -> AgentState:
    """Prepare a prompt augmented with retrieved document content."""
    # Get retrieved documents
    documents = state.get("retrieved_documents", [])

    if not documents:
        return {"messages": []}

    # Format retrieved documents for the model
    formatted_docs = "\n\n".join(
        [
            f"--- Document {i + 1} ---\n"
            f"Source: {doc.get('source', 'Unknown')}\n"
            f"Title: {doc.get('title', 'Unknown')}\n\n"
            f"{doc.get('content', '')}"
            for i, doc in enumerate(documents)
        ]
    )

    # Store formatted documents in the state
    return {"kb_documents": formatted_docs, "messages": []}


async def acall_model(state: AgentState, config: RunnableConfig) -> AgentState:
    """Generate a response based on the retrieved documents."""
    m = get_model(config["configurable"].get("model", settings.DEFAULT_MODEL))
    model_runnable = wrap_model(m)

    response = await model_runnable.ainvoke(state, config)

    return {"messages": [response]}


# Define the graph
agent = StateGraph(AgentState)

# Add nodes
agent.add_node("retrieve_documents", retrieve_documents)
agent.add_node("prepare_augmented_prompt", prepare_augmented_prompt)
agent.add_node("model", acall_model)

# Set entry point
agent.set_entry_point("retrieve_documents")

# Add edges to define the flow
agent.add_edge("retrieve_documents", "prepare_augmented_prompt")
agent.add_edge("prepare_augmented_prompt", "model")
agent.add_edge("model", END)

# Compile the agent
kb_agent = agent.compile()
