import pytest


@pytest.fixture(autouse=True)
def isolate_compiled_agent_runtime_dependencies():
    """Keep service lifespan resources from leaking into graph-level unit tests."""
    from agents import rag_assistant as rag_module
    from agents import research_assistant as research_module

    graphs = [research_module.research_assistant, rag_module.rag_assistant]
    prior_dependencies = [(graph.checkpointer, graph.store) for graph in graphs]
    for graph in graphs:
        graph.checkpointer = None
        graph.store = None

    try:
        yield
    finally:
        for graph, (checkpointer, store) in zip(graphs, prior_dependencies, strict=True):
            graph.checkpointer = checkpointer
            graph.store = store
