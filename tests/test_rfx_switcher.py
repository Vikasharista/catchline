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


def test_new_rfx_auto_seeds_and_does_not_touch_a_prior_rfx(client):
    """create_rfx now auto-seeds the reference draft (no more manual "Load
    reference RFx" button) — verify that still leaves each RFx's own data
    independent.
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
    assert rfx1["line_count"] == 30  # auto-seeded on creation
    assert rfx2["line_count"] == 30  # auto-seeded independently

    # rfx1's draft is still fully intact after rfx2 was created
    draft1 = client.get(f"/api/rfx/{rfx1_id}").json()
    assert len(draft1["draft"]["lines"]) == 30
