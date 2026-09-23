import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.api.deps import get_session
from app.main import app


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)

    def override_get_session():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_session] = override_get_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_list_rfx_empty(client):
    assert client.get("/api/rfx").json() == []


def test_new_rfx_starts_blank_and_does_not_touch_a_prior_rfx(client):
    """create_rfx seeds suppliers/history but leaves the draft itself
    blank — the co-pilot builds it up through chat instead of every new
    RFQ silently showing up pre-filled with the 30-line reference draft.
    Verify that still leaves each RFx's own data independent.
    """
    rfx1_id = client.post("/api/rfx").json()["id"]
    rfx2_id = client.post("/api/rfx").json()["id"]
    assert rfx2_id != rfx1_id

    listing = client.get("/api/rfx").json()
    assert len(listing) == 2
    ids = {r["id"] for r in listing}
    assert ids == {rfx1_id, rfx2_id}

    rfx1 = next(r for r in listing if r["id"] == rfx1_id)
    rfx2 = next(r for r in listing if r["id"] == rfx2_id)
    assert rfx1["line_count"] == 0
    assert rfx2["line_count"] == 0

    # each RFx got its own greeting message asking about scope
    history1 = client.get(f"/api/rfx/{rfx1_id}/copilot/messages").json()
    assert len(history1) == 1
    assert history1[0]["role"] == "assistant"
    assert "scope" in history1[0]["content"].lower()

    # explicitly seeding the reference draft on rfx1 doesn't touch rfx2
    client.post(f"/api/rfx/{rfx1_id}/seed-reference")
    draft1 = client.get(f"/api/rfx/{rfx1_id}").json()
    assert len(draft1["draft"]["lines"]) == 30
    draft2 = client.get(f"/api/rfx/{rfx2_id}").json()
    assert len(draft2["draft"]["lines"]) == 0
