"""The chat panel used to lose its whole history on reload/navigation
because the frontend never fetched it back — ChatTurn rows were persisted
all along, but nothing served them. These test the API contract the fixed
frontend relies on: GET returns history with proposals attached to the
right message, and POST's response is enriched with full proposal objects
(not bare ids) so the UI can render an Accept/Reject card immediately.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.api.deps import get_session
from app.copilot import agent as copilot_agent
from app.main import app


@pytest.fixture
def client(monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    def override_get_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session

    def fake_loop(messages, tools, tool_impls, **kwargs):
        tool_impls["propose_change"](
            section="lines",
            op="add",
            target="lines",
            value={"line_id": "L99", "species": "Test cod", "form": "Fillet", "grade": "Standard", "annual_volume_kg": 1000},
            reason="test",
            origin="from_you",
        )
        return "I've suggested 1 change.", []

    monkeypatch.setattr(copilot_agent, "run_tool_loop", fake_loop)

    yield TestClient(app)
    app.dependency_overrides.clear()


def test_history_has_only_the_greeting_for_a_fresh_rfx(client):
    """A new RFx starts with a blank draft + a canned greeting (not an LLM
    call) asking about scope, so the buyer sees the co-pilot prompting
    them instead of a silent empty chat."""
    rfx_id = client.post("/api/rfx").json()["id"]
    history = client.get(f"/api/rfx/{rfx_id}/copilot/messages").json()
    assert len(history) == 1
    assert history[0]["role"] == "assistant"
    assert "scope" in history[0]["content"].lower()


def test_sent_message_is_persisted_and_reloadable(client):
    rfx_id = client.post("/api/rfx").json()["id"]
    client.post(f"/api/rfx/{rfx_id}/copilot/messages", json={"message": "Add cod, 1000kg"})

    history = client.get(f"/api/rfx/{rfx_id}/copilot/messages").json()
    assert [m["role"] for m in history] == ["assistant", "user", "assistant"]
    assert history[1]["content"] == "Add cod, 1000kg"
    assert history[2]["content"] == "I've suggested 1 change."


def test_proposal_is_attached_to_the_assistant_turn_that_created_it(client):
    rfx_id = client.post("/api/rfx").json()["id"]
    client.post(f"/api/rfx/{rfx_id}/copilot/messages", json={"message": "Add cod, 1000kg"})

    history = client.get(f"/api/rfx/{rfx_id}/copilot/messages").json()
    assert history[1]["proposals"] == []
    assert len(history[2]["proposals"]) == 1
    proposal = history[2]["proposals"][0]
    assert proposal["target"] == "lines"
    assert proposal["status"] == "pending"


def test_post_response_includes_full_proposal_objects_not_just_ids(client):
    rfx_id = client.post("/api/rfx").json()["id"]
    resp = client.post(f"/api/rfx/{rfx_id}/copilot/messages", json={"message": "Add cod, 1000kg"}).json()
    assert len(resp["proposals"]) == 1
    assert resp["proposals"][0]["section"] == "lines"
    assert resp["proposals"][0]["status"] == "pending"


def test_history_reflects_proposal_status_after_accept(client):
    rfx_id = client.post("/api/rfx").json()["id"]
    resp = client.post(f"/api/rfx/{rfx_id}/copilot/messages", json={"message": "Add cod, 1000kg"}).json()
    proposal_id = resp["proposals"][0]["id"]

    client.post(f"/api/proposals/{proposal_id}/accept")

    history = client.get(f"/api/rfx/{rfx_id}/copilot/messages").json()
    assert history[2]["proposals"][0]["status"] == "accepted"
