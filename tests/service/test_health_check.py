from unittest.mock import Mock

from service import service as service_module


def test_health_check_returns_current_service_status(test_client, monkeypatch):
    monkeypatch.setattr(service_module.settings, "LANGFUSE_TRACING", False)

    response = test_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_check_reports_optional_langfuse_disconnection_without_crashing(
    test_client, monkeypatch
):
    monkeypatch.setattr(service_module.settings, "LANGFUSE_TRACING", True)

    def fail_langfuse():
        raise RuntimeError("langfuse unavailable")

    monkeypatch.setattr(service_module, "Langfuse", fail_langfuse)

    response = test_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "langfuse": "disconnected"}


def test_health_check_is_stable_when_agent_dependency_is_unavailable(test_client, monkeypatch):
    """Current liveness endpoint does not yet expose agent/store readiness."""
    monkeypatch.setattr(service_module.settings, "LANGFUSE_TRACING", False)
    unavailable_agent = Mock(side_effect=RuntimeError("agent unavailable"))
    monkeypatch.setattr(service_module, "get_agent", unavailable_agent)

    response = test_client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    unavailable_agent.assert_not_called()
    # TODO: Add a readiness endpoint if degraded agent/store state must be observable.
