"""API-level checks that the credit-wastage guardrails actually surface as
the right HTTP status/detail on the co-pilot and analyst endpoints, not
just that the underlying functions raise the right exception in isolation.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.rate_limit as rate_limit_module
from app.api.deps import get_session
from app.copilot import agent as copilot_agent
from app.llm import BudgetExceededError
from app.main import app


@pytest.fixture
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    def override_get_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session

    from collections import defaultdict, deque

    monkeypatch.setattr(rate_limit_module, "_hits", defaultdict(deque))

    yield TestClient(app)
    app.dependency_overrides.clear()


def test_copilot_returns_429_once_rate_limited(client, monkeypatch):
    monkeypatch.setattr(rate_limit_module.settings, "llm_chat_rate_limit_count", 1)

    def fake_loop(*args, **kwargs):
        return "ok", []

    monkeypatch.setattr(copilot_agent, "run_tool_loop", fake_loop)

    rfx_id = client.post("/api/rfx").json()["id"]
    first = client.post(f"/api/rfx/{rfx_id}/copilot/messages", json={"message": "hello"})
    assert first.status_code == 200

    second = client.post(f"/api/rfx/{rfx_id}/copilot/messages", json={"message": "hello again"})
    assert second.status_code == 429
    assert second.json()["detail"]["error"] == "Rate limited"


def test_copilot_returns_402_on_budget_exceeded(client, monkeypatch):
    def fake_loop(*args, **kwargs):
        raise BudgetExceededError("Daily LLM budget of $3.00 reached")

    monkeypatch.setattr(copilot_agent, "run_tool_loop", fake_loop)

    rfx_id = client.post("/api/rfx").json()["id"]
    resp = client.post(
        f"/api/rfx/{rfx_id}/copilot/messages",
        json={"message": "Add salmon HOG 3-4kg, 60 tonnes annual volume"},
    )
    assert resp.status_code == 402
    assert resp.json()["detail"]["error"] == "Daily LLM budget reached"
